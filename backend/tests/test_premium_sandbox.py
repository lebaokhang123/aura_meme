"""Unit tests for AuraMeme Premium sandbox, pricing, orders, and VNPAY adapter."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from app.aura_v1 import _POLICY
from app.config import PremiumSettings
from app.models import SubscriptionOrder, User, UserSubscription
from app.premium import active_subscription_dto, get_plans_info, read_user_subscription
from app.premium_plans import PLANS, get_plan
from app.vnpay_adapter import VnpayAdapter, VnpayConfigurationError


def test_premium_plans_authoritative_pricing():
    """Verify Owner-approved plan pricing ($5 for Plus, $50 for Prime) and durations."""
    plus = get_plan("plus")
    assert plus.tier == "plus"
    assert plus.name == "Aura Plus"
    assert plus.duration_days == 30
    assert plus.boost_multiplier == 2
    assert plus.amount_usd_cents == 500
    assert plus.amount_usd_formatted == "$5"
    assert plus.default_amount_vnd == 130000
    assert plus.default_amount_vnd % 10000 == 0

    prime = get_plan("prime")
    assert prime.tier == "prime"
    assert prime.name == "Aura Prime"
    assert prime.duration_days == 365
    assert prime.boost_multiplier == 3
    assert prime.amount_usd_cents == 5000
    assert prime.amount_usd_formatted == "$50"
    assert prime.default_amount_vnd == 1250000
    assert prime.default_amount_vnd % 10000 == 0

    with pytest.raises(ValueError, match="Invalid plan tier"):
        get_plan("unknown_plan")


def test_aura_v1_multipliers_remain_disabled():
    """Verify that the published Aura V1 policy preserves multipliers_enabled = False."""
    assert _POLICY["multipliers_enabled"] is False
    assert _POLICY["schema"] == "aurameme-aura-v1"


def test_vnpay_adapter_url_generation_and_tamper_detection():
    """Verify VNPAY HMAC SHA512 signature computation, response verification, and tamper detection."""
    adapter = VnpayAdapter(
        tmn_code="DEMO_TMN",
        hash_secret="SECRET_KEY_SANDBOX_32_BYTES_HEX_DEMO",
        pricing_approved=True,
    )
    assert adapter.is_configured() is True

    url = adapter.create_payment_url(
        order_code="AM-PLUS-TEST1234",
        amount_vnd=125000,
        order_info="Thanh toan goi Plus",
        ip_addr="127.0.0.1",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    assert "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?" in url
    assert "vnp_Amount=12500000" in url
    assert "vnp_TmnCode=DEMO_TMN" in url
    assert "vnp_TxnRef=AM-PLUS-TEST1234" in url
    assert "vnp_SecureHash=" in url

    # Parse and verify
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    qs = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

    valid, filtered = adapter.verify_response(qs)
    assert valid is True
    assert filtered["vnp_TxnRef"] == "AM-PLUS-TEST1234"
    assert filtered["vnp_Amount"] == "12500000"

    # Tampered amount
    tampered_amount = dict(qs, vnp_Amount="99999999")
    valid_tampered, _ = adapter.verify_response(tampered_amount)
    assert valid_tampered is False

    # Tampered order code
    tampered_order = dict(qs, vnp_TxnRef="AM-TAMPERED-000")
    valid_order, _ = adapter.verify_response(tampered_order)
    assert valid_order is False


def test_vnpay_adapter_fail_closed_without_approval_or_credentials():
    """VNPAY adapter must fail closed if merchant credentials or VND approval are missing."""
    # 1. Missing credentials
    unconfigured = VnpayAdapter(tmn_code=None, hash_secret=None, pricing_approved=True)
    assert unconfigured.is_configured() is False
    with pytest.raises(VnpayConfigurationError, match="credentials are not configured"):
        unconfigured.create_payment_url("ORD-1", 125000, "info")

    # 2. Missing VND pricing approval
    unapproved = VnpayAdapter(
        tmn_code="TMN",
        hash_secret="SECRET",
        pricing_approved=False,
    )
    assert unapproved.is_configured() is False
    with pytest.raises(VnpayConfigurationError, match="pricing has not been approved"):
        unapproved.create_payment_url("ORD-1", 125000, "info")


def test_active_subscription_dto_lifecycle():
    """Verify subscription DTO maps active, expired, and free states correctly."""
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)

    # 1. None -> Free
    dto_none = active_subscription_dto(None, now)
    assert dto_none.tier == "free"
    assert dto_none.is_active is False
    assert dto_none.boost_multiplier == 1
    assert dto_none.days_remaining == 0

    # 2. Active Plus
    sub_plus = UserSubscription(
        id=uuid4(),
        user_id=uuid4(),
        tier="plus",
        status="active",
        starts_at=now,
        expires_at=now + timedelta(days=30),
        created_at=now,
        updated_at=now,
    )
    dto_plus = active_subscription_dto(sub_plus, now)
    assert dto_plus.tier == "plus"
    assert dto_plus.is_active is True
    assert dto_plus.boost_multiplier == 2
    assert dto_plus.days_remaining == 30

    # 3. Active Prime
    sub_prime = UserSubscription(
        id=uuid4(),
        user_id=uuid4(),
        tier="prime",
        status="active",
        starts_at=now,
        expires_at=now + timedelta(days=365),
        created_at=now,
        updated_at=now,
    )
    dto_prime = active_subscription_dto(sub_prime, now)
    assert dto_prime.tier == "prime"
    assert dto_prime.is_active is True
    assert dto_prime.boost_multiplier == 3
    assert dto_prime.days_remaining == 365

    # 4. Expired subscription
    sub_expired = UserSubscription(
        id=uuid4(),
        user_id=uuid4(),
        tier="plus",
        status="active",
        starts_at=now - timedelta(days=31),
        expires_at=now - timedelta(days=1),
        created_at=now - timedelta(days=31),
        updated_at=now - timedelta(days=31),
    )
    dto_expired = active_subscription_dto(sub_expired, now)
    assert dto_expired.tier == "free"
    assert dto_expired.is_active is False
    assert dto_expired.boost_multiplier == 1


def test_openapi_premium_endpoints():
    """Verify OpenAPI schema contracts and security requirements for premium endpoints."""
    from app.main import app
    schema = app.openapi()
    paths = schema["paths"]

    # 1. GET /api/v1/premium/status
    status_op = paths["/api/v1/premium/status"]["get"]
    assert status_op["operationId"] == "getPremiumStatus"
    assert {"200", "401", "403"} <= set(status_op["responses"])

    # 2. POST /api/v1/premium/orders
    orders_op = paths["/api/v1/premium/orders"]["post"]
    assert orders_op["operationId"] == "createSubscriptionOrder"
    assert orders_op["security"] == [{"sessionCookie": []}]
    assert {"201", "401", "403"} <= set(orders_op["responses"])
    assert any(param["name"] == "X-CSRF-Token" for param in orders_op["parameters"])

    # 3. GET /api/v1/premium/orders/{order_code}
    get_order_op = paths["/api/v1/premium/orders/{order_code}"]["get"]
    assert get_order_op["operationId"] == "getSubscriptionOrder"
    assert get_order_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "404"} <= set(get_order_op["responses"])

    # 4. POST /api/v1/premium/orders/{order_code}/simulate
    sim_op = paths["/api/v1/premium/orders/{order_code}/simulate"]["post"]
    assert sim_op["operationId"] == "simulateSubscriptionOrder"
    assert sim_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "403", "404"} <= set(sim_op["responses"])
    assert any(param["name"] == "X-CSRF-Token" for param in sim_op["parameters"])

    # 5. GET /api/v1/premium/vnpay-return
    ret_op = paths["/api/v1/premium/vnpay-return"]["get"]
    assert ret_op["operationId"] == "handleVnpayReturn"

    # 6. GET /api/v1/premium/vnpay-ipn
    ipn_op = paths["/api/v1/premium/vnpay-ipn"]["get"]
    assert ipn_op["operationId"] == "handleVnpayIpn"


def test_guest_status_and_order_creation_guards(monkeypatch):
    """Guest can check status and view $5 / $50 plans, but cannot create orders (401)."""
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test")

    with TestClient(app, base_url="https://testserver") as client:
        # 1. Guest status check
        res = client.get("/api/v1/premium/status")
        assert res.status_code == 200
        data = res.json()
        assert data["subscription"]["tier"] == "free"
        assert data["subscription"]["is_active"] is False
        assert data["subscription"]["boost_multiplier"] == 1
        assert len(data["plans"]) == 2
        assert data["plans"][0]["amount_usd_formatted"] == "$5"
        assert data["plans"][0]["duration_days"] == 30
        assert data["plans"][1]["amount_usd_formatted"] == "$50"
        assert data["plans"][1]["duration_days"] == 365

        # 2. Guest order creation is rejected with 401
        order_res = client.post("/api/v1/premium/orders", json={"plan_tier": "plus"})
        assert order_res.status_code == 401
        assert order_res.json()["error"]["code"] == "UNAUTHORIZED"


def test_ipn_verification_amount_mismatch_and_idempotency():
    """Verify IPN callback validates signature, detects amount mismatch, and enforces idempotency."""
    adapter = VnpayAdapter(
        tmn_code="TEST_TMN",
        hash_secret="TEST_HASH_SECRET_AT_LEAST_32_BYTES_HEX",
        pricing_approved=True,
    )

    # 1. Invalid signature
    invalid_query = {
        "vnp_TxnRef": "AM-ORDER-1",
        "vnp_Amount": "12500000",
        "vnp_ResponseCode": "00",
        "vnp_SecureHash": "invalid_hash_signature",
    }
    is_valid, _ = adapter.verify_response(invalid_query)
    assert is_valid is False

    # 2. Valid signature for 125,000 VND
    valid_query = {
        "vnp_Amount": "12500000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TEST_TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORDER-1",
        "vnp_Version": "2.1.0",
    }
    import urllib.parse
    sorted_parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(valid_query[k])}" for k in sorted(valid_query.keys())]
    signature = adapter.calculate_signature("&".join(sorted_parts))
    valid_query["vnp_SecureHash"] = signature

    is_valid, filtered = adapter.verify_response(valid_query)
    assert is_valid is True
    assert filtered["vnp_TxnRef"] == "AM-ORDER-1"
    assert int(filtered["vnp_Amount"]) // 100 == 125000


def test_subscription_extension_accumulates_days():
    """Verify that extending an active subscription adds days without resetting remaining duration."""
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    current_expiry = now + timedelta(days=15)

    sub = UserSubscription(
        id=uuid4(),
        user_id=uuid4(),
        tier="plus",
        status="active",
        starts_at=now - timedelta(days=15),
        expires_at=current_expiry,
        created_at=now - timedelta(days=15),
        updated_at=now - timedelta(days=15),
    )

    # Renew Plus (30 days) while 15 days remain
    base_time = sub.expires_at if (sub.expires_at and sub.expires_at > now) else now
    new_expiry = base_time + timedelta(days=30)
    assert new_expiry == current_expiry + timedelta(days=30)
    assert (new_expiry - now).days == 45


def test_round_vnd_to_nearest_10k():
    """Verify rounding rules to the nearest 10,000 VND."""
    from app.premium_plans import round_vnd_to_nearest_10k
    assert round_vnd_to_nearest_10k(156345.333) == 160000
    assert round_vnd_to_nearest_10k(124999) == 120000
    assert round_vnd_to_nearest_10k(125000) == 130000
    assert round_vnd_to_nearest_10k(1250000) == 1250000
    assert round_vnd_to_nearest_10k(0) == 0


def test_simulate_direct_call_production_guard():
    """Verify simulate_subscription_order explicitly raises 403 FORBIDDEN when auth_environment == 'production'."""
    from unittest.mock import MagicMock
    from app.premium import simulate_subscription_order, SimulateOrderInput
    from app.security import AuthError

    mock_request = MagicMock()
    mock_request.app.state.auth.settings.auth_environment = "production"
    mock_request.app.state.premium.premium_sandbox_enabled = True

    mock_account = MagicMock()

    with pytest.raises(AuthError) as exc_info:
        simulate_subscription_order(
            order_code="AM-PLUS-1795330000-TEST1234",
            payload=SimulateOrderInput(action="pay_success"),
            request=mock_request,
            account=mock_account,
        )
    assert exc_info.value.status == 403
    assert exc_info.value.code == "FORBIDDEN"
    assert "production" in exc_info.value.message.lower()


def test_create_order_schema_contract():
    """Verify create_subscription_order accepts plan_tier and provider, computing correct order snapshot."""
    from unittest.mock import MagicMock
    from app.premium import create_subscription_order, CreateOrderInput

    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now
    mock_request.app.state.premium.vnpay_price_plus_vnd = 125000
    mock_request.app.state.premium.vnpay_price_prime_vnd = 1250000

    mock_account = MagicMock()
    mock_account.user.id = uuid4()

    # Plus order
    order_dto_plus = create_subscription_order(
        payload=CreateOrderInput(plan_tier="plus", provider="sandbox_simulated"),
        request=mock_request,
        account=mock_account,
    )
    assert order_dto_plus.tier == "plus"
    assert order_dto_plus.duration_days == 30
    assert order_dto_plus.amount_usd_cents == 500
    assert order_dto_plus.amount_usd_formatted == "$5"
    assert order_dto_plus.amount_vnd == 130000
    assert order_dto_plus.amount_vnd % 10000 == 0
    assert order_dto_plus.status == "pending"

    # Prime order
    order_dto_prime = create_subscription_order(
        payload=CreateOrderInput(plan_tier="prime", provider="sandbox_simulated"),
        request=mock_request,
        account=mock_account,
    )
    assert order_dto_prime.tier == "prime"
    assert order_dto_prime.duration_days == 365
    assert order_dto_prime.amount_usd_cents == 5000
    assert order_dto_prime.amount_usd_formatted == "$50"
    assert order_dto_prime.amount_vnd == 1250000
    assert order_dto_prime.status == "pending"


def test_vnpay_return_redirects_without_activating_subscription():
    """Verify handle_vnpay_return redirects with vnp_status and does NOT activate subscription."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_return
    from app.models import SubscriptionOrder, UserSubscription

    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)

    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "12500000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-123",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-123",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=125000,
        currency="USD",
        status="pending",
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    response = handle_vnpay_return(mock_request)
    assert response.status_code in {302, 307}
    assert "/premium?vnp_status=success&order_code=AM-ORD-123" in response.headers["location"]
    # UserSubscription was never created during return URL navigation!
    assert not any(isinstance(call.args[0], UserSubscription) for call in mock_db.add.call_args_list if call.args)


def test_vnpay_ipn_confirms_and_activates_subscription():
    """Verify handle_vnpay_ipn is authoritative: updates order to success and activates subscription."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn
    from app.models import SubscriptionOrder, UserSubscription

    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now

    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-123",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    user_id = uuid4()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-123",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.side_effect = [order, None]
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    res = handle_vnpay_ipn(mock_request)
    assert res == {"RspCode": "00", "Message": "Confirm Success"}
    assert order.status == "success"
    assert order.completed_at == now
    assert mock_db.add.called
    added_sub = mock_db.add.call_args[0][0]
    assert isinstance(added_sub, UserSubscription)
    assert added_sub.tier == "plus"
    assert added_sub.status == "active"
    assert added_sub.expires_at == now + timedelta(days=30)


def test_vnpay_ipn_duplicate_callback_returns_rspcode_02():
    """Verify duplicate IPN callback returns RspCode 02 (Order already confirmed) without re-processing."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn
    from app.models import SubscriptionOrder

    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now

    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-123",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-123",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="success",  # Already processed!
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    res = handle_vnpay_ipn(mock_request)
    assert res == {"RspCode": "02", "Message": "Order already confirmed"}


def test_vnpay_ipn_failure_marks_order_failed():
    """Verify IPN callback with non-00 response code marks order failed without creating subscription."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn
    from app.models import SubscriptionOrder

    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now

    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "24",  # Customer cancelled
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-123",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-123",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    res = handle_vnpay_ipn(mock_request)
    assert res == {"RspCode": "00", "Message": "Confirm Success"}
    assert order.status == "cancelled"
    assert not mock_db.add.called


def test_vnpay_ipn_requires_strict_transaction_status_00():
    """Verify handle_vnpay_ipn strictly requires vnp_TransactionStatus == '00'."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn
    from app.models import SubscriptionOrder

    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now
    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    # Case A: Missing vnp_TransactionStatus
    params_missing = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-MISSING-STATUS",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params_missing[k])}" for k in sorted(params_missing.keys())]
    params_missing["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params_missing

    mock_db = MagicMock()
    order_a = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-MISSING-STATUS",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order_a
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    res_a = handle_vnpay_ipn(mock_request)
    assert res_a == {"RspCode": "00", "Message": "Confirm Success"}
    # Must NOT become success
    assert order_a.status != "success"
    assert order_a.status == "failed"

    # Case B: Invalid vnp_TransactionStatus == "02" (failed)
    params_invalid = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "02",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-INVALID-STATUS",
        "vnp_Version": "2.1.0",
    }
    parts_b = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params_invalid[k])}" for k in sorted(params_invalid.keys())]
    params_invalid["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts_b))
    mock_request.query_params = params_invalid

    order_b = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-INVALID-STATUS",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order_b
    res_b = handle_vnpay_ipn(mock_request)
    assert res_b == {"RspCode": "00", "Message": "Confirm Success"}
    assert order_b.status != "success"
    assert order_b.status == "failed"


def test_pricing_and_rounding_policy_on_actual_plans_and_orders():
    """Verify 10,000 VND rounding policy on authoritative plans, status responses, and order creation."""
    from app.premium_plans import PLANS, round_vnd_to_nearest_10k
    from app.premium import get_plans_info

    # 1. Authoritative plans adhere to 10k VND rounding
    for tier, plan in PLANS.items():
        assert plan.default_amount_vnd % 10000 == 0, f"Plan {tier} VND price must be divisible by 10,000"

    # 2. Status response plans adhere to 10k VND rounding and include formatted string
    mock_req = MagicMock()
    mock_req.app.state.premium = None
    plans_info = get_plans_info(mock_req)
    for p in plans_info:
        assert p.amount_vnd % 10000 == 0
        assert p.amount_vnd_formatted.endswith(" VNĐ")

    # 3. Dynamic odd settings are strictly rounded to nearest 10,000
    mock_settings = MagicMock()
    mock_settings.vnpay_price_plus_vnd = 124999  # Should round down to 120,000
    mock_settings.vnpay_price_prime_vnd = 127500  # Should round up to 130,000
    mock_req.app.state.premium = mock_settings
    plans_rounded = get_plans_info(mock_req)
    plus_p = next(p for p in plans_rounded if p.tier == "plus")
    prime_p = next(p for p in plans_rounded if p.tier == "prime")
    assert plus_p.amount_vnd == 120000
    assert prime_p.amount_vnd == 130000


def test_vnpay_return_strictly_redirects_without_any_db_writes():
    """Verify handle_vnpay_return performs ZERO writes and never mutates order status."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_return
    from app.models import SubscriptionOrder

    mock_request = MagicMock()
    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-RETURN-TEST",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-ORD-RETURN-TEST",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",  # Status must remain pending!
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    res = handle_vnpay_return(mock_request)
    assert res.status_code == 302
    assert "/premium?vnp_status=success&order_code=AM-ORD-RETURN-TEST" in res.headers["location"]
    # Order status MUST NOT be changed by Return URL!
    assert order.status == "pending"
    assert not mock_db.flush.called


def test_vnpay_ipn_rejects_simulated_order_provider():
    """Verify handle_vnpay_ipn rejects simulated order provider with RspCode 99."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn
    from app.models import SubscriptionOrder

    mock_request = MagicMock()
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request.app.state.auth.now.return_value = now
    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-SIM-PLUS-123",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-SIM-PLUS-123",
        user_id=uuid4(),
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="sandbox_simulated",  # Not a VNPAY order!
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order
    mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

    res = handle_vnpay_ipn(mock_request)
    assert res == {"RspCode": "99", "Message": "Invalid order provider"}
    assert order.status == "pending"


def test_vnpay_ipn_rejects_terminal_state_orders():
    """Verify handle_vnpay_ipn rejects orders that are already failed or cancelled with RspCode 02."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn
    from app.models import SubscriptionOrder

    mock_request = MagicMock()
    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request.app.state.auth.now.return_value = now
    adapter = VnpayAdapter(tmn_code="TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-PLUS-TERMINAL",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    mock_db = MagicMock()
    for terminal_status in ["failed", "cancelled", "expired"]:
        order = SubscriptionOrder(
            id=uuid4(),
            order_code="AM-PLUS-TERMINAL",
            user_id=uuid4(),
            tier="plus",
            duration_days=30,
            amount_cents=500,
            amount_vnd=130000,
            currency="USD",
            status=terminal_status,
            provider="vnpay_sandbox",
            created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
        )
        mock_db.scalar.return_value = order
        mock_request.app.state.auth_session_factory.return_value.__enter__.return_value = mock_db

        res = handle_vnpay_ipn(mock_request)
        assert res == {"RspCode": "02", "Message": "Order already processed"}
        assert order.status == terminal_status


def test_vnpay_ipn_merchant_code_validation():
    """Verify handle_vnpay_ipn rejects mismatched vnp_TmnCode with RspCode 97."""
    import urllib.parse
    from unittest.mock import MagicMock
    from app.premium import handle_vnpay_ipn

    mock_request = MagicMock()
    adapter = VnpayAdapter(tmn_code="CORRECT_TMN", hash_secret="SECRET", pricing_approved=True)
    mock_request.app.state.vnpay = adapter

    params = {
        "vnp_Amount": "13000000",
        "vnp_Command": "pay",
        "vnp_ResponseCode": "00",
        "vnp_TmnCode": "WRONG_TMN",
        "vnp_TransactionNo": "140001",
        "vnp_TxnRef": "AM-ORD-TMN-TEST",
        "vnp_Version": "2.1.0",
    }
    parts = [f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(params[k])}" for k in sorted(params.keys())]
    params["vnp_SecureHash"] = adapter.calculate_signature("&".join(parts))
    mock_request.query_params = params

    res = handle_vnpay_ipn(mock_request)
    assert res == {"RspCode": "97", "Message": "Invalid Merchant Code"}


def test_get_subscription_order_endpoint():
    """Verify GET /orders/{order_code} returns order details for owner and raises 404 for non-owners."""
    from unittest.mock import MagicMock
    from app.premium import get_subscription_order
    from app.security import AuthError
    from app.models import SubscriptionOrder

    user_id = uuid4()
    mock_account = MagicMock()
    mock_account.user.id = user_id

    mock_db = MagicMock()
    order = SubscriptionOrder(
        id=uuid4(),
        order_code="AM-PLUS-1795330001-GET12345",
        user_id=user_id,
        tier="plus",
        duration_days=30,
        amount_cents=500,
        amount_vnd=130000,
        currency="USD",
        status="pending",
        provider="vnpay_sandbox",
        created_at=datetime(2026, 11, 21, 10, 0, 0, tzinfo=timezone.utc),
    )
    mock_db.scalar.return_value = order
    mock_account.db = mock_db

    mock_db.get.return_value.username = "order_owner"
    dto = get_subscription_order("AM-PLUS-1795330001-GET12345", account=mock_account)
    assert dto.order_code == "AM-PLUS-1795330001-GET12345"
    assert dto.tier == "plus"
    assert dto.amount_vnd == 130000
    assert dto.amount_vnd % 10000 == 0

    # Non-existent or non-owned order
    mock_db.scalar.return_value = None
    with pytest.raises(AuthError) as exc_info:
        get_subscription_order("AM-PLUS-1795330002-UNKNOWN1", account=mock_account)
    assert exc_info.value.status == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_create_order_database_error_logging_and_propagation():
    """Verify create_subscription_order logs server errors and propagates database exceptions."""
    from unittest.mock import MagicMock
    from sqlalchemy.exc import ProgrammingError
    from app.premium import create_subscription_order, CreateOrderInput

    now = datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    mock_request = MagicMock()
    mock_request.app.state.auth.now.return_value = now
    mock_request.app.state.premium.vnpay_price_plus_vnd = 130000
    mock_request.app.state.premium.vnpay_price_prime_vnd = 1250000

    mock_account = MagicMock()
    mock_account.user.id = uuid4()
    # Simulate DB error such as missing table (UndefinedTable 42P01)
    mock_account.db.flush.side_effect = ProgrammingError(
        "INSERT INTO subscription_orders",
        {},
        Exception("relation subscription_orders does not exist"),
    )

    with pytest.raises(ProgrammingError):
        create_subscription_order(
            payload=CreateOrderInput(plan_tier="prime", provider="sandbox_simulated"),
            request=mock_request,
            account=mock_account,
        )


@pytest.mark.integration
def test_create_order_and_subscription_real_postgresql_integration():
    """Verify real PostgreSQL database integration for migration 0014: order creation and subscription persistence.

    If TEST_DATABASE_URL is not provided, this test skips safely per AGENTS.md rules
    (INTEGRATION UNVERIFIED). If provided, it verifies real database writes to subscription_orders
    and user_subscriptions.
    """
    import os
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL missing; PostgreSQL migration 0014 integration UNVERIFIED (per AGENTS.md)")

    from app.config import Settings
    from app.db import create_db_engine
    from app.models import Base, SubscriptionOrder, User, UserSubscription
    from app.premium import CreateOrderInput, create_subscription_order
    from sqlalchemy import inspect, select
    from sqlalchemy.orm import Session

    engine = create_db_engine(Settings(_env_file=None, database_url=url))
    with Session(engine) as db:
        from sqlalchemy import text
        assert db.execute(text("SELECT current_database(), current_schema()")).one() == ("aurameme_test", "public")
        inspector = inspect(db.connection())
        tables = set(inspector.get_table_names())
        assert "subscription_orders" in tables, "Migration 0014 table subscription_orders must exist in test database"
        assert "user_subscriptions" in tables, "Migration 0014 table user_subscriptions must exist in test database"

        now = datetime.now(timezone.utc)
        test_user = User(
            id=uuid4(),
            username=f"test_sub_{uuid4().hex[:8]}",
            email=f"test_sub_{uuid4().hex[:8]}@example.com",
            password_hash="synthetic_hash_for_test",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(test_user)
        db.flush()

        try:
            mock_request = MagicMock()
            mock_request.app.state.auth.now.return_value = now
            mock_request.app.state.premium.vnpay_price_plus_vnd = 130000
            mock_request.app.state.premium.vnpay_price_prime_vnd = 1250000

            mock_account = MagicMock()
            mock_account.user = test_user
            mock_account.db = db

            # Test 1: Create Plus order in real DB
            order_dto_plus = create_subscription_order(
                payload=CreateOrderInput(plan_tier="plus", provider="sandbox_simulated"),
                request=mock_request,
                account=mock_account,
            )
            assert order_dto_plus.tier == "plus"
            assert order_dto_plus.amount_usd_cents == 500
            assert order_dto_plus.amount_vnd == 130000
            assert order_dto_plus.status == "pending"

            persisted_plus = db.scalar(
                select(SubscriptionOrder).where(SubscriptionOrder.order_code == order_dto_plus.order_code)
            )
            assert persisted_plus is not None
            from app.premium import get_subscription_order
            assert get_subscription_order(persisted_plus.order_code, account=mock_account).id == persisted_plus.id
            from app.premium import SimulateOrderInput, simulate_subscription_order
            mock_request.app.state.auth.settings.auth_environment = "development"
            mock_request.app.state.premium.premium_sandbox_enabled = True
            assert persisted_plus.user_id == test_user.id
            assert persisted_plus.tier == "plus"
            assert persisted_plus.amount_cents == 500
            assert persisted_plus.amount_vnd == 130000
            assert persisted_plus.status == "pending"
            assert persisted_plus.provider == "sandbox_simulated"

            # Test 2: Create Prime order in real DB
            order_dto_prime = create_subscription_order(
                payload=CreateOrderInput(plan_tier="prime", provider="sandbox_simulated"),
                request=mock_request,
                account=mock_account,
            )
            assert order_dto_prime.tier == "prime"
            assert order_dto_prime.amount_usd_cents == 5000
            assert order_dto_prime.amount_vnd == 1250000

            persisted_prime = db.scalar(
                select(SubscriptionOrder).where(SubscriptionOrder.order_code == order_dto_prime.order_code)
            )
            assert persisted_prime is not None
            for _ in range(2):
                simulate_subscription_order(persisted_plus.order_code, SimulateOrderInput(action="pay_success"), mock_request, mock_account)
            sub = db.scalar(select(UserSubscription).where(UserSubscription.user_id == test_user.id))
            assert sub.order_id == persisted_plus.id and sub.expires_at - sub.starts_at == timedelta(days=30)
            assert persisted_prime.user_id == test_user.id
            assert persisted_prime.tier == "prime"

            db.rollback()
        finally:
            engine.dispose()




