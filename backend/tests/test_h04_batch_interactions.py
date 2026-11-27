"""H04 integration tests: verify batch read_post_states parity with single-post read_post_state and O(1) SQL count."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

ORIGIN_HEADERS = {"Origin": "http://127.0.0.1:5173"}
USER_1_EMAIL = "sim_user_001@example.com"
USER_2_EMAIL = "sim_user_002@example.com"
USER_PASSWORD = "H01SimUser!2026"


def _ensure_test_db_env():
    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        env_path = Path(__file__).resolve().parents[1] / ".env.h01"
        if env_path.exists():
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in raw and not raw.strip().startswith("#"):
                    k, v = raw.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL / DATABASE_URL not configured for integration test.")
    parsed = urlparse(db_url)
    if parsed.path.lstrip("/") != "aurameme_test":
        pytest.skip(f"Refusing to run against non-test database: {parsed.path}")
    os.environ["DATABASE_URL"] = db_url


@contextmanager
def _capture_sql_count():
    count = 0

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal count
        count += 1

    event.listen(Engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield lambda: count
    finally:
        event.remove(Engine, "before_cursor_execute", before_cursor_execute)


def _login_client(client: TestClient, email: str):
    pre_csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": USER_PASSWORD},
        headers={"X-CSRF-Token": pre_csrf},
    )
    assert res.status_code == 200


def test_read_post_states_empty_input():
    _ensure_test_db_env()
    from app.interactions import read_post_states

    assert read_post_states([], None, None, None) == {}


def test_feed_batch_interactions_parity_and_constant_sql_count():
    _ensure_test_db_env()
    from app.main import app

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN_HEADERS) as client:
        # 1. Guest O(1) SQL count check across page_size 10, 20, 50, 100
        guest_sql_counts = {}
        for ps in (10, 20, 50, 100):
            with _capture_sql_count() as get_count:
                res = client.get(f"/api/v1/posts?page=1&page_size={ps}&include_interactions=true")
            assert res.status_code == 200
            guest_sql_counts[ps] = get_count()
        assert guest_sql_counts[10] == guest_sql_counts[20] == guest_sql_counts[50] == guest_sql_counts[100]
        assert guest_sql_counts[100] <= 12

        # 2. Guest parity + contract + ordering + pagination
        feed_json = client.get("/api/v1/posts?page=1&page_size=20&include_interactions=true").json()
        assert set(feed_json.keys()) == {"items", "pagination"}
        feed_items = feed_json["items"]
        assert len(feed_items) == 20
        for item in feed_items:
            assert "membership_tier" in item["author"]
            direct = client.get(f"/api/v1/posts/{item['id']}/interactions")
            assert direct.status_code == 200
            assert item["interactions"] == direct.json()

        # Hot sort & page 2 parity
        hot_items = client.get("/api/v1/posts?sort=reaction_desc&page=2&page_size=10&include_interactions=true").json()["items"]
        assert len(hot_items) == 10
        for item in hot_items:
            direct = client.get(f"/api/v1/posts/{item['id']}/interactions")
            assert direct.status_code == 200
            assert item["interactions"] == direct.json()

        # 3. Viewer 1 authenticated O(1) SQL count & parity
        _login_client(client, USER_1_EMAIL)
        auth_sql_counts = {}
        for ps in (10, 20, 50, 100):
            with _capture_sql_count() as get_count:
                res = client.get(f"/api/v1/posts?page=1&page_size={ps}&include_interactions=true")
            assert res.status_code == 200
            auth_sql_counts[ps] = get_count()
        assert auth_sql_counts[10] == auth_sql_counts[20] == auth_sql_counts[50] == auth_sql_counts[100]
        assert auth_sql_counts[100] <= 19

        auth_items = client.get("/api/v1/posts?page=1&page_size=20&include_interactions=true").json()["items"]
        assert len(auth_items) == 20
        for item in auth_items:
            direct = client.get(f"/api/v1/posts/{item['id']}/interactions")
            assert direct.status_code == 200
            assert item["interactions"] == direct.json()

    # 4. Viewer 2 distinct session parity
    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN_HEADERS) as client2:
        _login_client(client2, USER_2_EMAIL)
        v2_items = client2.get("/api/v1/posts?page=1&page_size=20&include_interactions=true").json()["items"]
        assert len(v2_items) == 20
        for item in v2_items:
            direct = client2.get(f"/api/v1/posts/{item['id']}/interactions")
            assert direct.status_code == 200
            assert item["interactions"] == direct.json()


def test_read_post_states_edge_cases_visibility_locked_comments_and_meme():
    """Verify read_post_states matches read_post_state for zero interactions, locked/deleted users,
    visible/hidden/deleted comments, viewer reaction/bookmark, meme reactions, and post visibility."""
    _ensure_test_db_env()
    from starlette.requests import Request
    from sqlalchemy import select
    from app.interactions import read_post_state, read_post_states
    from app.main import app
    from app.models import AssetItem, Category, Comment, Post, PostBookmark, PostReaction, Profile, User, UserInventory
    from app.security import AuthError

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN_HEADERS):
        now = app.state.auth.now()
        fake_request = Request({"type": "http", "app": app, "headers": []})
        with app.state.auth_session_factory() as db:
            try:
                active_u1 = db.scalar(select(User).where(User.email == USER_1_EMAIL))
                active_u2 = db.scalar(select(User).where(User.email == USER_2_EMAIL))
                cat = db.scalar(select(Category).limit(1))
                owned_inv = db.execute(
                    select(UserInventory.user_id, UserInventory.asset_id)
                    .join(AssetItem, AssetItem.id == UserInventory.asset_id)
                    .where(UserInventory.quantity > 0, AssetItem.active.is_(True), AssetItem.kind == "avatar")
                    .limit(1)
                ).first()
                assert active_u1 and active_u2 and cat

                # Create temporary locked user + deleted user (rolled back at end)
                locked_u = User(
                    id=uuid4(),
                    email=f"h04_locked_{uuid4().hex[:8]}@example.com",
                    username=f"h04l_{uuid4().hex[:8]}",
                    password_hash="x",
                    status="locked",
                    created_at=now,
                    updated_at=now,
                )
                deleted_u = User(
                    id=uuid4(),
                    email=f"h04_del_{uuid4().hex[:8]}@example.com",
                    username=f"h04d_{uuid4().hex[:8]}",
                    password_hash="x",
                    status="deleted",
                    deleted_at=now,
                    created_at=now,
                    updated_at=now,
                )
                db.add_all([locked_u, deleted_u])
                db.flush()
                db.add_all([
                    Profile(user_id=locked_u.id, display_name="Locked", updated_at=now),
                    Profile(user_id=deleted_u.id, display_name="Deleted", updated_at=now),
                ])

                # Post A: 0 interactions; Post B: mixed edge cases; Post C: hidden visibility
                post_a = Post(
                    id=uuid4(), author_id=active_u1.id, category_id=cat.id,
                    title="H04 Zero Interactions", content="zero", status="published",
                    created_at=now, updated_at=now,
                )
                post_b = Post(
                    id=uuid4(), author_id=active_u1.id, category_id=cat.id,
                    title="H04 Mixed Edge Cases", content="mixed", status="published",
                    created_at=now, updated_at=now,
                )
                post_c = Post(
                    id=uuid4(), author_id=active_u1.id, category_id=cat.id,
                    title="H04 Hidden Post", content="hidden", status="hidden",
                    created_at=now, updated_at=now,
                )
                db.add_all([post_a, post_b, post_c])
                db.flush()

                # Reactions on Post B: active like, locked fire, deleted sad, plus meme reaction
                db.add_all([
                    PostReaction(post_id=post_b.id, user_id=active_u1.id, reaction_type="like", created_at=now, updated_at=now),
                    PostReaction(post_id=post_b.id, user_id=locked_u.id, reaction_type="fire", created_at=now, updated_at=now),
                    PostReaction(post_id=post_b.id, user_id=deleted_u.id, reaction_type="sad", created_at=now, updated_at=now),
                ])
                if owned_inv is not None and owned_inv[0] not in (active_u1.id, locked_u.id, deleted_u.id):
                    db.add(PostReaction(
                        post_id=post_b.id, user_id=owned_inv[0], reaction_type="meme",
                        meme_asset_id=owned_inv[1], created_at=now, updated_at=now,
                    ))
                # Bookmark for Viewer 1 only
                db.add(PostBookmark(post_id=post_b.id, user_id=active_u1.id, created_at=now))

                # Comments on Post B: visible active, hidden active, deleted active, visible locked
                db.add_all([
                    Comment(id=uuid4(), post_id=post_b.id, author_id=active_u1.id, body="visible", status="visible", created_at=now, updated_at=now),
                    Comment(id=uuid4(), post_id=post_b.id, author_id=active_u2.id, body="hidden", status="hidden", created_at=now, updated_at=now),
                    Comment(id=uuid4(), post_id=post_b.id, author_id=active_u2.id, body="deleted", status="deleted", deleted_at=now, created_at=now, updated_at=now),
                    Comment(id=uuid4(), post_id=post_b.id, author_id=locked_u.id, body="locked author", status="visible", created_at=now, updated_at=now),
                ])
                db.flush()

                for viewer in (None, active_u1.id, active_u2.id):
                    batch = read_post_states([post_a.id, post_b.id, post_c.id], db, viewer, fake_request)
                    assert post_c.id not in batch
                    assert set(batch.keys()) == {post_a.id, post_b.id}
                    assert batch[post_a.id].model_dump() == read_post_state(post_a.id, db, viewer, fake_request).model_dump()
                    assert batch[post_b.id].model_dump() == read_post_state(post_b.id, db, viewer, fake_request).model_dump()
                    with pytest.raises(AuthError) as exc_info:
                        read_post_state(post_c.id, db, viewer, fake_request)
                    assert exc_info.value.status == 404
            finally:
                db.rollback()
