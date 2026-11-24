"""Regression for pending reuse, admin visibility, and receipt history on isolated PostgreSQL."""
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.models import SubscriptionOrder
from test_auth import auth, migrated
from test_blog import admin, blog, mutation


@pytest.mark.integration
@pytest.mark.parametrize("minutes", [5, 20, 50])
def test_pending_reuse_keeps_identity_and_original_creation(blog, minutes):
    client, db, owner, *_ = blog
    first = mutation(client, "POST", "/premium/orders", {"plan_tier": "prime"}).json()
    created = client.app.state.auth.now() - timedelta(minutes=minutes)
    db.execute(SubscriptionOrder.__table__.update().where(SubscriptionOrder.order_code == first["order_code"]).values(created_at=created))
    plus = mutation(client, "POST", "/premium/orders", {"plan_tier": "plus"}).json()
    again = mutation(client, "POST", "/premium/orders", {"plan_tier": "prime"}).json()
    assert again["order_code"] == first["order_code"] != plus["order_code"]
    assert db.scalar(select(SubscriptionOrder.created_at).where(SubscriptionOrder.order_code == first["order_code"])) == created


@pytest.mark.integration
def test_expired_pending_cannot_capture_or_simulate(blog, monkeypatch):
    client, db, owner, *_ = blog
    monkeypatch.setattr(client.app.state.auth.settings, "auth_environment", "development")
    first = mutation(client, "POST", "/premium/orders", {"plan_tier": "plus"}).json()
    db.execute(SubscriptionOrder.__table__.update().where(SubscriptionOrder.order_code == first["order_code"]).values(
        created_at=client.app.state.auth.now() - timedelta(hours=1, seconds=1)))
    for endpoint, payload in [("simulate", {"action": "pay_success"}), ("capture", {})]:
        response = mutation(client, "POST", "/premium/orders/" + first["order_code"] + "/" + endpoint, payload)
        assert response.status_code == 409, response.text
    fresh = mutation(client, "POST", "/premium/orders", {"plan_tier": "plus"}).json()
    assert fresh["order_code"] != first["order_code"]


@pytest.mark.integration
def test_admin_orders_all_statuses_search_pagination_and_errors(admin, monkeypatch):
    from app import admin_workspace
    client, db, owner, *_ = admin
    now = client.app.state.auth.now()
    from fastapi.testclient import TestClient
    from app.main import app
    from test_auth import register
    other = TestClient(app, base_url="https://testserver")
    try:
        member_b = UUID(register(other, username="hotfix_member_b", email="hotfix-b@example.com").json()["id"])
    finally:
        other.close()
    statuses = ["pending", "pending", "success", "success", "success", "success", "success", "failed", "expired", "cancelled"]
    for i, status in enumerate(statuses):
        db.execute(SubscriptionOrder.__table__.insert().values(id=uuid4(), order_code=f"AM-PLUS-HOTFIX-{i:03}",
            user_id=member_b if status == "failed" else owner, tier="plus", duration_days=30, amount_cents=500, amount_vnd=130000,
            currency="USD", status=status, provider="sandbox_simulated", created_at=now,
            updated_at=now, completed_at=now if status=="success" else None))
    result = client.get("/api/v1/admin/orders?page_size=3").json()
    assert result["pagination"]["total"] == 10 and len(result["items"]) == 3
    assert all(item["owner_username"] for item in result["items"])
    all_rows = client.get("/api/v1/admin/orders?page_size=100").json()["items"]
    assert all_rows == sorted(all_rows, key=lambda item:(item["created_at"], item["id"]), reverse=True)
    assert client.get("/api/v1/admin/orders?status=failed").json()["items"][0]["owner_username"] == "hotfix_member_b"
    assert client.get("/api/v1/admin/orders?status=expired").json()["pagination"]["total"] == 1
    assert client.get("/api/v1/admin/orders?search=HOTFIX-009").json()["items"][0]["status"] == "cancelled"
    history = client.get("/api/v1/premium/orders/successful").json()
    assert len(history) == 5 and all(item["status"]=="success" for item in history)
    def failure(*args, **kwargs):
        from sqlalchemy.exc import SQLAlchemyError
        raise SQLAlchemyError("synthetic database failure")
    original_dto = admin_workspace.AdminOrder
    from pydantic import create_model
    monkeypatch.setattr(admin_workspace, "AdminOrder", create_model("BrokenOrder", required_field=(str, ...)))
    assert client.get("/api/v1/admin/orders").status_code == 500
    monkeypatch.setattr(admin_workspace, "AdminOrder", original_dto)
    monkeypatch.setattr(admin_workspace, "page_rows", failure)
    assert client.get("/api/v1/admin/orders").status_code == 500


@pytest.mark.integration
def test_paypal_intent_binding_and_idempotent_capture(blog, monkeypatch):
    from app.paypal_adapter import PaypalAdapter
    from app.models import UserSubscription

    client, db, owner, *_ = blog
    auth = client.app.state.auth
    monkeypatch.setattr(auth.settings, "auth_environment", "development")
    paypal = PaypalAdapter("fixture-client", "fixture-secret", merchant_id="FIXTURE-MERCHANT")
    monkeypatch.setattr(client.app.state, "paypal", paypal)
    monkeypatch.setattr(client.app.state.premium, "premium_sandbox_enabled", True)

    def post(order, op, body=None):
        return mutation(client, "POST", f"/premium/orders/{order['order_code']}/{op}", body)

    order = mutation(client, "POST", "/premium/orders", {"plan_tier": "plus"}).json()
    # Legacy mock references must never be queried as real PayPal orders.
    db.execute(SubscriptionOrder.__table__.update().where(SubscriptionOrder.order_code == order["order_code"]).values(
        provider="paypal_sandbox", provider_txn_id="MOCK-PP-OLD",
        payment_url="https://www.sandbox.paypal.com/checkoutnow?token=MOCK-PP-OLD",
    ))
    assert post(order, "capture", {"paypal_order_id": "MOCK-PP-OLD"}).status_code == 400
    monkeypatch.setattr(paypal, "merchant_id", None)
    assert post(order, "init-paypal").status_code == 503
    monkeypatch.setattr(paypal, "merchant_id", "FIXTURE-MERCHANT")
    monkeypatch.setattr(paypal, "create_order", lambda **kw: {"id": "REAL-ORDER"})
    assert post(order, "init-paypal").status_code == 502
    assert db.scalar(select(SubscriptionOrder.provider_txn_id).where(SubscriptionOrder.order_code == order["order_code"])) == "MOCK-PP-OLD"

    url = "https://www.sandbox.paypal.com/checkoutnow?token=REAL-ORDER"
    monkeypatch.setattr(paypal, "create_order", lambda **kw: {"id": "REAL-ORDER", "approve_url": url})
    result = post(order, "init-paypal")
    assert result.status_code == 200
    assert result.json()["payment_url"] == url
    assert post(order, "capture", {"intent": "simulate"}).status_code == 409
    assert post(order, "simulate", {"action": "pay_success"}).status_code == 409
    assert post(order, "capture", {"intent": "paypal", "paypal_order_id": "OTHER-ORDER"}).status_code == 400

    calls = []
    receipt = []
    from app import premium
    monkeypatch.setattr(premium, "_dispatch_receipt_email_safe", lambda *args: receipt.append(args[2].order_code))

    def capture(paypal_order_id, *, idempotency_key):
        calls.append((paypal_order_id, idempotency_key))
        return {"id": paypal_order_id, "status": "COMPLETED", "purchase_units": [{
            "reference_id": idempotency_key, "payee": {"merchant_id": "FIXTURE-MERCHANT"},
            "payments": {"captures": [{"id": "REAL-CAPTURE", "status": "COMPLETED",
                                       "amount": {"currency_code": "USD", "value": "5.00"}}]},
        }]}

    monkeypatch.setattr(paypal, "capture_order", capture)
    payload = {"intent": "paypal", "paypal_order_id": "REAL-ORDER"}
    paid = post(order, "capture", payload)
    assert paid.status_code == 200
    assert paid.json()["provider_txn_id"] == "REAL-CAPTURE"
    expiry = db.scalar(select(UserSubscription.expires_at).where(UserSubscription.user_id == owner))
    duplicate = post(order, "capture", payload)
    assert duplicate.json()["provider_txn_id"] == "REAL-CAPTURE"
    assert db.scalar(select(UserSubscription.expires_at).where(UserSubscription.user_id == owner)) == expiry
    assert calls == [("REAL-ORDER", order["order_code"])]
    assert receipt == [order["order_code"]]

    instant = mutation(client, "POST", "/premium/orders", {"plan_tier": "prime"}).json()
    simulated = post(instant, "capture", {"intent": "simulate"})
    assert simulated.status_code == 200
    assert simulated.json()["provider_txn_id"].startswith("SIM-PP-")
    assert calls == [("REAL-ORDER", order["order_code"])]
