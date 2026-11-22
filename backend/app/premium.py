"""Premium sandbox membership and payment orders API."""
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import re
from typing import Literal
from uuid import UUID, uuid4

ORDER_CODE_REGEX = re.compile(r"^AM-(PLUS|PRIME)-\d{9,12}-[A-Z0-9]{4,12}$")


def validate_order_code(order_code: str) -> str:
    """Validate order code format, length, and character set strictly."""
    if not order_code or len(order_code) > 64 or not ORDER_CODE_REGEX.match(order_code):
        raise AuthError(422, "INVALID_ORDER_CODE", "Mã đơn hàng không đúng định dạng.")
    return order_code

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

ORDER_EXPIRY_TIMEOUT = timedelta(hours=1)

from app.auth import CSRF_HEADER, ERRORS, current_session, session_cookie
from app.auth_schemas import ErrorResponse
from app.models import Role, SubscriptionOrder, User, UserRole, UserSubscription
from app.permissions import require_account_csrf, require_authenticated_user
from app.premium_plans import PLANS, PlanDefinition, get_plan, round_vnd_to_nearest_10k
from app.security import AuthError
from app.vnpay_adapter import VnpayAdapter, VnpayConfigurationError
from app.paypal_adapter import PaypalAdapter, PaypalError

logger = logging.getLogger("aurameme.premium")

router = APIRouter(prefix="/api/v1/premium", tags=["Premium Sandbox"])


class CreateOrderInput(BaseModel):
    plan_tier: Literal["plus", "prime"]
    provider: Literal["sandbox_simulated", "vnpay_sandbox", "paypal_sandbox", "unselected"] = "unselected"


class SimulateOrderInput(BaseModel):
    action: Literal["pay_success", "pay_fail", "cancel"]


class CaptureOrderInput(BaseModel):
    paypal_order_id: str | None = None
    mock_fail: bool = False


class OrderDto(BaseModel):
    id: UUID
    order_code: str
    tier: str
    duration_days: int
    amount_usd_cents: int
    amount_usd_formatted: str
    amount_vnd: int
    amount_vnd_formatted: str | None = None
    currency: str
    status: str
    provider: str
    provider_txn_id: str | None = None
    payment_url: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class OrderDetailDto(OrderDto):
    owner_username: str


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class OrderPage(BaseModel):
    items: list[OrderDto]
    pagination: Pagination


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
    paypal_configured: bool = False
    paypal_client_id: str | None = None
    paypal_mode: str = "sandbox"
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
    paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None)

    vnpay_configured = bool(vnpay and vnpay.is_configured())
    vnpay_pricing_approved = bool(premium_settings and premium_settings.vnpay_pricing_approved)
    paypal_configured = bool(paypal and paypal.is_configured())
    paypal_client_id = paypal.get_client_id() if (paypal and paypal.is_configured()) else None
    paypal_mode = getattr(paypal, "mode", "sandbox") if paypal else "sandbox"

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
        paypal_configured=paypal_configured,
        paypal_client_id=paypal_client_id,
        paypal_mode=paypal_mode,
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
    auth_runtime = getattr(request.app.state, "auth", None)
    auth_env = getattr(auth_runtime.settings, "auth_environment", "production") if auth_runtime and hasattr(auth_runtime, "settings") else "production"
    sandbox_enabled = getattr(premium_settings, "premium_sandbox_enabled", False) if premium_settings else False

    # Rate limiting: maximum 10 order creations per minute per user
    if auth_runtime and getattr(auth_runtime, "limiter", None):
        auth_runtime.limiter.check(f"order_create:{account.user.id}", limit=10, window=60)

    # Production boundary guard: block simulated sandbox orders in production
    if payload.provider == "sandbox_simulated":
        if auth_env == "production" or not sandbox_enabled:
            raise AuthError(403, "FORBIDDEN", "Phương thức thanh toán mô phỏng bị vô hiệu hóa trên môi trường production.")

    # Resolve configured VND price and enforce 10,000 VND rounding policy
    amount_vnd = plan.default_amount_vnd
    if premium_settings:
        if plan.tier == "plus":
            amount_vnd = premium_settings.vnpay_price_plus_vnd
        elif plan.tier == "prime":
            amount_vnd = premium_settings.vnpay_price_prime_vnd
    amount_vnd = round_vnd_to_nearest_10k(amount_vnd)

    # Serialize different sessions and tabs for the same buyer.
    account.db.execute(select(User.id).where(User.id == account.user.id).with_for_update())
    # Reopening an order preserves its original lifetime.
    existing_active = account.db.scalar(
        select(SubscriptionOrder).where(
            SubscriptionOrder.user_id == account.user.id,
            SubscriptionOrder.tier == plan.tier,
            SubscriptionOrder.status == "pending",
            SubscriptionOrder.created_at > now - ORDER_EXPIRY_TIMEOUT,
        ).order_by(SubscriptionOrder.created_at.desc(), SubscriptionOrder.id.desc()).with_for_update()
    )
    if existing_active and isinstance(existing_active, SubscriptionOrder):
        if payload.provider != "unselected" and existing_active.provider == "unselected":
            existing_active.provider = payload.provider
            existing_active.updated_at = now
            account.db.flush()
        plan_active = get_plan(existing_active.tier)
        return OrderDto(
            id=existing_active.id,
            order_code=existing_active.order_code,
            tier=existing_active.tier,
            duration_days=existing_active.duration_days,
            amount_usd_cents=existing_active.amount_cents,
            amount_usd_formatted=plan_active.amount_usd_formatted,
            amount_vnd=existing_active.amount_vnd,
            amount_vnd_formatted=f"{existing_active.amount_vnd:,} VNĐ".replace(",", "."),
            currency=existing_active.currency,
            status=existing_active.status,
            provider=existing_active.provider,
            provider_txn_id=existing_active.provider_txn_id,
            payment_url=existing_active.payment_url,
            created_at=existing_active.created_at,
            completed_at=existing_active.completed_at,
        )

    payment_url = None
    provider_txn_id = None
    provider_payload = {}

    if payload.provider == "vnpay_sandbox":
        if not vnpay or not vnpay.is_configured():
            raise AuthError(
                422,
                "VNPAY_NOT_AVAILABLE",
                "Cổng VNPAY Sandbox chưa được cấu hình credentials hoặc giá VND chưa được duyệt bởi Owner.",
            )
        order_code = f"AM-{plan.tier.upper()}-{int(now.timestamp())}-{uuid4().hex[:8].upper()}"
        payment_url = vnpay.create_payment_url(
            order_code=order_code,
            amount_vnd=amount_vnd,
            order_info=f"Thanh toan goi {plan.name} Sandbox",
            ip_addr=request.client.host if request.client else "127.0.0.1",
            created_at=now,
        )
    elif payload.provider == "paypal_sandbox":
        paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None)
        order_code = f"AM-{plan.tier.upper()}-{int(now.timestamp())}-{uuid4().hex[:8].upper()}"
        from urllib.parse import urlsplit, urlunsplit
        origin = request.headers.get("origin")
        if origin not in auth_runtime.settings.auth_allowed_origins:
            raise AuthError(403, "FORBIDDEN", "Invalid checkout origin.")
        parsed = urlsplit(origin)
        return_url = urlunsplit((parsed.scheme, parsed.netloc, "/premium/checkout", f"order={order_code}", ""))
        cancel_url = return_url + "&cancelled=true"
        if paypal and paypal.is_configured():
            try:
                pp_order = paypal.create_order(
                    order_code=order_code,
                    plan_tier=plan.tier,
                    return_url=return_url,
                    cancel_url=cancel_url,
                )
                payment_url = pp_order.get("approve_url")
                provider_txn_id = pp_order.get("id")
                provider_payload = pp_order
            except PaypalError as exc:
                logger.error("Failed to create PayPal order: %s", exc)
                raise AuthError(502, "PAYPAL_ERROR", f"Không thể tạo đơn hàng PayPal: {str(exc)}")
        else:
            # Sandbox simulated token when PayPal credentials are not yet configured in local test
            mock_id = f"MOCK-PP-{uuid4().hex[:12].upper()}"
            provider_txn_id = mock_id
            payment_url = f"https://www.sandbox.paypal.com/checkoutnow?token={mock_id}"
            provider_payload = {"mock": True, "id": mock_id}
    else:
        order_code = f"AM-{plan.tier.upper()}-{int(now.timestamp())}-{uuid4().hex[:8].upper()}"

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
        provider_txn_id=provider_txn_id,
        provider_payload=provider_payload,
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


@router.post(
    "/orders/{order_code}/init-paypal",
    response_model=OrderDto,
    operation_id="initPaypalOrder",
    responses={**ERRORS, 404: {"model": ErrorResponse}},
    openapi_extra=CSRF_HEADER,
)
def init_paypal_order(
    order_code: str,
    request: Request,
    account=Depends(require_account_csrf),
):
    """Authoritative PayPal order initialization when user starts PayPal payment at checkout."""
    validate_order_code(order_code)
    now = request.app.state.auth.now()
    order = account.db.scalar(
        select(SubscriptionOrder).where(
            SubscriptionOrder.order_code == order_code,
            SubscriptionOrder.user_id == account.user.id,
        ).with_for_update()
    )
    if not order:
        raise AuthError(404, "NOT_FOUND", "Đơn hàng không tồn tại.")

    _check_and_expire_order(order, account.db, now, getattr(request.app.state, "paypal", None), reconcile=True)
    plan = get_plan(order.tier)
    if order.status == "success":
        return OrderDto(
            id=order.id,
            order_code=order.order_code,
            tier=order.tier,
            duration_days=order.duration_days,
            amount_usd_cents=order.amount_cents,
            amount_usd_formatted=plan.amount_usd_formatted,
            amount_vnd=order.amount_vnd,
            amount_vnd_formatted=f"{order.amount_vnd:,} VNĐ".replace(",", "."),
            currency=order.currency,
            status=order.status,
            provider=order.provider,
            provider_txn_id=order.provider_txn_id,
            payment_url=order.payment_url,
            created_at=order.created_at,
            completed_at=order.completed_at,
        )

    if order.status in {"failed", "cancelled", "expired"}:
        raise AuthError(409, "ORDER_NOT_PAYABLE", "Đơn hàng không ở trạng thái có thể thanh toán.")

    if order.provider == "paypal_sandbox" and order.payment_url:
        return OrderDto(
            id=order.id,
            order_code=order.order_code,
            tier=order.tier,
            duration_days=order.duration_days,
            amount_usd_cents=order.amount_cents,
            amount_usd_formatted=plan.amount_usd_formatted,
            amount_vnd=order.amount_vnd,
            amount_vnd_formatted=f"{order.amount_vnd:,} VNĐ".replace(",", "."),
            currency=order.currency,
            status=order.status,
            provider=order.provider,
            provider_txn_id=order.provider_txn_id,
            payment_url=order.payment_url,
            created_at=order.created_at,
            completed_at=order.completed_at,
        )

    order.provider = "paypal_sandbox"
    paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None)
    origin = request.headers.get("origin")
    if origin not in request.app.state.auth.settings.auth_allowed_origins:
        raise AuthError(403, "FORBIDDEN", "Invalid checkout origin.")
    return_url = f"{origin}/premium/checkout?order={order.order_code}"
    cancel_url = return_url + "&cancelled=true"

    if paypal and paypal.is_configured():
        try:
            pp_order = paypal.create_order(
                order_code=order.order_code,
                plan_tier=order.tier,
                return_url=return_url,
                cancel_url=cancel_url,
            )
            order.payment_url = pp_order.get("approve_url")
            order.provider_txn_id = pp_order.get("id")
            order.provider_payload = pp_order
        except PaypalError as exc:
            logger.error("Failed to initialize PayPal order: %s", exc)
            raise AuthError(502, "PAYPAL_ERROR", f"Không thể tạo đơn hàng PayPal: {str(exc)}")
    else:
        mock_id = f"MOCK-PP-{uuid4().hex[:12].upper()}"
        order.provider_txn_id = mock_id
        order.payment_url = f"https://www.sandbox.paypal.com/checkoutnow?token={mock_id}"
        order.provider_payload = {"mock": True, "id": mock_id}

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
        amount_vnd_formatted=f"{order.amount_vnd:,} VNĐ".replace(",", "."),
        currency=order.currency,
        status=order.status,
        provider=order.provider,
        provider_txn_id=order.provider_txn_id,
        payment_url=order.payment_url,
        created_at=order.created_at,
        completed_at=order.completed_at,
    )


def _activate_subscription(db, order: SubscriptionOrder, now: datetime) -> UserSubscription:
    """Authoritative idempotent subscription activation / extension."""
    sub = db.scalar(select(UserSubscription).where(UserSubscription.user_id == order.user_id))
    if sub and isinstance(sub, UserSubscription):
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
    return sub


def _check_and_expire_order(order: SubscriptionOrder, db, now: datetime, paypal: PaypalAdapter | None = None, *, reconcile: bool = False) -> bool:
    """Checks a stale pending order. Reconciles if captured on PayPal; otherwise transitions to expired.
    Never grants subscription without verified capture confirmation."""
    stale = order.created_at <= now - ORDER_EXPIRY_TIMEOUT
    if order.status != "pending" or (not stale and not reconcile):
        return False
    real_paypal = (order.provider == "paypal_sandbox" and order.provider_txn_id
                   and not order.provider_txn_id.startswith(("SIM-", "MOCK-")))
    if real_paypal and (paypal is None or not paypal.is_configured()):
        raise AuthError(503, "PAYPAL_UNAVAILABLE", "Chưa thể đối soát đơn PayPal.")

    is_captured = False
    if order.provider == "paypal_sandbox" and paypal and paypal.is_configured() and order.provider_txn_id:
        try:
            pp_order = paypal.get_order_details(order.provider_txn_id)
            if pp_order.get("status") == "COMPLETED" and pp_order.get("id") == order.provider_txn_id:
                is_valid, _ = paypal.verify_capture(
                    pp_order,
                    expected_amount_cents=order.amount_cents,
                    expected_order_code=order.order_code,
                    expected_merchant_id=paypal.merchant_id,
                )
                if is_valid:
                    order.status = "success"
                    order.completed_at = now
                    order.updated_at = now
                    _activate_subscription(db, order, now)
                    is_captured = True
                    logger.info("Stale pending order %s reconciled to success via PayPal verification.", order.order_code)
                else:
                    raise AuthError(503, "PAYPAL_UNAVAILABLE", "PayPal capture chưa thể xác minh.")
        except Exception as exc:
            raise AuthError(503, "PAYPAL_UNAVAILABLE", "Chưa thể đối soát đơn PayPal. Vui lòng thử lại.") from exc

    if not is_captured and stale and order.status == "pending":
        order.status = "expired"
        order.updated_at = now
    db.flush()
    return True


@router.get(
    "/orders",
    operation_id="listSubscriptionOrders",
    response_model=OrderPage,
    responses={**ERRORS},
)
def list_subscription_orders(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=64),
    request: Request = None,
    account=Depends(require_authenticated_user),
):
    """List subscription orders for the current user with pagination, optional status filter, and order_code search."""
    try:
        now = datetime.now(timezone.utc)
        paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None) if (request and hasattr(request, "app")) else None
        # Auto-expire stale pending orders older than ORDER_EXPIRY_TIMEOUT (checking PayPal capture first)
        stale_res = account.db.scalars(
            select(SubscriptionOrder).where(
                SubscriptionOrder.user_id == account.user.id,
                SubscriptionOrder.status == "pending",
                SubscriptionOrder.created_at < now - ORDER_EXPIRY_TIMEOUT,
            ).order_by(SubscriptionOrder.id).with_for_update()
        )
        stale_orders = stale_res.all() if hasattr(stale_res, "all") else list(stale_res or [])
        for st in stale_orders:
            _check_and_expire_order(st, account.db, now, paypal)

        stmt = select(SubscriptionOrder).where(SubscriptionOrder.user_id == account.user.id)
        if isinstance(status, str) and status and status != "all":
            stmt = stmt.where(SubscriptionOrder.status == status)
        if isinstance(q, str) and q.strip():
            clean_q = q.strip()[:64]
            escaped_q = clean_q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(SubscriptionOrder.order_code.ilike(f"%{escaped_q}%"))

        total = account.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        total_pages = max(1, (total + limit - 1) // limit) if total > 0 else 1

        # Stable sort: newest created_at first, tie-break by id desc
        stmt = stmt.order_by(SubscriptionOrder.created_at.desc(), SubscriptionOrder.id.desc())
        offset = (page - 1) * limit
        if offset < total:
            orders_res = account.db.scalars(stmt.offset(offset).limit(limit))
            orders = orders_res.all() if hasattr(orders_res, "all") else list(orders_res or [])
        else:
            orders = []

        result = []
        for o in orders:
            plan = get_plan(o.tier)
            result.append(
                OrderDto(
                    id=o.id,
                    order_code=o.order_code,
                    tier=o.tier,
                    duration_days=o.duration_days,
                    amount_usd_cents=o.amount_cents,
                    amount_usd_formatted=plan.amount_usd_formatted if plan else f"${o.amount_cents / 100:.2f}",
                    amount_vnd=o.amount_vnd,
                    amount_vnd_formatted=f"{o.amount_vnd:,} VNĐ".replace(",", "."),
                    currency=o.currency,
                    status=o.status,
                    provider=o.provider,
                    provider_txn_id=o.provider_txn_id,
                    payment_url=o.payment_url,
                    created_at=o.created_at,
                    completed_at=o.completed_at,
                )
            )
        return OrderPage(
            items=result,
            pagination=Pagination(
                page=page,
                page_size=limit,
                total=total,
                total_pages=total_pages,
            ),
        )
    except Exception as exc:
        logger.error("Failed to list subscription orders for user %s: %s", account.user.id, exc, exc_info=True)
        raise AuthError(500, "INTERNAL_ERROR", "Không thể lấy danh sách đơn hàng.")


@router.get(
    "/orders/successful",
    operation_id="listSuccessfulOrders",
    response_model=list[OrderDto],
    responses={**ERRORS},
)
def list_successful_orders(
    limit: int = Query(default=10, ge=1, le=10),
    account=Depends(require_authenticated_user),
):
    """Retrieve up to 10 most recent successful orders of the authenticated user for receipt summary."""
    try:
        stmt = (
            select(SubscriptionOrder)
            .where(
                SubscriptionOrder.user_id == account.user.id,
                SubscriptionOrder.status == "success",
            )
            .order_by(
                SubscriptionOrder.completed_at.desc().nullslast(),
                SubscriptionOrder.created_at.desc(),
                SubscriptionOrder.id.desc(),
            )
            .limit(limit)
        )
        res = account.db.scalars(stmt)
        orders = res.all() if hasattr(res, "all") else list(res or [])
        result = []
        for o in orders:
            plan = get_plan(o.tier)
            result.append(
                OrderDto(
                    id=o.id,
                    order_code=o.order_code,
                    tier=o.tier,
                    duration_days=o.duration_days,
                    amount_usd_cents=o.amount_cents,
                    amount_usd_formatted=plan.amount_usd_formatted if plan else f"${o.amount_cents / 100:.2f}",
                    amount_vnd=o.amount_vnd,
                    amount_vnd_formatted=f"{o.amount_vnd:,} VNĐ".replace(",", "."),
                    currency=o.currency,
                    status=o.status,
                    provider=o.provider,
                    provider_txn_id=o.provider_txn_id,
                    payment_url=o.payment_url,
                    created_at=o.created_at,
                    completed_at=o.completed_at,
                )
            )
        return result
    except Exception as exc:
        logger.error("Failed to retrieve successful orders for user %s: %s", account.user.id, exc, exc_info=True)
        raise AuthError(500, "INTERNAL_ERROR", "Không thể lấy lịch sử đơn hàng thành công.")


@router.get(
    "/orders/{order_code}",
    response_model=OrderDetailDto,
    operation_id="getSubscriptionOrder",
    responses={**ERRORS, 404: {"model": ErrorResponse}},
)
def get_subscription_order(
    order_code: str,
    request: Request = None,
    account=Depends(require_authenticated_user),
):
    """Retrieve authoritative order status for authenticated user."""
    validate_order_code(order_code)

    admin_role = select(UserRole.user_id).join(Role).where(
        UserRole.user_id == account.user.id, Role.code == "ADMIN"
    ).exists()
    stmt = select(SubscriptionOrder).where(
        SubscriptionOrder.order_code == order_code,
        (SubscriptionOrder.user_id == account.user.id) | admin_role,
    )
    order = account.db.scalar(stmt.with_for_update())
    if not order:
        raise AuthError(404, "NOT_FOUND", "Đơn hàng không tồn tại.")

    now = datetime.now(timezone.utc)
    paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None) if (request and hasattr(request, "app")) else None
    _check_and_expire_order(order, account.db, now, paypal, reconcile=True)

    plan = get_plan(order.tier)
    return OrderDetailDto(
        owner_username=account.db.get(User, order.user_id).username,
        id=order.id,
        order_code=order.order_code,
        tier=order.tier,
        duration_days=order.duration_days,
        amount_usd_cents=order.amount_cents,
        amount_usd_formatted=plan.amount_usd_formatted,
        amount_vnd=order.amount_vnd,
        amount_vnd_formatted=f"{order.amount_vnd:,} VNĐ".replace(",", "."),
        currency=order.currency,
        status=order.status,
        provider=order.provider,
        provider_txn_id=order.provider_txn_id,
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
    validate_order_code(order_code)

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
        ).with_for_update()
    )
    if not order:
        raise AuthError(404, "NOT_FOUND", "Đơn hàng không tồn tại.")

    plan = get_plan(order.tier)

    _check_and_expire_order(order, account.db, now, getattr(request.app.state, "paypal", None))

    # Idempotent response if order is already resolved
    if order.status == "success":
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

    if order.status in {"failed", "cancelled", "expired"}:
        raise AuthError(409, "ORDER_NOT_PAYABLE", "Đơn hàng không ở trạng thái có thể thanh toán.")

    if payload.action == "pay_success":
        # Guard: if order already has an active real PayPal transaction, ensure it was not already captured
        if order.provider == "paypal_sandbox" and order.provider_txn_id and not order.provider_txn_id.startswith("SIM-") and not order.provider_txn_id.startswith("MOCK-"):
            paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None)
            if paypal and paypal.is_configured():
                try:
                    pp_check = paypal.get_order_details(order.provider_txn_id)
                    if pp_check.get("status") != "VOIDED":
                        raise AuthError(409, "ORDER_ALREADY_CAPTURED", "Đơn hàng đã được thanh toán trên PayPal.")
                except PaypalError as exc:
                    raise AuthError(503, "PAYPAL_UNAVAILABLE", "Chưa thể đối soát đơn PayPal.") from exc
            else:
                raise AuthError(503, "PAYPAL_NOT_CONFIGURED", "Chưa thể đối soát đơn PayPal.")

        order.status = "success"
        order.completed_at = now
        order.provider = "sandbox_simulated"
        order.provider_txn_id = f"SIM-CARD-{uuid4().hex[:12].upper()}"
        order.provider_response_code = "SUCCESS"
        order.payment_url = None
        order.updated_at = now

        _activate_subscription(account.db, order, now)

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


@router.post(
    "/orders/{order_code}/capture",
    response_model=OrderDto,
    operation_id="captureSubscriptionOrder",
    responses={**ERRORS, 404: {"model": ErrorResponse}},
    openapi_extra=CSRF_HEADER,
)
def capture_subscription_order(
    order_code: str,
    request: Request,
    payload: CaptureOrderInput | None = None,
    account=Depends(require_account_csrf),
):
    validate_order_code(order_code)

    now = request.app.state.auth.now()
    order = account.db.scalar(
        select(SubscriptionOrder).where(
            SubscriptionOrder.order_code == order_code,
            SubscriptionOrder.user_id == account.user.id,
        ).with_for_update()
    )
    if not order:
        raise AuthError(404, "NOT_FOUND", "Đơn hàng không tồn tại.")

    plan = get_plan(order.tier)

    _check_and_expire_order(order, account.db, now, getattr(request.app.state, "paypal", None))

    # Idempotent response if order is already resolved
    if order.status == "success":
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

    if order.status in {"failed", "cancelled", "expired"}:
        raise AuthError(409, "ORDER_NOT_PAYABLE", "Đơn hàng không ở trạng thái có thể thanh toán.")

    auth_runtime = getattr(request.app.state, "auth", None)
    auth_env = getattr(auth_runtime.settings, "auth_environment", "production") if auth_runtime and hasattr(auth_runtime, "settings") else "production"

    sandbox_enabled = getattr(getattr(request.app.state, "premium", None), "premium_sandbox_enabled", False)
    paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None)

    if order.provider in ("paypal_sandbox", "unselected"):
        order.provider = "paypal_sandbox"
        pp_order_id = (payload.paypal_order_id if payload else None) or order.provider_txn_id
        if not pp_order_id:
            raise AuthError(400, "MISSING_PAYPAL_ID", "Thiếu mã định danh giao dịch PayPal (PayPal Order ID).")

        if paypal and paypal.is_configured():
            if not paypal.merchant_id:
                raise AuthError(503, "PAYPAL_NOT_CONFIGURED", "Thiếu cấu hình merchant PayPal Sandbox.")
            if pp_order_id != order.provider_txn_id:
                raise AuthError(400, "PAYPAL_ORDER_MISMATCH", "Mã PayPal không khớp đơn hàng.")
            try:
                capture_res = paypal.capture_order(pp_order_id, idempotency_key=order.order_code)
            except PaypalError as exc:
                logger.error("PayPal capture API call failed for order %s: %s", order.order_code, exc)
                order.status = "failed"
                order.completed_at = now
                order.updated_at = now
                account.db.flush()
                raise AuthError(400, "CAPTURE_FAILED", f"Lỗi capture từ PayPal: {str(exc)}")

            if capture_res.get("id") != pp_order_id:
                raise AuthError(400, "PAYPAL_ORDER_MISMATCH", "Mã phản hồi PayPal không khớp đơn hàng.")
            is_valid, reason = paypal.verify_capture(
                capture_res,
                expected_amount_cents=order.amount_cents,
                expected_order_code=order.order_code,
            )
            if not is_valid:
                logger.warning("PayPal capture verification failed for %s: %s", order.order_code, reason)
                order.status = "failed"
                order.provider_response_code = reason
                order.provider_payload = capture_res
                order.completed_at = now
                order.updated_at = now
                account.db.flush()
                raise AuthError(400, "CAPTURE_INVALID", f"Xác thực thanh toán thất bại: {reason}")

            cap_id = pp_order_id
            try:
                cap_id = capture_res["purchase_units"][0]["payments"]["captures"][0]["id"]
            except Exception:
                pass

            order.provider_txn_id = cap_id
            order.provider_payload = capture_res
            order.provider_response_code = "COMPLETED"
        else:
            # Production boundary guard: Never allow mock simulation fallback in production environment
            if auth_env == "production":
                raise AuthError(503, "PAYPAL_NOT_CONFIGURED", "Cổng thanh toán PayPal chưa được cấu hình cho môi trường production.")
            if not sandbox_enabled:
                raise AuthError(403, "FORBIDDEN", "Mô phỏng thanh toán bị vô hiệu hóa.")
            # Mock sandbox simulation mode
            if payload and payload.mock_fail:
                order.status = "failed"
                order.completed_at = now
                order.updated_at = now
                account.db.flush()
                raise AuthError(400, "PAYMENT_FAILED", "Mô phỏng thanh toán PayPal thất bại.")
            order.provider_txn_id = f"SIM-PP-{uuid4().hex[:12].upper()}"
            order.provider_payload = {"mock": True, "captured": True}
            order.provider_response_code = "COMPLETED"

    elif order.provider == "sandbox_simulated":
        # Production boundary guard: Never allow simulated capture in production environment
        if auth_env == "production" or not sandbox_enabled:
            raise AuthError(403, "FORBIDDEN", "Phương thức thanh toán mô phỏng bị vô hiệu hóa trên môi trường production.")
        order.provider_txn_id = f"SIM-CARD-{uuid4().hex[:12].upper()}"
        order.provider_response_code = "SUCCESS"
    else:
        raise AuthError(400, "INVALID_PROVIDER", f"Không hỗ trợ capture cho nhà cung cấp '{order.provider}'.")

    # Authoritative activation / extension
    order.status = "success"
    order.completed_at = now
    order.updated_at = now

    _activate_subscription(account.db, order, now)
    account.db.flush()

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


@router.post("/paypal/webhook", operation_id="handlePaypalWebhook")
async def handle_paypal_webhook(request: Request):
    """Handle PayPal webhook events (e.g. PAYMENT.CAPTURE.COMPLETED) with strict fail-closed security."""
    now = request.app.state.auth.now()
    paypal: PaypalAdapter | None = getattr(request.app.state, "paypal", None)
    raw_body = await request.body()
    headers = dict(request.headers)

    # 1. Fail-closed: missing adapter, missing credentials, or missing webhook_id must reject
    if not paypal or not paypal.is_configured() or not paypal.webhook_id:
        logger.warning("PayPal webhook rejected: adapter or webhook_id is not configured (fail-closed).")
        return Response(
            content=json.dumps({"status": "rejected", "reason": "webhook_not_configured"}),
            status_code=503,
            media_type="application/json",
        )

    # 2. Fail-closed: invalid signature must reject immediately
    is_valid_sig = paypal.verify_webhook_signature(headers, raw_body)
    if not is_valid_sig:
        logger.warning("PayPal webhook rejected: signature verification failed (fail-closed).")
        return Response(
            content=json.dumps({"status": "rejected", "reason": "invalid_signature"}),
            status_code=400,
            media_type="application/json",
        )

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return Response(
            content=json.dumps({"status": "error", "reason": "invalid_json"}),
            status_code=400,
            media_type="application/json",
        )

    event_type = event.get("event_type")
    resource = event.get("resource", {})

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        order_code = resource.get("custom_id") or resource.get("invoice_id")
        capture_id = resource.get("id")
        paypal_order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        if not capture_id or not (order_code or paypal_order_id):
            return Response(status_code=400)

        with request.app.state.auth_session_factory() as db, db.begin():
            stmt = select(SubscriptionOrder)
            if order_code:
                stmt = stmt.where(SubscriptionOrder.order_code == order_code)
            else:
                stmt = stmt.where(SubscriptionOrder.provider_txn_id.in_([paypal_order_id, capture_id]))
            # Session-based checkout also locks the account before the order.
            owner = stmt.with_only_columns(SubscriptionOrder.user_id).scalar_subquery()
            db.execute(select(User.id).where(User.id == owner).with_for_update())
            order = db.scalar(stmt.with_for_update())
            if not order:
                logger.warning("PayPal webhook received for unknown order: %s / %s", order_code, capture_id)
                return Response(
                    content=json.dumps({"status": "ignored", "reason": "order_not_found"}),
                    status_code=200,
                    media_type="application/json",
                )

            # Strict provider check
            if order.provider != "paypal_sandbox":
                logger.warning("PayPal webhook rejected: order %s provider is '%s', expected 'paypal_sandbox'.", order.order_code, order.provider)
                return Response(
                    content=json.dumps({"status": "rejected", "reason": "invalid_provider"}),
                    status_code=400,
                    media_type="application/json",
                )

            # Idempotency check: if order is already successful, do not re-activate
            if order.status == "success":
                logger.info("PayPal webhook idempotent skip: order %s already marked success.", order.order_code)
                return Response(
                    content=json.dumps({"status": "already_processed", "order_code": order.order_code}),
                    status_code=200,
                    media_type="application/json",
                )

            if not order.provider_txn_id or (paypal_order_id and paypal_order_id != order.provider_txn_id):
                return Response(status_code=400)
            try:
                capture_payload = paypal.get_order_details(order.provider_txn_id)
            except PaypalError:
                return Response(status_code=503)
            if capture_payload.get("id") != order.provider_txn_id:
                return Response(status_code=400)
            is_valid_capture, reason = paypal.verify_capture(
                capture_payload, order.amount_cents, order.order_code, paypal.merchant_id,
            )
            if is_valid_capture and capture_payload["purchase_units"][0]["payments"]["captures"][0]["id"] != capture_id:
                return Response(status_code=400)
            if not is_valid_capture:
                logger.warning("PayPal webhook capture verification failed for order %s: %s", order.order_code, reason)
                return Response(
                    content=json.dumps({"status": "rejected", "reason": reason}),
                    status_code=400,
                    media_type="application/json",
                )

            # Reconcile order to success (even if callback was delayed and order was pending or expired)
            order.status = "success"
            order.completed_at = now
            order.provider_txn_id = capture_id or resource.get("id")
            order.provider_payload = capture_payload
            order.provider_response_code = "COMPLETED"
            order.updated_at = now

            _activate_subscription(db, order, now)
            logger.info("PayPal webhook successfully completed and activated subscription for order %s.", order.order_code)

        return Response(
            content=json.dumps({"status": "success", "order_code": order_code}),
            status_code=200,
            media_type="application/json",
        )

    return Response(
        content=json.dumps({"status": "received", "event_type": event_type}),
        status_code=200,
        media_type="application/json",
    )

