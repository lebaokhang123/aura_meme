"""Premium sandbox membership and payment orders API."""
from datetime import datetime, timedelta, timezone
import logging
import math
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import CSRF_HEADER, ERRORS, current_session, session_cookie
from app.auth_schemas import ErrorResponse
from app.models import SubscriptionOrder, User, UserSubscription
from app.permissions import require_account_csrf, require_authenticated_user
from app.premium_plans import PLANS, PlanDefinition, get_plan, round_vnd_to_nearest_10k
from app.security import AuthError
from app.vnpay_adapter import VnpayAdapter, VnpayConfigurationError

logger = logging.getLogger("aurameme.premium")

router = APIRouter(prefix="/api/v1/premium", tags=["Premium Sandbox"])


class CreateOrderInput(BaseModel):
    plan_tier: Literal["plus", "prime"]
    provider: Literal["sandbox_simulated", "vnpay_sandbox"] = "sandbox_simulated"


class SimulateOrderInput(BaseModel):
    action: Literal["pay_success", "pay_fail", "cancel"]


class OrderDto(BaseModel):
    id: UUID
    order_code: str
    tier: str
    duration_days: int
    amount_usd_cents: int
    amount_usd_formatted: str
    amount_vnd: int
    currency: str
    status: str
    provider: str
    payment_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class SubscriptionDto(BaseModel):
    tier: str
    is_active: bool
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    days_remaining: int = 0
    boost_multiplier: int = 1
    sandbox_mode: bool = True
    order_code: str | None = None


class PlanInfoDto(BaseModel):
    tier: str
    name: str
    duration_days: int
    boost_multiplier: int
    amount_usd_formatted: str
    amount_vnd: int
    amount_vnd_formatted: str


class PremiumStatusResponse(BaseModel):
    subscription: SubscriptionDto
    plans: list[PlanInfoDto]
    vnpay_configured: bool
    vnpay_pricing_approved: bool
    sandbox_notice: str


def active_subscription_dto(sub: UserSubscription | None, now: datetime) -> SubscriptionDto:
    if not sub:
        return SubscriptionDto(tier="free", is_active=False, boost_multiplier=1)

    if sub.status == "active":
        if sub.expires_at <= now:
            return SubscriptionDto(tier="free", is_active=False, boost_multiplier=1)
        remaining = max(0, math.ceil((sub.expires_at - now).total_seconds() / 86400.0))
        boost = 2 if sub.tier == "plus" else (3 if sub.tier == "prime" else 1)
        return SubscriptionDto(
            tier=sub.tier,
            is_active=True,
            starts_at=sub.starts_at,
            expires_at=sub.expires_at,
            days_remaining=remaining,
            boost_multiplier=boost,
            sandbox_mode=True,
        )

    return SubscriptionDto(tier="free", is_active=False, boost_multiplier=1)


def read_user_subscription(db: Session, user_id: UUID, now: datetime) -> UserSubscription | None:
    sub = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
    if sub and sub.status == "active" and sub.expires_at <= now:
        sub.status = "expired"
        sub.updated_at = now
        db.flush()
    return sub


def get_plans_info(request: Request) -> list[PlanInfoDto]:
    premium_settings = getattr(request.app.state, "premium", None)
    result = []
    for plan in PLANS.values():
        vnd_price = plan.default_amount_vnd
        if premium_settings:
            if plan.tier == "plus":
                vnd_price = premium_settings.vnpay_price_plus_vnd
            elif plan.tier == "prime":
                vnd_price = premium_settings.vnpay_price_prime_vnd
        vnd_price = round_vnd_to_nearest_10k(vnd_price)
        formatted_vnd = f"{vnd_price:,.0f} VNĐ".replace(",", ".")
        result.append(
            PlanInfoDto(
                tier=plan.tier,
                name=plan.name,
                duration_days=plan.duration_days,
                boost_multiplier=plan.boost_multiplier,
                amount_usd_formatted=plan.amount_usd_formatted,
                amount_vnd=vnd_price,
                amount_vnd_formatted=formatted_vnd,
            )
        )
    return result


@router.get(
    "/status",
    response_model=PremiumStatusResponse,
    operation_id="getPremiumStatus",
    responses=ERRORS,
)
def get_premium_status(request: Request, raw=Depends(session_cookie)):
    now = request.app.state.auth.now()
    premium_settings = getattr(request.app.state, "premium", None)
    vnpay: VnpayAdapter | None = getattr(request.app.state, "vnpay", None)

    vnpay_configured = bool(vnpay and vnpay.is_configured())
    vnpay_pricing_approved = bool(premium_settings and premium_settings.vnpay_pricing_approved)

    sub_dto = SubscriptionDto(tier="free", is_active=False, boost_multiplier=1)

    if raw:
        try:
            with request.app.state.auth_session_factory() as db:
                record = current_session(db, request.app.state.auth, raw)
                sub = read_user_subscription(db, record.user_id, now)
                sub_dto = active_subscription_dto(sub, now)
                if sub and sub.order_id:
                    order = db.get(SubscriptionOrder, sub.order_id)
                    if order:
                        sub_dto.order_code = order.order_code
        except Exception:
            sub_dto = SubscriptionDto(tier="free", is_active=False, boost_multiplier=1)

    return PremiumStatusResponse(
        subscription=sub_dto,
        plans=get_plans_info(request),
        vnpay_configured=vnpay_configured,
        vnpay_pricing_approved=vnpay_pricing_approved,
        sandbox_notice="Môi trường thử nghiệm Sandbox — Không thu tiền thật.",
    )


@router.post(
    "/orders",
    response_model=OrderDto,
    status_code=201,
    operation_id="createSubscriptionOrder",
    responses=ERRORS,
    openapi_extra=CSRF_HEADER,
)
def create_subscription_order(
    payload: CreateOrderInput,
    request: Request,
    account=Depends(require_account_csrf),
):
    plan: PlanDefinition = get_plan(payload.plan_tier)
    now = request.app.state.auth.now()
    premium_settings = getattr(request.app.state, "premium", None)
    vnpay: VnpayAdapter | None = getattr(request.app.state, "vnpay", None)

    # Resolve configured VND price and enforce 10,000 VND rounding policy
    amount_vnd = plan.default_amount_vnd
    if premium_settings:
        if plan.tier == "plus":
            amount_vnd = premium_settings.vnpay_price_plus_vnd
        elif plan.tier == "prime":
            amount_vnd = premium_settings.vnpay_price_prime_vnd
    amount_vnd = round_vnd_to_nearest_10k(amount_vnd)

    payment_url = None

    if payload.provider == "vnpay_sandbox":
        if not vnpay or not vnpay.is_configured():
            raise AuthError(
                422,
                "VNPAY_NOT_AVAILABLE",
                "Cổng VNPAY Sandbox chưa được cấu hình credentials hoặc giá VND chưa được duyệt bởi Owner.",
            )
        order_code = f"AM-{plan.tier.upper()}-{uuid4().hex[:10].upper()}"
        payment_url = vnpay.create_payment_url(
            order_code=order_code,
            amount_vnd=amount_vnd,
            order_info=f"Thanh toan goi {plan.name} Sandbox",
            ip_addr=request.client.host if request.client else "127.0.0.1",
            created_at=now,
        )
    else:
        order_code = f"AM-SIM-{plan.tier.upper()}-{uuid4().hex[:10].upper()}"

    order = SubscriptionOrder(
        id=uuid4(),
        order_code=order_code,
        user_id=account.user.id,
        tier=plan.tier,
        duration_days=plan.duration_days,
        amount_cents=plan.amount_usd_cents,
        amount_vnd=amount_vnd,
        currency="USD",
        status="pending",
        provider=payload.provider,
        provider_payload={},
        payment_url=payment_url,
        created_at=now,
        updated_at=now,
    )
    try:
        account.db.add(order)
        account.db.flush()
    except Exception as exc:
        logger.error(
            "Failed to save subscription order '%s' for user '%s': %s",
            order_code,
            account.user.id,
            exc,
        )
        raise

    return OrderDto(
        id=order.id,
        order_code=order.order_code,
        tier=order.tier,
        duration_days=order.duration_days,
        amount_usd_cents=order.amount_cents,
        amount_usd_formatted=plan.amount_usd_formatted,
        amount_vnd=order.amount_vnd,
        currency=order.currency,
        status=order.status,
        provider=order.provider,
        payment_url=order.payment_url,
        created_at=order.created_at,
        completed_at=order.completed_at,
    )


@router.get(
    "/orders/{order_code}",
    response_model=OrderDto,
    operation_id="getSubscriptionOrder",
    responses={**ERRORS, 404: {"model": ErrorResponse}},
)
def get_subscription_order(
    order_code: str,
    account=Depends(require_authenticated_user),
):
    """Retrieve authoritative order status for authenticated user."""
    order = account.db.scalar(
        select(SubscriptionOrder).where(
            SubscriptionOrder.order_code == order_code,
            SubscriptionOrder.user_id == account.user.id,
        )
    )
    if not order:
        raise AuthError(404, "NOT_FOUND", "Đơn hàng không tồn tại hoặc không thuộc tài khoản của bạn.")

    plan = get_plan(order.tier)
    return OrderDto(
        id=order.id,
        order_code=order.order_code,
        tier=order.tier,
        duration_days=order.duration_days,
        amount_usd_cents=order.amount_cents,
        amount_usd_formatted=plan.amount_usd_formatted,
        amount_vnd=order.amount_vnd,
        currency=order.currency,
        status=order.status,
        provider=order.provider,
        payment_url=order.payment_url,
        created_at=order.created_at,
        completed_at=order.completed_at,
    )


@router.post(
    "/orders/{order_code}/simulate",
    response_model=OrderDto,
    operation_id="simulateSubscriptionOrder",
    responses={**ERRORS, 404: {"model": ErrorResponse}},
    openapi_extra=CSRF_HEADER,
)
def simulate_subscription_order(
    order_code: str,
    payload: SimulateOrderInput,
    request: Request,
    account=Depends(require_account_csrf),
):
    auth_runtime = getattr(request.app.state, "auth", None)
    auth_env = getattr(auth_runtime.settings, "auth_environment", "production") if auth_runtime and hasattr(auth_runtime, "settings") else "production"
    premium_settings = getattr(request.app.state, "premium", None)
    sandbox_enabled = getattr(premium_settings, "premium_sandbox_enabled", False) if premium_settings else False

    if auth_env == "production" or not sandbox_enabled:
        raise AuthError(403, "FORBIDDEN", "Môi trường giả lập (simulate) bị vô hiệu hóa trên môi trường production.")

    now = request.app.state.auth.now()
    order = account.db.scalar(
        select(SubscriptionOrder).where(
            SubscriptionOrder.order_code == order_code,
            SubscriptionOrder.user_id == account.user.id,
        )
    )
    if not order:
        raise AuthError(404, "NOT_FOUND", "Đơn hàng không tồn tại hoặc không thuộc tài khoản của bạn.")

    plan = get_plan(order.tier)

    # Idempotent response if order is already resolved
    if order.status in {"success", "failed", "cancelled"}:
        return OrderDto(
            id=order.id,
            order_code=order.order_code,
            tier=order.tier,
            duration_days=order.duration_days,
            amount_usd_cents=order.amount_cents,
            amount_usd_formatted=plan.amount_usd_formatted,
            amount_vnd=order.amount_vnd,
            currency=order.currency,
            status=order.status,
            provider=order.provider,
            payment_url=order.payment_url,
            created_at=order.created_at,
            completed_at=order.completed_at,
        )

    if payload.action == "pay_success":
        order.status = "success"
        order.completed_at = now
        order.provider_txn_id = f"SIM-{uuid4().hex[:12].upper()}"
        order.updated_at = now

        # Activate or extend membership idempotently without losing remaining days
        sub = account.db.scalar(select(UserSubscription).where(UserSubscription.user_id == account.user.id))
        if sub:
            sub.tier = order.tier
            sub.status = "active"
            base_time = sub.expires_at if (sub.expires_at and sub.expires_at > now) else now
            sub.expires_at = base_time + timedelta(days=order.duration_days)
            if not sub.starts_at or sub.starts_at > now:
                sub.starts_at = now
            sub.order_id = order.id
            sub.updated_at = now
        else:
            sub = UserSubscription(
                id=uuid4(),
                user_id=account.user.id,
                tier=order.tier,
                status="active",
                starts_at=now,
                expires_at=now + timedelta(days=order.duration_days),
                order_id=order.id,
                created_at=now,
                updated_at=now,
            )
            account.db.add(sub)

    elif payload.action == "pay_fail":
        order.status = "failed"
        order.completed_at = now
        order.updated_at = now
    elif payload.action == "cancel":
        order.status = "cancelled"
        order.completed_at = now
        order.updated_at = now

    account.db.flush()

    return OrderDto(
        id=order.id,
        order_code=order.order_code,
        tier=order.tier,
        duration_days=order.duration_days,
        amount_usd_cents=order.amount_cents,
        amount_usd_formatted=plan.amount_usd_formatted,
        amount_vnd=order.amount_vnd,
        currency=order.currency,
        status=order.status,
        provider=order.provider,
        payment_url=order.payment_url,
        created_at=order.created_at,
        completed_at=order.completed_at,
    )


@router.get("/vnpay-return", operation_id="handleVnpayReturn")
def handle_vnpay_return(request: Request):
    """Handle VNPAY browser return callback.

    IMPORTANT: This endpoint strictly performs signature verification and user redirection.
    It DOES NOT mutate order status, and DOES NOT grant subscription entitlements.
    Authoritative state mutation is performed exclusively by handle_vnpay_ipn.
    """
    vnpay: VnpayAdapter | None = getattr(request.app.state, "vnpay", None)
    params = dict(request.query_params)

    if not vnpay or not vnpay.is_configured():
        return RedirectResponse("/premium?vnp_status=error&message=not_configured", status_code=302)

    is_valid, filtered = vnpay.verify_response(params)
    if not is_valid:
        return RedirectResponse("/premium?vnp_status=error&message=invalid_signature", status_code=302)

    order_code = filtered.get("vnp_TxnRef")
    response_code = filtered.get("vnp_ResponseCode")

    with request.app.state.auth_session_factory() as db:
        order = db.scalar(select(SubscriptionOrder).where(SubscriptionOrder.order_code == order_code))
        if not order:
            return RedirectResponse("/premium?vnp_status=error&message=order_not_found", status_code=302)

        if response_code == "00":
            return RedirectResponse(f"/premium?vnp_status=success&order_code={order.order_code}", status_code=302)
        elif response_code == "24":
            return RedirectResponse(f"/premium?vnp_status=cancelled&order_code={order.order_code}", status_code=302)
        else:
            return RedirectResponse(f"/premium?vnp_status=failed&order_code={order.order_code}&code={response_code}", status_code=302)


@router.get("/vnpay-ipn", operation_id="handleVnpayIpn")
def handle_vnpay_ipn(request: Request):
    """Handle VNPAY server-to-server IPN callback.

    This is the sole authoritative webhook endpoint that validates transactions,
    updates order status, and activates user subscription entitlements.
    """
    now = request.app.state.auth.now()
    vnpay: VnpayAdapter | None = getattr(request.app.state, "vnpay", None)
    params = dict(request.query_params)

    if not vnpay or not vnpay.is_configured():
        return {"RspCode": "99", "Message": "Unknown error / VNPAY not configured"}

    is_valid, filtered = vnpay.verify_response(params)
    if not is_valid:
        return {"RspCode": "97", "Message": "Invalid Checksum"}

    # Merchant code check
    vnp_tmn_code = filtered.get("vnp_TmnCode")
    if not vnp_tmn_code or vnp_tmn_code != vnpay.tmn_code:
        return {"RspCode": "97", "Message": "Invalid Merchant Code"}

    order_code = filtered.get("vnp_TxnRef")
    response_code = filtered.get("vnp_ResponseCode")
    vnp_amount_str = filtered.get("vnp_Amount")
    txn_no = filtered.get("vnp_TransactionNo")
    txn_status = filtered.get("vnp_TransactionStatus")

    with request.app.state.auth_session_factory() as db, db.begin():
        # Concurrency safety: acquire row-level lock on the order
        order = db.scalar(
            select(SubscriptionOrder)
            .where(SubscriptionOrder.order_code == order_code)
            .with_for_update()
        )
        if not order:
            return {"RspCode": "01", "Message": "Order not found"}

        # Provider check: VNPAY IPN must never process simulated orders
        if order.provider != "vnpay_sandbox":
            return {"RspCode": "99", "Message": "Invalid order provider"}

        # Amount check: vnp_Amount is actual_vnd * 100
        try:
            vnp_amount_raw = int(vnp_amount_str)
        except (ValueError, TypeError):
            return {"RspCode": "04", "Message": "Invalid amount"}

        if vnp_amount_raw != order.amount_vnd * 100:
            return {"RspCode": "04", "Message": "Invalid amount"}

        # Idempotency: if order is already successful, acknowledge without re-granting
        if order.status == "success":
            return {"RspCode": "02", "Message": "Order already confirmed"}

        # Terminal state protection: do not revive failed or cancelled orders
        if order.status in {"failed", "cancelled", "expired"}:
            return {"RspCode": "02", "Message": "Order already processed"}

        order.provider_txn_id = txn_no
        order.provider_response_code = response_code
        order.provider_payload = filtered
        order.updated_at = now

        is_success = (
            response_code == "00"
            and txn_status == "00"
            and bool(txn_no)
            and txn_no != "0"
        )

        if is_success:
            order.status = "success"
            order.completed_at = now
            sub = db.scalar(select(UserSubscription).where(UserSubscription.user_id == order.user_id))
            if sub:
                sub.tier = order.tier
                sub.status = "active"
                base_time = sub.expires_at if (sub.expires_at and sub.expires_at > now) else now
                sub.expires_at = base_time + timedelta(days=order.duration_days)
                if not sub.starts_at or sub.starts_at > now:
                    sub.starts_at = now
                sub.order_id = order.id
                sub.updated_at = now
            else:
                sub = UserSubscription(
                    id=uuid4(),
                    user_id=order.user_id,
                    tier=order.tier,
                    status="active",
                    starts_at=now,
                    expires_at=now + timedelta(days=order.duration_days),
                    order_id=order.id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(sub)
            return {"RspCode": "00", "Message": "Confirm Success"}
        else:
            order.status = "cancelled" if response_code == "24" else "failed"
            order.completed_at = now
            return {"RspCode": "00", "Message": "Confirm Success"}
