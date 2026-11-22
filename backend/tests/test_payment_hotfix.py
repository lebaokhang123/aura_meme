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
