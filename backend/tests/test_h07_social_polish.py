"""H07 PostgreSQL integration tests: Reaction Details, Comment Replies, Sorting/Batch SQL Count, Notifications & Locate."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "h04"))
from safety_guard import load_env_file, verify_isolated_postgres, verify_runtime_env  # noqa: E402

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://127.0.0.1:5173"}
ADMIN_EMAIL = "khang_dev@example.com"
ADMIN_PASSWORD = "H01SimAdmin!2026"
USER_1_EMAIL = "sim_user_001@example.com"
USER_2_EMAIL = "sim_user_002@example.com"
USER_PASSWORD = "H01SimUser!2026"
MANIFEST_PATH = ROOT / "backend" / "h01.local" / "seed_manifest.json"
ENV_PATH = ROOT / "backend" / ".env.h01"


def _ensure_test_db():
    if ENV_PATH.exists():
        env_vals = load_env_file(ENV_PATH)
        for k, v in env_vals.items():
            os.environ.setdefault(k, v)
    else:
        env_vals = dict(os.environ)
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL / DATABASE_URL not configured.")
    verify_runtime_env({**env_vals, "DATABASE_URL": db_url})
    verify_isolated_postgres(db_url, MANIFEST_PATH)
    os.environ["DATABASE_URL"] = db_url


def _login(client: TestClient, email: str, password: str) -> str:
    client.cookies.clear()
    pre = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers={**ORIGIN, "X-CSRF-Token": pre})
    assert r.status_code == 200, r.text
    return client.get("/api/v1/auth/csrf").json()["csrf_token"]


def test_h07_reactions_replies_sorting_batch_notifications_and_locate():
    _ensure_test_db()
    from app.config import load_settings
    from app.db import create_db_engine
    from app.main import app
    from app.models import AuraLedger, Category, Comment, CommentReaction, Notification, Post, PostReaction, User

    engine = create_db_engine(load_settings())
    with Session(engine) as db:
        u1 = db.execute(select(User).where(User.email == USER_1_EMAIL)).scalar_one()
        u2 = db.execute(select(User).where(User.email == USER_2_EMAIL)).scalar_one()
        admin = db.execute(select(User).where(User.email == ADMIN_EMAIL)).scalar_one()
        u1_id, u1_uname = u1.id, u1.username
        u2_id, u2_uname = u2.id, u2.username
        admin_id = admin.id
        cat = db.execute(select(Category).where(Category.status == "active")).scalars().first()
        assert cat is not None
        cat_id = cat.id

    created_posts = []
    try:
        with TestClient(app) as client:
            # 1. u1 creates 2 published posts
            csrf1 = _login(client, USER_1_EMAIL, USER_PASSWORD)
            for idx in range(2):
                pr = client.post(
                    "/api/v1/posts",
                    json={"title": f"H07 Test Post {idx} {uuid4().hex[:6]}", "content": "H07 content", "category_id": str(cat_id), "status": "published"},
                    headers={**ORIGIN, "X-CSRF-Token": csrf1},
                )
                assert pr.status_code == 201, pr.text
                created_posts.append(pr.json()["id"])
            post_id, other_post_id = created_posts

            # 2. H07.1 Reaction Details: u1 reacts 'like', u2 reacts 'fire' on post_id
            assert client.put(f"/api/v1/posts/{post_id}/reactions", json={"reaction_type": "like"}, headers={**ORIGIN, "X-CSRF-Token": csrf1}).status_code == 200
            csrf2 = _login(client, USER_2_EMAIL, USER_PASSWORD)
            assert client.put(f"/api/v1/posts/{post_id}/reactions", json={"reaction_type": "fire"}, headers={**ORIGIN, "X-CSRF-Token": csrf2}).status_code == 200

            # Guest can read reaction list (no email/private data)
            client.cookies.clear()
            rx_all = client.get(f"/api/v1/posts/{post_id}/reactions?page=1&page_size=20")
            assert rx_all.status_code == 200, rx_all.text
            rx_data = rx_all.json()
            assert rx_data["pagination"]["total"] == 2
            assert rx_data["reaction_counts"]["like"] == 1
            assert rx_data["reaction_counts"]["fire"] == 1
            for item in rx_data["items"]:
                assert "email" not in item["user"]

            rx_fire = client.get(f"/api/v1/posts/{post_id}/reactions?reaction_type=fire")
            assert rx_fire.status_code == 200
            assert len(rx_fire.json()["items"]) == 1
            assert rx_fire.json()["items"][0]["user"]["username"] == u2_uname

            # Invalid filter combo -> 422
            assert client.get(f"/api/v1/posts/{post_id}/reactions?reaction_type=like&meme_asset_id={uuid4()}").status_code == 422

            # 3. H07.2 Comment Reply (root -> child -> reply-to-child stays 1-level)
            csrf2 = _login(client, USER_2_EMAIL, USER_PASSWORD)
            req_root = str(uuid4())
            c_root = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": "Root comment H07", "request_id": req_root},
                headers={**ORIGIN, "X-CSRF-Token": csrf2},
            )
            assert c_root.status_code == 201, c_root.text
            root_id = c_root.json()["id"]

            # u1 replies to root (u1 is post owner AND reply target is u2 -> u2 gets 1 reply notif, u1 gets 0 self-notif)
            csrf1 = _login(client, USER_1_EMAIL, USER_PASSWORD)
            req_r1 = str(uuid4())
            r1 = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": "Reply 1 to root", "parent_comment_id": root_id, "request_id": req_r1},
                headers={**ORIGIN, "X-CSRF-Token": csrf1},
            )
            assert r1.status_code == 201, r1.text
            r1_data = r1.json()
            assert r1_data["parent_comment_id"] == root_id
            assert r1_data["reply_to_comment_id"] == root_id
            assert r1_data["reply_to_user"]["username"] == u2_uname

            # Idempotent replay with same request_id & parent works; mismatched parent -> 409
            r1_replay = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": "Reply 1 to root", "parent_comment_id": root_id, "request_id": req_r1},
                headers={**ORIGIN, "X-CSRF-Token": csrf1},
            )
            assert r1_replay.status_code == 201
            r1_conflict = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": "Reply 1 to root", "request_id": req_r1},
                headers={**ORIGIN, "X-CSRF-Token": csrf1},
            )
            assert r1_conflict.status_code == 409

            # u2 replies to child r1 -> parent_comment_id stays root_id, reply_to_comment_id is r1_id!
            csrf2 = _login(client, USER_2_EMAIL, USER_PASSWORD)
            r2 = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": "Reply 2 to child", "parent_comment_id": r1_data["id"]},
                headers={**ORIGIN, "X-CSRF-Token": csrf2},
            )
            assert r2.status_code == 201, r2.text
            r2_data = r2.json()
            assert r2_data["parent_comment_id"] == root_id
            assert r2_data["reply_to_comment_id"] == r1_data["id"]
            assert r2_data["reply_to_user"]["username"] == u1_uname

            # Cross-post parent rejected (422)
            cross = client.post(
                f"/api/v1/posts/{other_post_id}/comments",
                json={"body": "Cross post reply", "parent_comment_id": root_id},
                headers={**ORIGIN, "X-CSRF-Token": csrf2},
            )
            assert cross.status_code == 422

            # 4. H07.4 Comment Reaction Notification (u1 reacts to root_id -> u2 gets 1 notification, no extra EXP)
            csrf1 = _login(client, USER_1_EMAIL, USER_PASSWORD)
            assert client.put(f"/api/v1/comments/{root_id}/reactions", json={"reaction_type": "love"}, headers={**ORIGIN, "X-CSRF-Token": csrf1}).status_code == 200
            assert client.put(f"/api/v1/comments/{root_id}/reactions", json={"reaction_type": "fire"}, headers={**ORIGIN, "X-CSRF-Token": csrf1}).status_code == 200

            # Comment reactions GET
            c_rx = client.get(f"/api/v1/comments/{root_id}/reactions")
            assert c_rx.status_code == 200
            assert c_rx.json()["reaction_counts"]["fire"] == 1

            # Verify u2 notifications: 1 reply notif + 1 comment-reaction notif (no duplicates)
            csrf2 = _login(client, USER_2_EMAIL, USER_PASSWORD)
            inbox = client.get("/api/v1/notifications?page=1&page_size=20").json()["items"]
            reply_notifs = [n for n in inbox if n["type"] == "comment" and n["target_id"] == r1_data["id"]]
            crx_notifs = [n for n in inbox if n["type"] == "reaction" and n["target_type"] == "comment" and n["target_id"] == root_id]
            assert len(reply_notifs) == 1 and reply_notifs[0]["payload"]["action"] == "reply"
            assert len(crx_notifs) == 1

            # 5. H07.5 Locate endpoint for reply
            loc = client.get(f"/api/v1/posts/{post_id}/comments/{r2_data['id']}/locate")
            assert loc.status_code == 200
            assert loc.json()["root_comment_id"] == root_id
            assert loc.json()["is_reply"] is True

            # 6. H07.3 Comment Sorting (reaction_desc) & O(1) Batch SQL Query Count
            # Add second root comment with 0 reactions
            c_root2 = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": "Root comment 2 (0 reactions)"},
                headers={**ORIGIN, "X-CSRF-Token": csrf2},
            )
            assert c_root2.status_code == 201
            root2_id = c_root2.json()["id"]

            # Measure SQL query count for list_comments with include_interactions=true
            sql_queries = []
            def count_sql(conn, cursor, statement, parameters, context, executemany):
                sql_queries.append(statement)

            event.listen(app.state.engine, "before_cursor_execute", count_sql)
            try:
                sorted_res = client.get(f"/api/v1/posts/{post_id}/comments?sort=reaction_desc&include_interactions=true&page_size=50")
            finally:
                event.remove(app.state.engine, "before_cursor_execute", count_sql)
            assert sorted_res.status_code == 200
            items = sorted_res.json()["items"]
            assert [x["id"] for x in items] == [root_id, root2_id]
            assert items[0]["reply_count"] == 2
            assert items[0]["interactions"]["reaction_counts"]["fire"] == 1
            assert len(sql_queries) <= 18, f"Expected O(1) batch SQL queries, got {len(sql_queries)}"

            # 7. Hide root comment -> replies & locate become 404, comments_count excludes orphan replies
            csrf_admin = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
            assert client.patch(f"/api/v1/admin/comments/{root_id}", json={"status": "hidden", "reason": "H07 hide root"}, headers={**ORIGIN, "X-CSRF-Token": csrf_admin}).status_code == 204
            assert client.get(f"/api/v1/comments/{root_id}/replies").status_code == 404
            assert client.get(f"/api/v1/posts/{post_id}/comments/{r2_data['id']}/locate").status_code == 404
            pi = client.get(f"/api/v1/posts/{post_id}/interactions").json()
            assert pi["comments_count"] == 1  # only root2_id remains visible!

            # Restore root comment -> replies become visible again
            assert client.patch(f"/api/v1/admin/comments/{root_id}", json={"status": "visible", "reason": "H07 restore root"}, headers={**ORIGIN, "X-CSRF-Token": csrf_admin}).status_code == 204
            rep_after = client.get(f"/api/v1/comments/{root_id}/replies?include_interactions=true")
            assert rep_after.status_code == 200
            assert len(rep_after.json()["items"]) == 2
    finally:
        # Soft-delete test posts so immutable aura_ledger rows are preserved
        with TestClient(app) as cleanup_client:
            csrf_admin = _login(cleanup_client, ADMIN_EMAIL, ADMIN_PASSWORD)
            for pid in created_posts:
                cleanup_client.delete(f"/api/v1/admin/posts/{pid}", headers={**ORIGIN, "X-CSRF-Token": csrf_admin})
        engine.dispose()
