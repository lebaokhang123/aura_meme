"""Unit tests for notifications API contracts, model schema, and helper logic."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4
import importlib.util

import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

ROOT = Path(__file__).resolve().parents[1]


def migration_module():
    path = ROOT / "alembic/versions/0013_notifications.py"
    spec = importlib.util.spec_from_file_location("notifications_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notifications_openapi_contracts():
    from app.main import app
    schema = app.openapi()
    paths = schema["paths"]

    # 1. GET /api/v1/notifications
    list_op = paths["/api/v1/notifications"]["get"]
    assert list_op["operationId"] == "getNotifications"
    assert list_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "403"} <= set(list_op["responses"])

    # 2. GET /api/v1/notifications/unread-count
    count_op = paths["/api/v1/notifications/unread-count"]["get"]
    assert count_op["operationId"] == "getUnreadCount"
    assert count_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "403"} <= set(count_op["responses"])

    # 3. PATCH /api/v1/notifications/{notification_id}/read
    patch_op = paths["/api/v1/notifications/{notification_id}/read"]["patch"]
    assert patch_op["operationId"] == "markNotificationRead"
    assert patch_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "403", "404"} <= set(patch_op["responses"])

    # 4. POST /api/v1/notifications/read-all
    read_all_op = paths["/api/v1/notifications/read-all"]["post"]
    assert read_all_op["operationId"] == "markAllNotificationsRead"
    assert read_all_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "403"} <= set(read_all_op["responses"])


def test_notifications_model_table_schema():
    from app.models import Base
    table = Base.metadata.tables["notifications"]

    assert [c.name for c in table.primary_key] == ["id"]
    fk_targets = {(f.parent.name, f.target_fullname, f.ondelete) for f in table.foreign_keys}
    assert ("recipient_user_id", "users.id", "CASCADE") in fk_targets
    assert ("actor_user_id", "users.id", "SET NULL") in fk_targets

    index_cols = {tuple(c.name for c in idx.columns) for idx in table.indexes}
    assert ("recipient_user_id", "created_at") in index_cols
    assert ("recipient_user_id", "read_at") in index_cols

    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "uq_notifications_dedupe_key" in ddl
    assert "ck_notifications_notification_type" in ddl
    assert "ck_notifications_notification_target_type" in ddl


def test_notifications_migration_metadata():
    mod = migration_module()
    assert mod.revision == "0013_notifications"
    assert mod.down_revision == "0012_aura_v1"
    assert hasattr(mod, "upgrade") and callable(mod.upgrade)
    assert hasattr(mod, "downgrade") and callable(mod.downgrade)


def test_create_notification_self_interaction_guard():
    from app.notifications import create_notification
    db = MagicMock()
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    # Actor == Recipient: must return None without touching db
    res = create_notification(
        db,
        recipient_user_id=user_id,
        actor_user_id=user_id,
        type="reaction",
        target_type="post",
        target_id=uuid4(),
        now=now
    )
    assert res is None
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_create_notification_deduplication():
    from app.notifications import create_notification
    from app.models import Notification
    db = MagicMock()
    recipient_id = uuid4()
    actor_id = uuid4()
    now = datetime.now(timezone.utc)
    dedupe_key = "test:reaction:123"

    # When dedupe_key already exists in DB
    existing_notif = Notification(
        id=uuid4(),
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        type="reaction",
        target_type="post",
        created_at=now,
        dedupe_key=dedupe_key
    )
    db.scalar.return_value = existing_notif

    res = create_notification(
        db,
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        type="reaction",
        target_type="post",
        dedupe_key=dedupe_key,
        now=now
    )
    assert res is existing_notif
    db.add.assert_not_called()


def test_notifications_guest_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test")
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app, base_url="https://localhost:8000") as client:
        res = client.get("/api/v1/notifications")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"

        res = client.get("/api/v1/notifications/unread-count")
        assert res.status_code == 401

        res = client.patch(f"/api/v1/notifications/{uuid4()}/read")
        assert res.status_code == 401

        res = client.post("/api/v1/notifications/read-all")
        assert res.status_code == 401
