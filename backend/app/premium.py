"""Premium sandbox membership and payment orders API."""
from datetime import datetime, timedelta, timezone
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
from app.premium_plans import PLANS, PlanDefinition, get_plan
from app.security import AuthError
from app.vnpay_adapter import VnpayAdapter, VnpayConfigurationError

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
        result.append(
            PlanInfoDto(
                tier=plan.tier,
                name=plan.name,
                duration_days=plan.duration_days,
                boost_multiplier=plan.boost_multiplier,
                amount_usd_formatted=plan.amount_usd_formatted,
                amount_vnd=vnd_price,
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

    # Resolve configured VND price
    amount_vnd = plan.default_amount_vnd
    if premium_settings:
        if plan.tier == "plus":
            amount_vnd = premium_settings.vnpay_price_plus_vnd
        elif plan.tier == "prime":
            amount_vnd = premium_settings.vnpay_price_prime_vnd

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
        payment_url=payment_url,
        created_at=now,
        updated_at=now,
    )
    account.db.add(order)
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
    settings = getattr(request.app.state, "settings", None)
    if settings and getattr(settings, "ENVIRONMENT", "").lower() == "production":
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
    """Handle VNPAY browser return callback."""
    now = request.app.state.auth.now()
    vnpay: VnpayAdapter | None = getattr(request.app.state, "vnpay", None)
    params = dict(request.query_params)

    if not vnpay or not vnpay.is_configured():
        return RedirectResponse("/premium?vnp_status=error&message=not_configured")

    is_valid, filtered = vnpay.verify_response(params)
    if not is_valid:
        return RedirectResponse("/premium?vnp_status=error&message=invalid_signature")

    order_code = filtered.get("vnp_TxnRef")
    response_code = filtered.get("vnp_ResponseCode")
    vnp_amount_str = filtered.get("vnp_Amount")
    txn_no = filtered.get("vnp_TransactionNo")

    with request.app.state.auth_session_factory() as db, db.begin():
        order = db.scalar(select(SubscriptionOrder).where(SubscriptionOrder.order_code == order_code))
        if not order:
            return RedirectResponse("/premium?vnp_status=error&message=order_not_found")

        # Amount check
        try:
            paid_amount_vnd = int(vnp_amount_str) // 100
        except (ValueError, TypeError):
            return RedirectResponse("/premium?vnp_status=error&message=invalid_amount")

        if paid_amount_vnd != order.amount_vnd:
            order.status = "failed"
            order.updated_at = now
            order.provider_response_code = response_code
            return RedirectResponse("/premium?vnp_status=error&message=amount_mismatch")

        order.provider_txn_id = txn_no
        order.provider_response_code = response_code
        order.provider_payload = filtered
        order.updated_at = now

        if response_code == "00":
            if order.status != "success":
                order.status = "success"
                order.completed_at = now
                sub = db.scalar(select(UserSubscription).where(UserSubscription.user_id == order.user_id))
                if sub:
                    sub.tier = order.tier
                    sub.status = "active"
                    sub.starts_at = now
                    sub.expires_at = now + timedelta(days=order.duration_days)
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
            return RedirectResponse(f"/premium?vnp_status=success&order_code={order.order_code}")
        elif response_code == "24":
            order.status = "cancelled"
            order.completed_at = now
            return RedirectResponse(f"/premium?vnp_status=cancelled&order_code={order.order_code}")
        else:
            order.status = "failed"
            order.completed_at = now
            return RedirectResponse(f"/premium?vnp_status=failed&order_code={order.order_code}")


@router.get("/vnpay-ipn", operation_id="handleVnpayIpn")
def handle_vnpay_ipn(request: Request):
    """Handle VNPAY server-to-server IPN callback."""
    now = request.app.state.auth.now()
    vnpay: VnpayAdapter | None = getattr(request.app.state, "vnpay", None)
    params = dict(request.query_params)

    if not vnpay or not vnpay.is_configured():
        return {"RspCode": "99", "Message": "Unknown error / VNPAY not configured"}

    is_valid, filtered = vnpay.verify_response(params)
    if not is_valid:
        return {"RspCode": "97", "Message": "Invalid Checksum"}

    order_code = filtered.get("vnp_TxnRef")
    response_code = filtered.get("vnp_ResponseCode")
    vnp_amount_str = filtered.get("vnp_Amount")
    txn_no = filtered.get("vnp_TransactionNo")

    with request.app.state.auth_session_factory() as db, db.begin():
        order = db.scalar(select(SubscriptionOrder).where(SubscriptionOrder.order_code == order_code))
        if not order:
            return {"RspCode": "01", "Message": "Order not found"}

        # Amount check
        try:
            paid_amount_vnd = int(vnp_amount_str) // 100
        except (ValueError, TypeError):
            return {"RspCode": "04", "Message": "Invalid amount"}

        if paid_amount_vnd != order.amount_vnd:
            return {"RspCode": "04", "Message": "Invalid amount"}

        if order.status == "success":
            return {"RspCode": "02", "Message": "Order already confirmed"}

        order.provider_txn_id = txn_no
        order.provider_response_code = response_code
        order.provider_payload = filtered
        order.updated_at = now

        if response_code == "00":
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
            order.status = "failed"
            order.completed_at = now
            return {"RspCode": "00", "Message": "Confirm Success"}
