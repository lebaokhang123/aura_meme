"""H04 integration tests: verify batch read_post_states parity with single-post read_post_state and O(1) SQL count."""
from contextlib import contextmanager
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration

ORIGIN_HEADERS = {"Origin": "http://127.0.0.1:5173"}
USER_EMAIL = "sim_user_001@example.com"
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


def test_read_post_states_empty_input():
    _ensure_test_db_env()
    from app.interactions import read_post_states

    assert read_post_states([], None, None, None) == {}


def test_feed_batch_interactions_parity_and_constant_sql_count():
    _ensure_test_db_env()
    from app.main import app

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN_HEADERS) as client:
        # 1. Guest O(1) SQL count check across page_size 10, 20, 50
        guest_sql_counts = {}
        for ps in (10, 20, 50):
            with _capture_sql_count() as get_count:
                res = client.get(f"/api/v1/posts?page=1&page_size={ps}&include_interactions=true")
            assert res.status_code == 200
            guest_sql_counts[ps] = get_count()
        assert guest_sql_counts[10] == guest_sql_counts[20] == guest_sql_counts[50]
        assert guest_sql_counts[50] <= 10

        # 2. Guest parity: feed interactions match direct GET /api/v1/posts/{id}/interactions
        feed_items = client.get("/api/v1/posts?page=1&page_size=20&include_interactions=true").json()["items"]
        assert len(feed_items) == 20
        for item in feed_items:
            direct = client.get(f"/api/v1/posts/{item['id']}/interactions")
            assert direct.status_code == 200
            assert item["interactions"] == direct.json()

        # 3. Authenticated login
        pre_csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        login = client.post(
            "/api/v1/auth/login",
            json={"email": USER_EMAIL, "password": USER_PASSWORD},
            headers={"X-CSRF-Token": pre_csrf},
        )
        assert login.status_code == 200

        # 4. Authenticated O(1) SQL count check across page_size 10, 20, 50
        auth_sql_counts = {}
        for ps in (10, 20, 50):
            with _capture_sql_count() as get_count:
                res = client.get(f"/api/v1/posts?page=1&page_size={ps}&include_interactions=true")
            assert res.status_code == 200
            auth_sql_counts[ps] = get_count()
        assert auth_sql_counts[10] == auth_sql_counts[20] == auth_sql_counts[50]
        assert auth_sql_counts[50] <= 18

        # 5. Authenticated parity: feed interactions match direct GET /api/v1/posts/{id}/interactions
        auth_items = client.get("/api/v1/posts?page=1&page_size=20&include_interactions=true").json()["items"]
        assert len(auth_items) == 20
        for item in auth_items:
            direct = client.get(f"/api/v1/posts/{item['id']}/interactions")
            assert direct.status_code == 200
            assert item["interactions"] == direct.json()
