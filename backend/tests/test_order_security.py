"""Unit tests for Order Code validation, IDOR authorization, idempotency, and production guards (Part D)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models import SubscriptionOrder
from app.premium import (
    CaptureOrderInput,
    SimulateOrderInput,
    capture_subscription_order,
    get_subscription_order,
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
