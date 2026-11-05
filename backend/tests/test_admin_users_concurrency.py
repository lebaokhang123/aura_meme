"""Committed, independently connected administrators: last-admin and audit consistency."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from app.main import app
from app.models import AdminAuditLog, AuthSession, Profile, Role, User, UserRole
from test_auth import ORIGIN, csrf, login, migrated, register
from test_blog import mutation


@pytest.fixture
def admins(migrated, monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    tag = "m41a_" + uuid4().hex
    engine = create_engine(migrated.url, hide_parameters=True, connect_args={"application_name": tag,
        "options": "-c statement_timeout=12000 -c lock_timeout=8000"})
    names = ["admin_" + uuid4().hex[:16] for _ in range(2)]
    with TestClient(app, base_url=ORIGIN) as first:
        app.state.auth_session_factory = lambda: Session(engine)
        second = TestClient(app, base_url=ORIGIN)
        try:
            ids = []
            for client, name in zip([first, second], names):
                response = register(client, username=name, email=name + "@example.com")
                assert response.status_code == 201
                from uuid import UUID
                ids.append(UUID(response.json()["id"]))
                assert login(client, email=name + "@example.com").status_code == 200
            with engine.begin() as connection:
                role = uuid4()
                connection.execute(Role.__table__.insert().values(id=role, code="ADMIN", description="Isolated test role"))
                for ident in ids:
                    connection.execute(UserRole.__table__.insert().values(user_id=ident, role_id=role, granted_at=app.state.auth.now()))
            yield first, second, ids, engine, tag
        finally:
            second.close()
            with engine.begin() as connection:
                ids = list(connection.scalars(select(User.id).where(User.username.in_(names))))
                roles = set(connection.scalars(select(UserRole.role_id).where(UserRole.user_id.in_(ids))))
                connection.execute(AdminAuditLog.__table__.delete().where(AdminAuditLog.actor_id.in_(ids)))
                for model, column in [(AuthSession, AuthSession.user_id), (UserRole, UserRole.user_id), (Profile, Profile.user_id), (User, User.id)]:
                    connection.execute(model.__table__.delete().where(column.in_(ids)))
                for role in roles:
                    assert connection.scalar(select(UserRole.user_id).where(UserRole.role_id == role)) is None
                    connection.execute(Role.__table__.delete().where(Role.id == role))
            engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("action", ["lock", "delete"])
@pytest.mark.parametrize("target", ["self", "other"])
def test_last_active_admin_survives_concurrent_mutations(admins, action, target):
    first, second, ids, engine, tag = admins
    tokens = [csrf(first), csrf(second)]
    locked, release = Event(), Event()
    def hold_first(conn, cursor, statement, parameters, context, executemany):
        if "FROM roles" in statement and "FOR UPDATE" in statement and not locked.is_set():
            locked.set()
            assert release.wait(7)
    event.listen(engine, "after_cursor_execute", hold_first)
    def change(index):
        ident = ids[index if target == "self" else 1-index]
        return mutation([first, second][index], "PATCH" if action == "lock" else "DELETE",
                        "/admin/users/" + str(ident), {"status": "locked"} if action == "lock" else None, tokens[index])
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(change, 0)
            try:
                assert locked.wait(5)
                b = pool.submit(change, 1)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with engine.connect() as connection:
                        waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:tag AND wait_event_type='Lock'"), {"tag": tag})
                    if waiting: break
                    time.sleep(0.02)
                assert waiting, "No genuine lock contention observed"
            finally:
                release.set()
            responses = [a.result(timeout=15), b.result(timeout=15)]
        assert responses[0].status_code == (200 if action == "lock" else 204), responses[0].text
        assert responses[1].status_code == (409 if target == "self" else 401), responses[1].text
        with engine.connect() as connection:
            assert len(list(connection.scalars(select(User.id).where(User.id.in_(ids), User.status == "active")))) == 1
            assert len(list(connection.scalars(select(AdminAuditLog.id)))) == 1
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", hold_first)


@pytest.mark.integration
def test_deferred_audit_commit_failure_rolls_back_target(admins):
    first, second, ids, engine, tag = admins
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m41a_commit_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred audit failure'; END $$")
            connection.exec_driver_sql("CREATE CONSTRAINT TRIGGER m41a_commit_reject AFTER INSERT ON admin_audit_logs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m41a_commit_reject()")
        response = mutation(first, "PATCH", "/admin/users/" + str(ids[1]), {"status": "locked"})
        assert response.status_code == 500
        with engine.connect() as connection:
            assert set(connection.scalars(select(User.status))) == {"active"}
            assert list(connection.scalars(select(AdminAuditLog.id))) == []
            assert set(connection.scalars(select(AuthSession.revoked_at))) == {None}
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER m41a_commit_reject ON admin_audit_logs")
            connection.exec_driver_sql("DROP FUNCTION m41a_commit_reject()")
