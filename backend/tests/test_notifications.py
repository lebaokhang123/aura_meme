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

    # 5. DELETE /api/v1/notifications/{notification_id}
    del_op = paths["/api/v1/notifications/{notification_id}"]["delete"]
    assert del_op["operationId"] == "deleteNotification"
    assert del_op["security"] == [{"sessionCookie": []}]
    assert {"204", "401", "403", "404"} <= set(del_op["responses"])


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

        res = client.delete(f"/api/v1/notifications/{uuid4()}")
        assert res.status_code == 401


def test_reaction_deduplication_updates_payload():
    from app.notifications import create_notification
    from app.models import Notification
    db = MagicMock()
    recipient_id = uuid4()
    actor_id = uuid4()
    now = datetime.now(timezone.utc)
    dedupe_key = "reaction:post1:user1"

    existing_notif = Notification(
        id=uuid4(),
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        type="reaction",
        target_type="post",
        payload={"reaction_type": "like"},
        created_at=now,
        dedupe_key=dedupe_key
    )
    db.scalar.return_value = existing_notif

    new_payload = {"reaction_type": "fire"}
    res = create_notification(
        db,
        recipient_user_id=recipient_id,
        actor_user_id=actor_id,
        type="reaction",
        target_type="post",
        payload=new_payload,
        dedupe_key=dedupe_key,
        now=now
    )
    assert res is existing_notif
    assert existing_notif.payload == new_payload
    db.flush.assert_called_once()
    db.add.assert_not_called()


def test_social_notification_helpers_reaction_and_comment():
    from app.notifications import create_notification
    db = MagicMock()
    author_id = uuid4()
    interactor_id = uuid4()
    post_id = uuid4()
    comment_id = uuid4()
    now = datetime.now(timezone.utc)

    # 1. Reaction from another user
    db.scalar.return_value = None  # No existing dedupe
    notif_react = create_notification(
        db,
        recipient_user_id=author_id,
        type="reaction",
        target_type="post",
        target_id=post_id,
        actor_user_id=interactor_id,
        payload={"reaction_type": "fire", "post_title": "Test Title"},
        dedupe_key=f"reaction:{post_id}:{interactor_id}",
        now=now
    )
    assert notif_react is not None
    assert notif_react.recipient_user_id == author_id
    assert notif_react.actor_user_id == interactor_id
    assert notif_react.type == "reaction"
    assert notif_react.payload["reaction_type"] == "fire"

    # 2. Reaction on own post (self-interaction guard)
    notif_self_react = create_notification(
        db,
        recipient_user_id=author_id,
        type="reaction",
        target_type="post",
        target_id=post_id,
        actor_user_id=author_id,
        payload={"reaction_type": "fire"},
        now=now
    )
    assert notif_self_react is None

    # 3. Comment from another user
    db.scalar.return_value = None
    notif_comment = create_notification(
        db,
        recipient_user_id=author_id,
        type="comment",
        target_type="comment",
        target_id=comment_id,
        actor_user_id=interactor_id,
        payload={"post_id": str(post_id), "comment_body": "Nice meme!", "post_title": "Test Title"},
        dedupe_key=f"comment:{comment_id}",
        now=now
    )
    assert notif_comment is not None
    assert notif_comment.recipient_user_id == author_id
    assert notif_comment.type == "comment"
    assert notif_comment.payload["comment_body"] == "Nice meme!"

    # 4. Comment on own post
    notif_self_comment = create_notification(
        db,
        recipient_user_id=author_id,
        type="comment",
        target_type="comment",
        target_id=comment_id,
        actor_user_id=author_id,
        payload={"post_id": str(post_id), "comment_body": "My own comment"},
        now=now
    )
    assert notif_self_comment is None


def test_admin_moderation_notification_post_and_comment():
    from app.notifications import create_notification
    db = MagicMock()
    author_id = uuid4()
    admin_id = uuid4()
    post_id = uuid4()
    comment_id = uuid4()
    now = datetime.now(timezone.utc)

    # 1. Admin hides post with custom reason
    db.scalar.return_value = None
    notif_post_hidden = create_notification(
        db,
        recipient_user_id=author_id,
        type="moderation",
        target_type="post",
        target_id=post_id,
        actor_user_id=admin_id,
        payload={
            "action": "hidden",
            "reason": "Vi phạm bản quyền hình ảnh.",
            "post_title": "Meme title",
        },
        dedupe_key=f"mod:post:{post_id}:hidden",
        now=now
    )
    assert notif_post_hidden is not None
    assert notif_post_hidden.recipient_user_id == author_id
    assert notif_post_hidden.type == "moderation"
    assert notif_post_hidden.payload["action"] == "hidden"
    assert notif_post_hidden.payload["reason"] == "Vi phạm bản quyền hình ảnh."

    # 2. Admin deletes post
    db.scalar.return_value = None
    notif_post_deleted = create_notification(
        db,
        recipient_user_id=author_id,
        type="moderation",
        target_type="post",
        target_id=post_id,
        actor_user_id=admin_id,
        payload={
            "action": "deleted",
            "reason": "Nội dung phản cảm.",
            "post_title": "Meme title",
        },
        dedupe_key=f"mod:post:{post_id}:deleted",
        now=now
    )
    assert notif_post_deleted is not None
    assert notif_post_deleted.payload["action"] == "deleted"

    # 3. Admin hides comment
    db.scalar.return_value = None
    notif_comment_hidden = create_notification(
        db,
        recipient_user_id=author_id,
        type="moderation",
        target_type="comment",
        target_id=comment_id,
        actor_user_id=admin_id,
        payload={
            "action": "hidden",
            "reason": "Bình luận spam.",
            "comment_body": "Spam comment body",
        },
        dedupe_key=f"mod:comment:{comment_id}:hidden",
        now=now
    )
    assert notif_comment_hidden is not None
    assert notif_comment_hidden.target_type == "comment"
    assert notif_comment_hidden.payload["action"] == "hidden"

    # 4. Admin deletes comment
    db.scalar.return_value = None
    notif_comment_deleted = create_notification(
        db,
        recipient_user_id=author_id,
        type="moderation",
        target_type="comment",
        target_id=comment_id,
        actor_user_id=admin_id,
        payload={
            "action": "deleted",
            "reason": "Bình luận vi phạm tiêu chuẩn.",
            "comment_body": "Toxic comment body",
        },
        dedupe_key=f"mod:comment:{comment_id}:deleted",
        now=now
    )
    assert notif_comment_deleted is not None
    assert notif_comment_deleted.payload["action"] == "deleted"

    # 5. Admin self-moderation (e.g. admin hides their own post)
    notif_self_mod = create_notification(
        db,
        recipient_user_id=admin_id,
        type="moderation",
        target_type="post",
        target_id=post_id,
        actor_user_id=admin_id,
        payload={"action": "hidden"},
        now=now
    )
    assert notif_self_mod is None


def test_admin_announcements_openapi():
    from app.main import app
    schema = app.openapi()
    post_op = schema["paths"]["/api/v1/admin/announcements"]["post"]
    assert post_op["operationId"] == "adminCreateAnnouncement"
    assert post_op["security"] == [{"sessionCookie": []}]
    assert {"200", "401", "403"} <= set(post_op["responses"])


def test_admin_announcements_fanout():
    from app.admin_posts import create_admin_announcement, AnnouncementInput
    from types import SimpleNamespace
    db = MagicMock()
    admin_id = uuid4()
    u1, u2, u3 = uuid4(), uuid4(), uuid4()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [u1, u2, u3]
    db.scalars.return_value = scalars_mock

    now_val = datetime.now(timezone.utc)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(now=lambda: now_val))))
    account = SimpleNamespace(db=db, user=SimpleNamespace(id=admin_id))

    payload = AnnouncementInput(title="Bảo trì hệ thống", body="Máy chủ sẽ bảo trì lúc 00:00")
    res = create_admin_announcement(payload, request, account)

    assert res.success is True
    assert res.recipients_count == 3
    assert res.created_at == now_val

    # Verify notifications added
    db.add_all.assert_called_once()
    created_items = db.add_all.call_args[0][0]
    assert len(created_items) == 3
    assert {item.recipient_user_id for item in created_items} == {u1, u2, u3}
    assert all(item.type == "announcement" for item in created_items)
    assert all(item.payload["title"] == "Bảo trì hệ thống" for item in created_items)
    assert db.flush.assert_called_once is not None
