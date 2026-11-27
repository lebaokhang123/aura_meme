"""H05 unit & API tests for PresenceStore, heartbeat security, TTL, concurrency, and Admin RBAC."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.presence import PRESENCE_TTL_SECONDS, PresenceStore
from app.security import TOKEN, digest

ORIGIN = {"Origin": "http://127.0.0.1:5173"}


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_presence_store_dedup_multi_tab_multi_session_and_logout():
    clock = FakeClock()
    store = PresenceStore(ttl_seconds=90, max_entries=100, mono_clock=clock)

    # Same user, same session (multiple tabs) -> 1 user
    store.record_user_session("sess-1", "user-1")
    store.record_user_session("sess-1", "user-1")
    assert store.snapshot().active_users == 1

    # Same user, second device session -> still 1 distinct user
    store.record_user_session("sess-2", "user-1")
    assert store.snapshot().active_users == 1

    # Logout first device -> second device still active -> still 1 distinct user
    store.remove_session("sess-1")
    assert store.snapshot().active_users == 1

    # Logout second device -> 0 active users
    store.remove_session("sess-2")
    assert store.snapshot().active_users == 0


def test_presence_store_guest_dedup_transition_and_ttl_expiry():
    clock = FakeClock()
    store = PresenceStore(ttl_seconds=90, max_entries=100, mono_clock=clock)

    # Guest across multiple tabs sharing same guest digest -> 1 guest
    store.record_guest("guest-hash-1")
    store.record_guest("guest-hash-1")
    snap = store.snapshot()
    assert snap.active_guests == 1
    assert snap.active_users == 0
    assert snap.active_total == 1

    # Guest logs in -> guest entry cleared, counted once as user
    store.record_user_session("sess-1", "user-1", guest_digest="guest-hash-1")
    snap = store.snapshot()
    assert snap.active_guests == 0
    assert snap.active_users == 1
    assert snap.active_total == 1

    # Advance clock past TTL (90s) -> expired
    clock.advance(91.0)
    snap = store.snapshot()
    assert snap.active_total == 0
    assert snap.active_users == 0
    assert snap.active_guests == 0


def test_presence_store_bounded_capacity_and_thread_safety():
    clock = FakeClock()
    store = PresenceStore(ttl_seconds=90, max_entries=5, mono_clock=clock)

    for i in range(12):
        store.record_guest(f"g-{i}")
        store.record_user_session(f"s-{i}", f"u-{i}")

    snap = store.snapshot()
    assert snap.active_guests == 5
    assert snap.active_users == 5
    assert snap.active_total == 10

    # Concurrent updates across 8 threads
    conc_store = PresenceStore(ttl_seconds=90, max_entries=500, mono_clock=clock)

    def worker(idx: int):
        for j in range(25):
            conc_store.record_user_session(f"s-{idx}-{j}", f"u-{idx % 10}")
            conc_store.record_guest(f"g-{idx % 7}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))

    conc_snap = conc_store.snapshot()
    assert conc_snap.active_users == 8
    assert conc_snap.active_guests == 7
    assert conc_snap.active_total == 15


def test_presence_api_guest_auth_rbac_revoked_and_rate_limit(monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "h05-test-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')
    monkeypatch.setenv("AUTH_ENVIRONMENT", "development")
    now_utc = datetime.now(timezone.utc)
    user_id = uuid4()
    admin_id = uuid4()
    sess_user_id = uuid4()
    sess_admin_id = uuid4()
    raw_user_token = "u" * 43
    raw_admin_token = "a" * 43
    raw_revoked_token = "r" * 43

    assert TOKEN.fullmatch(raw_user_token)

    state = {"user_status": "active", "revoked": False, "expired": False}

    @contextmanager
    def fake_session_factory():
        db = MagicMock()

        def execute(stmt, *a, **kw):
            res = MagicMock()
            sql = str(stmt)
            # Distinguish session lookup in heartbeat vs require_role
            res.one_or_none.return_value = None
            return res

        db.execute.side_effect = execute
        yield db

    with TestClient(app, base_url="http://127.0.0.1:8000", headers=ORIGIN) as client:
        clock = FakeClock()
        app.state.presence = PresenceStore(ttl_seconds=PRESENCE_TTL_SECONDS, mono_clock=clock)

        # 1. Guest heartbeat without cookie -> issues am_guest, counts 1 guest
        r1 = client.post("/api/v1/presence/heartbeat")
        assert r1.status_code == 200
        assert r1.json()["window_seconds"] == 90
        assert "am_guest" in client.cookies

        # 2. Second guest heartbeat with same cookie -> still 1 guest
        r2 = client.post("/api/v1/presence/heartbeat")
        assert r2.status_code == 200
        assert app.state.presence.snapshot().active_guests == 1

        # 3. Missing/untrusted origin -> 403
        r_bad_origin = client.post("/api/v1/presence/heartbeat", headers={"Origin": "https://evil.example"})
        assert r_bad_origin.status_code == 403

        # 4. Guest cannot read /api/v1/admin/presence -> 401
        assert client.get("/api/v1/admin/presence").status_code == 401

        # 5. Rate limit after > 12 heartbeats in 60s -> 429
        statuses = [client.post("/api/v1/presence/heartbeat").status_code for _ in range(12)]
        assert 429 in statuses

        # 6. Mocked authenticated session checks (active, revoked, expired, locked, RBAC)
        def make_factory(role_code: str):
            @contextmanager
            def _factory():
                db = MagicMock()
                db.begin.return_value.__enter__ = lambda s: None
                db.begin.return_value.__exit__ = lambda s, *a: None

                def _exec(stmt, *a, **kw):
                    res = MagicMock()
                    # Heartbeat query selects 5 columns (id, user_id, expires_at, revoked_at, status)
                    if state["revoked"]:
                        res.one_or_none.return_value = SimpleNamespace(
                            id=sess_user_id, user_id=user_id,
                            expires_at=now_utc + timedelta(minutes=10),
                            revoked_at=now_utc, status="active",
                        )
                    elif state["expired"]:
                        res.one_or_none.return_value = SimpleNamespace(
                            id=sess_user_id, user_id=user_id,
                            expires_at=now_utc - timedelta(seconds=5),
                            revoked_at=None, status="active",
                        )
                    else:
                        res.one_or_none.return_value = SimpleNamespace(
                            id=sess_admin_id if role_code == "ADMIN" else sess_user_id,
                            user_id=admin_id if role_code == "ADMIN" else user_id,
                            expires_at=now_utc + timedelta(minutes=10),
                            revoked_at=None, status=state["user_status"],
                        )
                    return res

                def _scalar(stmt, *a, **kw):
                    sql = str(stmt)
                    uid = admin_id if role_code == "ADMIN" else user_id
                    sid = sess_admin_id if role_code == "ADMIN" else sess_user_id
                    if "SELECT auth_sessions.user_id" in sql:
                        return uid
                    if "FROM users" in sql:
                        return SimpleNamespace(id=uid, status=state["user_status"])
                    if "auth_sessions" in sql:
                        return SimpleNamespace(
                            id=sid,
                            user_id=uid,
                            created_at=now_utc - timedelta(minutes=1),
                            expires_at=now_utc + timedelta(minutes=10),
                            idle_expires_at=now_utc + timedelta(minutes=10),
                            last_seen_at=now_utc,
                            revoked_at=None,
                        )
                    if "user_roles" in sql:
                        return uid if role_code == "ADMIN" else None
                    return None

                db.execute.side_effect = _exec
                db.scalar.side_effect = _scalar
                db.scalars.side_effect = lambda stmt, *a, **kw: SimpleNamespace(one_or_none=lambda: _scalar(stmt, *a, **kw))
                db.get.return_value = SimpleNamespace(
                    id=admin_id if role_code == "ADMIN" else user_id,
                    status="active",
                )
                yield db

            return _factory

        app.state.auth_session_factory = make_factory("USER")
        client.cookies.set("am_session", raw_user_token)

        # Valid USER heartbeat
        ru = client.post("/api/v1/presence/heartbeat")
        assert ru.status_code == 200
        assert app.state.presence.snapshot().active_users == 1
        # Guest cookie was converted -> guest count dropped to 0
        assert app.state.presence.snapshot().active_guests == 0

        # USER cannot read /api/v1/admin/presence -> 403
        assert client.get("/api/v1/admin/presence").status_code == 403

        # Revoked session -> 401
        state["revoked"] = True
        assert client.post("/api/v1/presence/heartbeat").status_code == 401
        state["revoked"] = False

        # Expired session -> 401
        state["expired"] = True
        assert client.post("/api/v1/presence/heartbeat").status_code == 401
        state["expired"] = False

        # Locked user -> 401
        state["user_status"] = "locked"
        assert client.post("/api/v1/presence/heartbeat").status_code == 401
        state["user_status"] = "active"

        # ADMIN can read /api/v1/admin/presence -> 200, no-store, aggregate fields only
        app.state.auth_session_factory = make_factory("ADMIN")
        client.cookies.set("am_session", raw_admin_token)
        ra = client.get("/api/v1/admin/presence")
        assert ra.status_code == 200
        assert ra.headers.get("cache-control") == "no-store"
        body = ra.json()
        assert set(body.keys()) == {"active_total", "active_users", "active_guests", "window_seconds", "generated_at"}
        assert body["active_total"] == body["active_users"] + body["active_guests"]
