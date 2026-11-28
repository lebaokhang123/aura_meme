"""H06 PostgreSQL integration tests for Notification Localization/Follow & Admin Search/Date Filters."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select
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


def _user_password() -> str:
    if ENV_PATH.exists():
        env_vals = load_env_file(ENV_PATH)
        if env_vals.get("SIM_USER_PASSWORD"):
            return env_vals["SIM_USER_PASSWORD"]
    return "H01SimUser!2026"


def _make_session():
    from app.config import load_settings
    from app.db import create_db_engine
    engine = create_db_engine(load_settings())
    return engine, Session(engine)


def test_follow_notification_and_dedupe_and_exp_antifarm():
    _ensure_test_db()
    from app.main import app
    from app.models import AuraLedger, Notification, User, UserFollow

    engine, db = _make_session()
    try:
        u1 = db.execute(select(User).where(User.email == USER_1_EMAIL)).scalar_one()
        u2 = db.execute(select(User).where(User.email == USER_2_EMAIL)).scalar_one()
        u1_id, u1_uname = u1.id, u1.username
        u2_id, u2_uname = u2.id, u2.username
        db.execute(delete(UserFollow).where(UserFollow.follower_id == u1_id, UserFollow.followee_id == u2_id))
        db.execute(delete(Notification).where(Notification.dedupe_key == f"follow:{u1_id}:{u2_id}"))
        db.commit()
    finally:
        db.close()

    pw = _user_password()
    with TestClient(app) as client:
        csrf1 = _login(client, USER_1_EMAIL, pw)
        # Follow u2
        r = client.post(f"/api/v1/users/{u2_uname}/follow", headers={**ORIGIN, "X-CSRF-Token": csrf1})
        assert r.status_code == 200, r.text
        assert r.json()["is_following"] is True

        # Repeat follow (idempotent, no duplicate notification)
        r2 = client.post(f"/api/v1/users/{u2_uname}/follow", headers={**ORIGIN, "X-CSRF-Token": csrf1})
        assert r2.status_code == 200

        # Self-follow returns 400/422 and never creates self-notification
        r_self = client.post(f"/api/v1/users/{u1_uname}/follow", headers={**ORIGIN, "X-CSRF-Token": csrf1})
        assert r_self.status_code in (400, 422)

        # Unfollow then re-follow (dedupe_key prevents spam notification, EXP not double-awarded)
        r_un = client.delete(f"/api/v1/users/{u2_uname}/follow", headers={**ORIGIN, "X-CSRF-Token": csrf1})
        assert r_un.status_code == 200
        r_re = client.post(f"/api/v1/users/{u2_uname}/follow", headers={**ORIGIN, "X-CSRF-Token": csrf1})
        assert r_re.status_code == 200

        # Verify u2 inbox has exactly 1 follow notification from u1
        _login(client, USER_2_EMAIL, pw)
        inbox = client.get("/api/v1/notifications?page=1&page_size=20")
        assert inbox.status_code == 200, inbox.text
        follow_items = [
            item for item in inbox.json()["items"]
            if item["type"] == "follow" and item["target_type"] == "user" and item["actor"] and item["actor"]["id"] == str(u1_id)
        ]
        assert len(follow_items) == 1
        assert follow_items[0]["payload"].get("follower_username") == u1_uname

    with Session(engine) as db:
        ev_count = db.execute(
            select(AuraLedger.id).where(AuraLedger.event_key == f"follow-v1:{u1_id}", AuraLedger.user_id == u2_id)
        ).scalars().all()
        assert len(ev_count) <= 1
        # Cleanup test artifacts
        db.execute(delete(UserFollow).where(UserFollow.follower_id == u1_id, UserFollow.followee_id == u2_id))
        db.execute(delete(Notification).where(Notification.dedupe_key == f"follow:{u1_id}:{u2_id}"))
        db.commit()
    engine.dispose()


def test_admin_search_vietnamese_and_date_filter_and_rbac():
    _ensure_test_db()
    from app.main import app
    from app.models import Category, Comment, Post, Profile, User

    suffix = uuid4().hex[:8]
    cat_slug = f"h06-cat-{suffix}"
    cat_name = f"Danh mục Đặc Biệt {suffix}"
    post1_title = f"Bài viết Đêm Khuya {suffix}"
    post2_title = f"Bài viết Sáng Sớm {suffix}"
    comment_body = f"Bình luận Tiếng Việt có dấu {suffix}"

    engine, db = _make_session()
    try:
        u1 = db.execute(select(User).where(User.email == USER_1_EMAIL)).scalar_one()
        u1_profile = db.execute(select(Profile).where(Profile.user_id == u1.id)).scalar_one()
        u1_id, u1_uname, u1_email, u1_display = u1.id, u1.username, u1.email, u1_profile.display_name

        now_utc = datetime.now(timezone.utc)
        cat = Category(id=uuid4(), name=cat_name, slug=cat_slug, status="active", created_at=now_utc, updated_at=now_utc)
        db.add(cat)
        db.flush()

        # 2026-05-10 23:30 Asia/Ho_Chi_Minh == 2026-05-10 16:30 UTC
        p1 = Post(
            id=uuid4(),
            author_id=u1_id,
            category_id=cat.id,
            title=post1_title,
            content=f"Nội dung thử nghiệm {suffix}",
            status="published",
            created_at=datetime(2026, 5, 10, 16, 30, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 10, 16, 30, tzinfo=timezone.utc),
        )
        # 2026-05-11 00:15 Asia/Ho_Chi_Minh == 2026-05-10 17:15 UTC (still 2026-05-10 in UTC, but 2026-05-11 in VN!)
        p2 = Post(
            id=uuid4(),
            author_id=u1_id,
            category_id=cat.id,
            title=post2_title,
            content=f"Nội dung khác {suffix}",
            status="published",
            created_at=datetime(2026, 5, 10, 17, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 10, 17, 15, tzinfo=timezone.utc),
        )
        db.add_all([p1, p2])
        db.flush()

        c1 = Comment(
            id=uuid4(),
            post_id=p1.id,
            author_id=u1_id,
            body=comment_body,
            status="visible",
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(c1)
        db.commit()
        p1_id, p2_id, c1_id, cat_id = p1.id, p2.id, c1.id, cat.id
    finally:
        db.close()

    try:
        with TestClient(app) as client:
            # Non-admin gets 403
            _login(client, USER_1_EMAIL, _user_password())
            r_forbid = client.get("/api/v1/admin/posts")
            assert r_forbid.status_code == 403

            # Admin login
            _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

            # 1. Posts search: accent-insensitive title, @username, category name
            r_title = client.get(f"/api/v1/admin/posts?search=dem khuya {suffix}")
            assert r_title.status_code == 200
            assert [x["id"] for x in r_title.json()["items"]] == [str(p1_id)]

            r_cat = client.get(f"/api/v1/admin/posts?search=dac biet {suffix}")
            assert r_cat.status_code == 200
            assert {x["id"] for x in r_cat.json()["items"]} == {str(p1_id), str(p2_id)}

            r_at = client.get(f"/api/v1/admin/posts?search=@{u1_uname}&date_from=2026-05-10&date_to=2026-05-11")
            assert r_at.status_code == 200
            assert {str(p1_id), str(p2_id)}.issubset({x["id"] for x in r_at.json()["items"]})

            # 2. Posts date range Asia/Ho_Chi_Minh boundary: 2026-05-10 includes p1 (23:30 VN) and excludes p2 (00:15 VN on May 11)
            r_may10 = client.get(f"/api/v1/admin/posts?search={suffix}&date_from=2026-05-10&date_to=2026-05-10")
            assert r_may10.status_code == 200
            assert [x["id"] for x in r_may10.json()["items"]] == [str(p1_id)]
            assert r_may10.json()["pagination"]["total"] == 1

            r_may11 = client.get(f"/api/v1/admin/posts?search={suffix}&date_from=2026-05-11&date_to=2026-05-11")
            assert r_may11.status_code == 200
            assert [x["id"] for x in r_may11.json()["items"]] == [str(p2_id)]

            # Invalid date_from > date_to -> 422
            r_bad = client.get("/api/v1/admin/posts?date_from=2026-05-12&date_to=2026-05-10")
            assert r_bad.status_code == 422

            # 3. Comments search: Vietnamese accent-insensitive body, post title, @username
            r_cm_body = client.get(f"/api/v1/admin/comments?search=tieng viet co dau {suffix}")
            assert r_cm_body.status_code == 200
            assert [x["id"] for x in r_cm_body.json()["items"]] == [str(c1_id)]

            r_cm_post = client.get(f"/api/v1/admin/comments?search=dem khuya {suffix}")
            assert r_cm_post.status_code == 200
            assert [x["id"] for x in r_cm_post.json()["items"]] == [str(c1_id)]

            r_cm_user = client.get(f"/api/v1/admin/comments?search=@{u1_uname}")
            assert r_cm_user.status_code == 200
            assert str(c1_id) in [x["id"] for x in r_cm_user.json()["items"]]

            # 4. Categories search: accent-insensitive name
            r_cats = client.get(f"/api/v1/admin/categories?search=dac biet {suffix}")
            assert r_cats.status_code == 200
            assert [x["id"] for x in r_cats.json()["items"]] == [str(cat_id)]

            # 5. Users search: @username, email, display_name
            r_u_at = client.get(f"/api/v1/admin/users?search=@{u1_uname}")
            assert r_u_at.status_code == 200
            assert str(u1_id) in [x["id"] for x in r_u_at.json()["items"]]

            r_u_email = client.get(f"/api/v1/admin/users?search={u1_email}")
            assert r_u_email.status_code == 200
            assert str(u1_id) in [x["id"] for x in r_u_email.json()["items"]]

            if u1_display:
                r_u_disp = client.get(f"/api/v1/admin/users?search={u1_display}")
                assert r_u_disp.status_code == 200
                assert str(u1_id) in [x["id"] for x in r_u_disp.json()["items"]]
    finally:
        with Session(engine) as db:
            db.execute(delete(Comment).where(Comment.id == c1_id))
            db.execute(delete(Post).where(Post.id.in_([p1_id, p2_id])))
            db.execute(delete(Category).where(Category.id == cat_id))
            db.commit()
        engine.dispose()
