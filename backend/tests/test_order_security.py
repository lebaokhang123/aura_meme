"""Unit tests for Order Code validation, IDOR authorization, idempotency, and production guards (Part D & E)."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models import SubscriptionOrder, UserSubscription
from app.premium import (
    CaptureOrderInput,
    CreateOrderInput,
    ORDER_EXPIRY_TIMEOUT,
    OrderPage,
    SimulateOrderInput,
    capture_subscription_order,
    create_subscription_order,
    get_subscription_order,
    handle_paypal_webhook,
    list_subscription_orders,
    simulate_subscription_order,
    validate_order_code,
)
from app.security import AuthError


def test_order_code_format_validation():
    """Verify strict validation of order_code format, length, and allowed characters."""
    # Valid formats
    valid_codes = [
        "AM-PLUS-1795330000-ABCD1234",
        "AM-PRIME-1795330000-0123456789AB",
        "AM-PLUS-123456789-A1B2",
    ]
    for code in valid_codes:
        assert validate_order_code(code) == code

    # Invalid formats
    invalid_codes = [
        "",
        None,
        "   ",
        "AM-PLUS",
        "AM-PLUS-123",
        "am-plus-1795330000-abcd1234",  # lowercase
        "AM-VIP-1795330000-ABCD1234",    # invalid tier
        "AM-PLUS-1795330000-abcd-1234",  # invalid chars
        "AM-PLUS-1795330000-ABCD1234'; DROP TABLE subscription_orders; --",  # SQL injection
        "<script>alert(1)</script>",     # XSS
        "A" * 65,                        # too long
        "AM-PLUS-1795330000000000-ABCD", # timestamp too long
    ]
    for code in invalid_codes:
        with pytest.raises(AuthError) as exc_info:
            validate_order_code(code)
        assert exc_info.value.status == 422
        assert exc_info.value.code == "INVALID_ORDER_CODE"


def test_idor_order_authorization():
    """Verify User B cannot access, simulate, or capture User A's order."""
    user_a_id = uuid4()
    user_b_id = uuid4()
    order_code = "AM-PLUS-1795330000-USERA123"

    order = SubscriptionOrder(
        id=uuid4(),
        order_code=order_code,
        user_id=user_a_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        created_at=datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc),
    )

    # User B account
    account_b = MagicMock()
    account_b.user.id = user_b_id
    account_b.user.roles = ["USER"]
    account_b.db = MagicMock()
    # DB query filters by user_id, so returns None for User B
    account_b.db.scalar.return_value = None

    # User B calls GET /orders/{order_code}
    with pytest.raises(AuthError) as exc:
        get_subscription_order(order_code, account=account_b)
    assert exc.value.status == 404
    assert exc.value.code == "NOT_FOUND"

    # User B calls POST /orders/{order_code}/simulate
    mock_request = MagicMock()
    mock_request.app.state.auth.settings.auth_environment = "development"
    mock_request.app.state.premium.premium_sandbox_enabled = True
    with pytest.raises(AuthError) as exc:
        simulate_subscription_order(
            order_code=order_code,
            payload=SimulateOrderInput(action="pay_success"),
            request=mock_request,
            account=account_b,
        )
    assert exc.value.status == 404

    # User B calls POST /orders/{order_code}/capture
    mock_request.app.state.auth.now.return_value = datetime.now(timezone.utc)
    with pytest.raises(AuthError) as exc:
        capture_subscription_order(
            order_code=order_code,
            request=mock_request,
            payload=CaptureOrderInput(),
            account=account_b,
        )
    assert exc.value.status == 404

    # Admin user CAN read User A's order
    admin_account = MagicMock()
    admin_account.user.id = uuid4()
    admin_account.user.roles = ["ADMIN"]
    admin_account.db = MagicMock()
    admin_account.db.scalar.return_value = order

    admin_dto = get_subscription_order(order_code, account=admin_account)
    assert admin_dto.order_code == order_code
    assert admin_dto.tier == "plus"


def test_idempotency_prevent_double_capture():
    """Verify orders already marked 'success' return existing DTO without duplicate execution."""
    user_id = uuid4()
    order_code = "AM-PRIME-1795330000-PRIME123"
    completed_time = datetime(2026, 11, 22, 10, 5, 0, tzinfo=timezone.utc)

    order = SubscriptionOrder(
        id=uuid4(),
        order_code=order_code,
        user_id=user_id,
        tier="prime",
        duration_days=365,
        amount_cents=5000,
        amount_vnd=1250000,
        currency="USD",
        status="success",
        provider="paypal_sandbox",
        completed_at=completed_time,
        created_at=datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc),
    )

    account = MagicMock()
    account.user.id = user_id
    account.user.roles = ["USER"]
    account.db = MagicMock()
    account.db.scalar.return_value = order

    mock_request = MagicMock()
    mock_request.app.state.auth.settings.auth_environment = "development"
    mock_request.app.state.premium.premium_sandbox_enabled = True
    mock_request.app.state.auth.now.return_value = datetime.now(timezone.utc)

    # Calling simulate on already successful order
    dto_sim = simulate_subscription_order(
        order_code=order_code,
        payload=SimulateOrderInput(action="pay_success"),
        request=mock_request,
        account=account,
    )
    assert dto_sim.status == "success"
    assert dto_sim.completed_at == completed_time

    # Calling capture on already successful order
    dto_cap = capture_subscription_order(
        order_code=order_code,
        request=mock_request,
        payload=CaptureOrderInput(),
        account=account,
    )
    assert dto_cap.status == "success"
    assert dto_cap.completed_at == completed_time
    # account.db.add should NOT be called for updating subscription
    account.db.add.assert_not_called()


def test_finalized_orders_not_payable():
    """Verify orders marked 'failed', 'cancelled', or 'expired' reject capture/simulate with 409 ORDER_NOT_PAYABLE."""
    user_id = uuid4()
    order_code = "AM-PLUS-1795330000-FINISH12"

    for terminal_status in ["failed", "cancelled", "expired"]:
        order = SubscriptionOrder(
            id=uuid4(),
            order_code=order_code,
            user_id=user_id,
            tier="plus",
            duration_days=30,
            amount_cents=500,
            amount_vnd=130000,
            currency="USD",
            status=terminal_status,
            provider="paypal_sandbox",
            created_at=datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc),
        )

        account = MagicMock()
        account.user.id = user_id
        account.user.roles = ["USER"]
        account.db = MagicMock()
        account.db.scalar.return_value = order

        mock_request = MagicMock()
        mock_request.app.state.auth.settings.auth_environment = "development"
        mock_request.app.state.premium.premium_sandbox_enabled = True
        mock_request.app.state.auth.now.return_value = datetime.now(timezone.utc)

        with pytest.raises(AuthError) as exc_sim:
            simulate_subscription_order(
                order_code=order_code,
                payload=SimulateOrderInput(action="pay_success"),
                request=mock_request,
                account=account,
            )
        assert exc_sim.value.status == 409
        assert exc_sim.value.code == "ORDER_NOT_PAYABLE"

        with pytest.raises(AuthError) as exc_cap:
            capture_subscription_order(
                order_code=order_code,
                request=mock_request,
                payload=CaptureOrderInput(),
                account=account,
            )
        assert exc_cap.value.status == 409
        assert exc_cap.value.code == "ORDER_NOT_PAYABLE"


def test_production_boundary_guard():
    """Verify production environment strictly forbids mock simulation and unconfigured PayPal captures."""
    user_id = uuid4()
    order_code = "AM-PLUS-1795330000-PRODGUARD"

    order = SubscriptionOrder(
        id=uuid4(),
        order_code=order_code,
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        created_at=datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc),
    )

    account = MagicMock()
    account.user.id = user_id
    account.user.roles = ["USER"]
    account.db = MagicMock()
    account.db.scalar.return_value = order

    mock_request = MagicMock()
    mock_request.app.state.auth.settings.auth_environment = "production"
    mock_request.app.state.premium.premium_sandbox_enabled = False
    mock_request.app.state.auth.now.return_value = datetime.now(timezone.utc)
    mock_request.app.state.paypal = None

    # Direct simulate call raises 403 in production
    with pytest.raises(AuthError) as exc_sim:
        simulate_subscription_order(
            order_code=order_code,
            payload=SimulateOrderInput(action="pay_success"),
            request=mock_request,
            account=account,
        )
    assert exc_sim.value.status == 403
    assert exc_sim.value.code == "FORBIDDEN"

    # Missing paypal_order_id in production raises 400
    with pytest.raises(AuthError) as exc_missing:
        capture_subscription_order(
            order_code=order_code,
            request=mock_request,
            payload=CaptureOrderInput(),
            account=account,
        )
    assert exc_missing.value.status == 400
    assert exc_missing.value.code == "MISSING_PAYPAL_ID"

    # Capture call without paypal configured raises 503 in production
    with pytest.raises(AuthError) as exc_cap:
        capture_subscription_order(
            order_code=order_code,
            request=mock_request,
            payload=CaptureOrderInput(paypal_order_id="PP-123456"),
            account=account,
        )
    assert exc_cap.value.status == 503
    assert exc_cap.value.code == "PAYPAL_NOT_CONFIGURED"


def test_active_pending_order_reuse_for_same_intent():
    """Verify create_subscription_order reuses recent pending order (<15 min) for same tier and provider."""
    user_id = uuid4()
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    recent_pending = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330000-EXISTING1",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        created_at=now - timedelta(minutes=5),
    )

    account = MagicMock()
    account.user.id = user_id
    account.db = MagicMock()
    account.db.scalar.return_value = recent_pending

    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now
    mock_request.app.state.premium = None
    mock_request.app.state.vnpay = None

    payload = CreateOrderInput(plan_tier="plus", provider="paypal_sandbox")
    dto = create_subscription_order(payload=payload, request=mock_request, account=account)

    assert dto.order_code == "AM-PLUS-1795330000-EXISTING1"
    assert dto.status == "pending"
    # No new order inserted to db
    account.db.add.assert_not_called()


def test_pending_order_auto_expiration_after_1_hour():
    """Verify pending orders older than 1 hour automatically transition to 'expired'."""
    user_id = uuid4()
    order_code = "AM-PLUS-1795330000-STALEORDER"
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)

    order = SubscriptionOrder(
        id=uuid4(),
        order_code=order_code,
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        created_at=old_time,
    )

    account = MagicMock()
    account.user.id = user_id
    account.user.roles = ["USER"]
    account.db = MagicMock()
    account.db.scalar.return_value = order

    dto = get_subscription_order(order_code, account=account)
    assert dto.status == "expired"
    assert order.status == "expired"
    account.db.flush.assert_called_once()


def test_list_orders_pagination_and_filter():
    """Verify list_subscription_orders paginates and filters correctly."""
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    # 15 orders
    mock_orders = [
        SubscriptionOrder(
            id=uuid4(),
            order_code=f"AM-PLUS-1795330000-ORD{i:02d}",
            user_id=user_id,
            tier="plus" if i % 2 == 0 else "prime",
            duration_days=30,
            amount_cents=500,
            amount_vnd=130000,
            currency="USD",
            status="success" if i < 10 else "pending",
            provider="paypal_sandbox",
            created_at=now - timedelta(minutes=i),
        )
        for i in range(15)
    ]

    account = MagicMock()
    account.user.id = user_id
    account.user.roles = ["USER"]
    account.db = MagicMock()

    # When querying total count, return 15
    # When querying page items (limit=10), return first 10
    account.db.scalar.return_value = 15
    account.db.scalars.return_value = mock_orders[:10]

    result = list_subscription_orders(page=1, limit=10, account=account)
    assert isinstance(result, OrderPage)
    assert len(result.items) == 10
    assert result.pagination.total == 15
    assert result.pagination.page == 1
    assert result.pagination.page_size == 10
    assert result.pagination.total_pages == 2


def test_webhook_duplicate_idempotent():
    """Verify PayPal webhook PAYMENT.CAPTURE.COMPLETED does not double-extend subscription."""
    import asyncio
    user_id = uuid4()
    order_id = uuid4()
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    order_code = "AM-PLUS-1795330000-WEBHOOK1"

    order = SubscriptionOrder(
        id=order_id,
        order_code=order_code,
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="success",  # Already succeeded
        provider="paypal_sandbox",
        completed_at=now,
        created_at=now - timedelta(minutes=10),
    )

    mock_db = MagicMock()
    mock_db.scalar.return_value = order

    class MockContextManager:
        def __enter__(self):
            return mock_db
        def __exit__(self, *args):
            pass

    mock_factory = MagicMock(return_value=MockContextManager())

    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now
    mock_request.app.state.paypal = None
    mock_request.app.state.auth_session_factory = mock_factory
    mock_request.headers = {}

    webhook_payload = json.dumps({
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE-12345",
            "custom_id": order_code,
        }
    }).encode("utf-8")

    async def get_body():
        return webhook_payload

    mock_request.body = get_body

    res = asyncio.run(handle_paypal_webhook(mock_request))
    assert res == {"status": "received"}
    # Because order was already "success", sub was NOT modified/added
    mock_db.add.assert_not_called()

