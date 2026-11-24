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

    admin_account.db.get.return_value.username = "order_owner"
    admin_dto = get_subscription_order(order_code, account=admin_account)
    assert admin_dto.order_code == order_code
    assert admin_dto.tier == "plus"
    assert admin_dto.owner_username == "order_owner"


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
        created_at=datetime.now(timezone.utc),
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

    mock_request.headers = {"origin": "http://127.0.0.1:5189"}
    mock_request.app.state.auth.settings.auth_allowed_origins = ["http://127.0.0.1:5189"]
    paypal = mock_request.app.state.paypal
    paypal.mode = "sandbox"
    paypal.merchant_id = "AURAMEME_MERCHANT"
    paypal.create_order.return_value = {
        "id": "PP-EXISTING",
        "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=PP-EXISTING",
    }
    payload = CreateOrderInput(plan_tier="plus", provider="paypal_sandbox")
    dto = create_subscription_order(payload=payload, request=mock_request, account=account)

    assert dto.order_code == "AM-PLUS-1795330000-EXISTING1"
    assert dto.status == "pending"
    assert dto.provider_txn_id == "PP-EXISTING"
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

    account.db.get.return_value.username = "order_owner"
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


def test_list_orders_search_and_sort():
    """Verify list_subscription_orders handles q search parameter and stable newest-first sort order."""
    user_id = uuid4()
    now = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)
    mock_orders = [
        SubscriptionOrder(
            id=uuid4(),
            order_code=f"AM-PRIME-1795330000-NEW{i:02d}",
            user_id=user_id,
            tier="prime",
            duration_days=365,
            amount_cents=5000,
            amount_vnd=1250000,
            currency="USD",
            status="success",
            provider="paypal_sandbox",
            created_at=now - timedelta(minutes=i),
        )
        for i in range(15)
    ]
    # mock_orders is ordered newest first: index 0 is newest (now), index 14 is oldest (now - 14m)
    account = MagicMock()
    account.user.id = user_id
    account.user.roles = ["USER"]
    account.db = MagicMock()

    # Test page 1 with search q="NEW"
    account.db.scalar.return_value = 15
    account.db.scalars.return_value = mock_orders[:10]
    p1 = list_subscription_orders(page=1, limit=10, q="NEW", account=account)
    assert len(p1.items) == 10
    assert p1.pagination.page == 1
    assert p1.pagination.total == 15
    assert p1.pagination.total_pages == 2
    assert p1.items[0].order_code == "AM-PRIME-1795330000-NEW00"
    assert p1.items[9].order_code == "AM-PRIME-1795330000-NEW09"

    # Test page 2 (older 5 orders)
    account.db.scalar.return_value = 15
    account.db.scalars.return_value = mock_orders[10:15]
    p2 = list_subscription_orders(page=2, limit=10, q="NEW", account=account)
    assert len(p2.items) == 5
    assert p2.pagination.page == 2
    assert p2.items[0].order_code == "AM-PRIME-1795330000-NEW10"
    assert p2.items[4].order_code == "AM-PRIME-1795330000-NEW14"

    # Ensure no overlap between page 1 and page 2
    p1_codes = {o.order_code for o in p1.items}
    p2_codes = {o.order_code for o in p2.items}
    assert len(p1_codes.intersection(p2_codes)) == 0
    assert len(p1_codes.union(p2_codes)) == 15


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

    mock_paypal = MagicMock()
    mock_paypal.is_configured.return_value = True
    mock_paypal.webhook_id = "WH-123456"
    mock_paypal.verify_webhook_signature.return_value = True

    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now
    mock_request.app.state.paypal = mock_paypal
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
    assert res.status_code == 200
    res_json = json.loads(res.body.decode())
    assert res_json["status"] == "already_processed"
    # Because order was already "success", sub was NOT modified/added
    mock_db.add.assert_not_called()


def test_webhook_fail_closed_unconfigured():
    """Verify PayPal webhook rejects with 503 if adapter or webhook_id is not configured."""
    import asyncio

    # Case A: paypal adapter is None
    req1 = MagicMock()
    req1.app.state.paypal = None
    req1.body = lambda: asyncio.sleep(0, result=b"{}")
    req1.headers = {}
    res1 = asyncio.run(handle_paypal_webhook(req1))
    assert res1.status_code == 503
    assert json.loads(res1.body.decode())["reason"] == "webhook_not_configured"

    # Case B: paypal adapter has no webhook_id
    mock_paypal = MagicMock()
    mock_paypal.is_configured.return_value = True
    mock_paypal.webhook_id = None
    req2 = MagicMock()
    req2.app.state.paypal = mock_paypal
    req2.body = lambda: asyncio.sleep(0, result=b"{}")
    req2.headers = {}
    res2 = asyncio.run(handle_paypal_webhook(req2))
    assert res2.status_code == 503
    assert json.loads(res2.body.decode())["reason"] == "webhook_not_configured"


def test_webhook_fail_closed_invalid_signature():
    """Verify PayPal webhook rejects with 400 if signature verification fails."""
    import asyncio

    mock_paypal = MagicMock()
    mock_paypal.is_configured.return_value = True
    mock_paypal.webhook_id = "WH-123456"
    mock_paypal.verify_webhook_signature.return_value = False

    req = MagicMock()
    req.app.state.paypal = mock_paypal
    req.body = lambda: asyncio.sleep(0, result=b"{}")
    req.headers = {"paypal-transmission-sig": "forged_sig"}

    res = asyncio.run(handle_paypal_webhook(req))
    assert res.status_code == 400
    assert json.loads(res.body.decode())["reason"] == "invalid_signature"


def test_webhook_verification_mismatches_rejected():
    """Verify webhook rejects mismatched currency, amount, merchant, or provider."""
    import asyncio
    user_id = uuid4()
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    order_code = "AM-PLUS-1795330000-VERIF1"

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
        created_at=now - timedelta(minutes=5),
    )

    mock_db = MagicMock()
    mock_db.scalar.return_value = order

    class MockContextManager:
        def __enter__(self):
            return mock_db
        def __exit__(self, *args):
            pass

    mock_paypal = MagicMock()
    mock_paypal.is_configured.return_value = True
    mock_paypal.webhook_id = "WH-123456"
    mock_paypal.verify_webhook_signature.return_value = True
    mock_paypal.merchant_id = "AURAMEME_MERCHANT"
    order.provider_txn_id = "PP-order-mismatch"
    mock_paypal.get_order_details.return_value = {"id": order.provider_txn_id}

    # Mismatch 1: Amount mismatch (1000 cents instead of 500)
    mock_paypal.verify_capture.return_value = (False, "Amount mismatch: expected 500 cents, got 1000 cents.")
    req = MagicMock()
    req.app.state.auth.now.return_value = now
    req.app.state.paypal = mock_paypal
    req.app.state.auth_session_factory = MagicMock(return_value=MockContextManager())
    req.headers = {}

    payload = json.dumps({
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAP-MISMATCH",
            "custom_id": order_code,
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": "10.00"},
        }
    }).encode("utf-8")
    req.body = lambda: asyncio.sleep(0, result=payload)

    res = asyncio.run(handle_paypal_webhook(req))
    assert res.status_code == 400
    assert "Amount mismatch" in json.loads(res.body.decode())["reason"]
    # Subscription was NOT granted
    mock_db.add.assert_not_called()

    # Mismatch 2: Provider mismatch (order was created with vnpay_sandbox, not paypal_sandbox)
    order.provider = "vnpay_sandbox"
    res_prov = asyncio.run(handle_paypal_webhook(req))
    assert res_prov.status_code == 400
    assert json.loads(res_prov.body.decode())["reason"] == "invalid_provider"
    mock_db.add.assert_not_called()


def test_webhook_delayed_callback_reconciles_expired_order():
    """Verify delayed callback for an order marked 'expired' successfully reconciles to 'success' upon verified capture."""
    import asyncio
    user_id = uuid4()
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    order_code = "AM-PRIME-1795330000-DELAYED"

    order = SubscriptionOrder(
        id=uuid4(),
        order_code=order_code,
        user_id=user_id,
        tier="prime",
        duration_days=365,
        amount_cents=5000,
        amount_vnd=1250000,
        currency="USD",
        status="expired",  # Had transitioned to expired because callback was delayed > 1 hour
        provider="paypal_sandbox",
        created_at=now - timedelta(hours=2),
    )

    mock_db = MagicMock()
    mock_db.scalar.side_effect = [order, None]  # 1st call for order, 2nd call for existing subscription (None)

    class MockContextManager:
        def __enter__(self):
            return mock_db
        def __exit__(self, *args):
            pass

    mock_paypal = MagicMock()
    mock_paypal.is_configured.return_value = True
    mock_paypal.webhook_id = "WH-123456"
    mock_paypal.verify_webhook_signature.return_value = True
    mock_paypal.merchant_id = "AURAMEME_MERCHANT"
    order.provider_txn_id = "PP-order-delayed"
    mock_paypal.get_order_details.return_value = {
        "id": order.provider_txn_id,
        "purchase_units": [{"payments": {"captures": [{"id": "CAP-DELAYED-123"}]}}],
    }
    mock_paypal.verify_capture.return_value = (True, "Capture verified successfully.")

    req = MagicMock()
    req.app.state.auth.now.return_value = now
    req.app.state.paypal = mock_paypal
    req.app.state.auth_session_factory = MagicMock(return_value=MockContextManager())
    req.headers = {}

    payload = json.dumps({
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAP-DELAYED-123",
            "custom_id": order_code,
        }
    }).encode("utf-8")
    req.body = lambda: asyncio.sleep(0, result=payload)

    res = asyncio.run(handle_paypal_webhook(req))
    assert res.status_code == 200
    assert json.loads(res.body.decode())["status"] == "success"
    # Order was reconciled to success
    assert order.status == "success"
    # Subscription was granted
    mock_db.add.assert_called_once()


def test_pending_order_expiry_checks_paypal_capture_first():
    """Verify pending order > 1h does not expire if PayPal capture is verified; expires if not captured."""
    user_id = uuid4()
    now = datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    old_time = now - timedelta(hours=2)

    # Sub-case 1: Stale order WAS captured on PayPal -> Reconciled to success, NOT expired!
    captured_order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330000-CAPTURED1",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        provider_txn_id="PP-ORD-CAPTURED",
        created_at=old_time,
    )

    mock_db1 = MagicMock()
    mock_db1.scalar.side_effect = [captured_order, None]

    account1 = MagicMock()
    account1.user.id = user_id
    account1.user.roles = ["USER"]
    account1.db = mock_db1

    mock_paypal = MagicMock()
    mock_paypal.is_configured.return_value = True
    mock_paypal.merchant_id = "AURAMEME_MERCHANT"
    mock_paypal.mode = "sandbox"
    mock_paypal.get_order_details.return_value = {
        "id": "PP-ORD-CAPTURED",
        "status": "COMPLETED",
        "purchase_units": [{"payments": {"captures": [{"id": "PP-CAPTURED"}]}}],
    }
    mock_paypal.verify_capture.return_value = (True, "Capture verified successfully.")

    req1 = MagicMock()
    req1.app.state.paypal = mock_paypal

    account1.db.get.return_value.username = "order_owner"
    dto1 = get_subscription_order("AM-PLUS-1795330000-CAPTURED1", request=req1, account=account1)
    assert dto1.status == "success"
    assert captured_order.status == "success"

    # Sub-case 2: Stale order was NOT captured on PayPal (e.g. status CREATED/ABANDONED) -> Transitions to expired!
    uncaptured_order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330000-ABANDONED",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        provider_txn_id="PP-ORD-ABANDONED",
        created_at=old_time,
    )

    mock_db2 = MagicMock()
    mock_db2.scalar.return_value = uncaptured_order

    account2 = MagicMock()
    account2.user.id = user_id
    account2.user.roles = ["USER"]
    account2.db = mock_db2

    mock_paypal.get_order_details.return_value = {
        "id": "PP-ORD-ABANDONED",
        "status": "CREATED",
    }

    account2.db.get.return_value.username = "order_owner"
    dto2 = get_subscription_order("AM-PLUS-1795330000-ABANDONED", request=req1, account=account2)
    assert dto2.status == "expired"
    assert uncaptured_order.status == "expired"


def test_production_blocks_simulated_order_creation_and_capture():
    """Verify that all simulated and mock paths are strictly rejected in production."""
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    # 1. Block create_subscription_order with sandbox_simulated in production
    req = MagicMock()
    req.app.state.auth.now.return_value = now
    req.app.state.auth.settings.auth_environment = "production"
    req.app.state.premium.premium_sandbox_enabled = False
    req.app.state.auth.limiter = None
    req.app.state.vnpay = None

    account = MagicMock()
    account.user.id = user_id
    account.db = MagicMock()

    with pytest.raises(AuthError) as exc_info:
        create_subscription_order(
            CreateOrderInput(plan_tier="plus", provider="sandbox_simulated"),
            request=req,
            account=account,
        )
    assert exc_info.value.status == 403
    assert exc_info.value.code == "FORBIDDEN"

    # 2. Block capture_subscription_order with sandbox_simulated in production
    sim_order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330000-SIMPROD",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="sandbox_simulated",
        created_at=now,
    )
    account.db.scalar.return_value = sim_order

    with pytest.raises(AuthError) as exc_info:
        capture_subscription_order(
            "AM-PLUS-1795330000-SIMPROD",
            payload=CaptureOrderInput(),
            request=req,
            account=account,
        )
    assert exc_info.value.status == 403
    assert exc_info.value.code == "FORBIDDEN"

    req.app.state.auth.settings.auth_environment = "development"
    with pytest.raises(AuthError) as disabled:
        capture_subscription_order(sim_order.order_code, payload=CaptureOrderInput(), request=req, account=account)
    assert disabled.value.status == 403
    req.app.state.auth.settings.auth_environment = "production"

    # 3. Block unconfigured PayPal capture fallback in production
    pp_order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330000-PPPROD",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",
        provider_txn_id="PP-TXN-123",
        created_at=now,
    )
    account.db.scalar.return_value = pp_order
    req.app.state.paypal = None

    with pytest.raises(AuthError) as exc_info:
        capture_subscription_order(
            "AM-PLUS-1795330000-PPPROD",
            payload=CaptureOrderInput(paypal_order_id="PP-TXN-123"),
            request=req,
            account=account,
        )
    assert exc_info.value.status == 503
    assert exc_info.value.code == "PAYPAL_NOT_CONFIGURED"


def test_rate_limit_order_creation():
    """Verify rate limiter blocks spamming of order creation (>10 requests/minute)."""
    from app.security import RateLimiter
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    req = MagicMock()
    req.app.state.auth.now.return_value = now
    req.app.state.auth.settings.auth_environment = "development"
    req.app.state.premium.premium_sandbox_enabled = True
    req.app.state.auth.limiter = RateLimiter()
    req.app.state.vnpay = None
    req.app.state.paypal = None

    account = MagicMock()
    account.user.id = user_id
    mock_db = MagicMock()
    mock_db.scalar.return_value = None  # Always simulate fresh orders
    account.db = mock_db

    # First 10 requests succeed
    for i in range(10):
        dto = create_subscription_order(
            CreateOrderInput(plan_tier="plus", provider="sandbox_simulated"),
            request=req,
            account=account,
        )
        assert dto.status == "pending"

    # 11th request must be rate limited (HTTP 429)
    with pytest.raises(AuthError) as exc_info:
        create_subscription_order(
            CreateOrderInput(plan_tier="plus", provider="sandbox_simulated"),
            request=req,
            account=account,
        )
    assert exc_info.value.status == 429
    assert exc_info.value.code == "RATE_LIMITED"


def test_card_simulation_records_sandbox_simulated_and_sim_card_txn():
    """Verify that simulating card payment explicitly sets provider to sandbox_simulated and SIM-CARD- prefix."""
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330000-CARDPAY",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="paypal_sandbox",  # Created initially before method choice
        created_at=now,
    )

    mock_db = MagicMock()
    mock_db.scalar.side_effect = [order, None]  # order lookup, then sub lookup

    account = MagicMock()
    account.user.id = user_id
    account.db = mock_db

    req = MagicMock()
    req.app.state.auth.now.return_value = now
    req.app.state.auth.settings.auth_environment = "development"
    req.app.state.premium.premium_sandbox_enabled = True

    dto = simulate_subscription_order(
        "AM-PLUS-1795330000-CARDPAY",
        payload=SimulateOrderInput(action="pay_success"),
        request=req,
        account=account,
    )

    assert dto.status == "success"
    assert order.status == "success"
    assert order.provider == "sandbox_simulated"
    assert order.provider_txn_id.startswith("SIM-CARD-")
    assert order.provider_response_code == "SUCCESS"




def test_paypal_return_uses_the_authorized_checkout_origin():
    from app.config import PremiumSettings
    request = MagicMock()
    request.headers = {"origin": "http://127.0.0.1:5189"}
    request.app.state.auth.settings.auth_environment = "development"
    request.app.state.auth.settings.auth_allowed_origins = ["http://127.0.0.1:5189"]
    request.app.state.auth.now.return_value = datetime.now(timezone.utc)
    request.app.state.auth.limiter = None
    request.app.state.premium = PremiumSettings(_env_file=None)
    request.app.state.paypal = MagicMock()
    request.app.state.paypal.is_configured.return_value = True
    request.app.state.paypal.mode = "sandbox"
    request.app.state.paypal.merchant_id = "AURAMEME_MERCHANT"
    request.app.state.paypal.create_order.return_value = {"id":"PP-TEST", "approve_url":"https://www.sandbox.paypal.com/checkoutnow?token=PP-TEST"}
    request.app.state.vnpay = None
    account = MagicMock()
    account.user.id = uuid4()
    account.db.scalar.return_value = None
    order = create_subscription_order(CreateOrderInput(plan_tier="plus", provider="paypal_sandbox"), request, account)
    callback = request.app.state.paypal.create_order.call_args.kwargs
    assert callback["return_url"] == "http://127.0.0.1:5189/premium/checkout?order=" + order.order_code
    assert callback["cancel_url"] == callback["return_url"] + "&cancelled=true"
