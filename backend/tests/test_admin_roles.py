"""Role replacement through Admin lifecycle transaction on real PostgreSQL."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, text
from app.models import AdminAuditLog, AuthSession, Role, User, UserRole
from test_auth import auth, csrf, login, migrated
from test_blog import admin, blog, mutation
from test_admin_users import PAYLOAD
from test_admin_users_concurrency import admins


@pytest.mark.integration
def test_role_put_replaces_deduplicates_and_audits(admin):
    client, connection, actor, *_ = admin
    ident = mutation(client, "POST", "/admin/users", PAYLOAD).json()["id"]
    response = mutation(client, "PUT", "/admin/users/" + ident + "/roles", {"roles": ["USER", "ADMIN", "ADMIN"]})
    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["ADMIN", "USER"]
    audit = connection.execute(select(AdminAuditLog.__table__).where(AdminAuditLog.action == "user.roles")).mappings().one()
    assert audit["before_json"]["roles"] == ["USER"]
    assert audit["after_json"]["roles"] == ["ADMIN", "USER"]
    assert PAYLOAD["email"] not in str(audit)


@pytest.mark.integration
def test_role_put_keeps_last_active_admin(admin):
    client, connection, actor, *_ = admin
    response = mutation(client, "PUT", "/admin/users/" + str(actor) + "/roles", {"roles": ["USER"]})
    assert response.status_code == 409, response.text


@pytest.mark.integration
@pytest.mark.parametrize("payload", [{}, {"roles": None}, {"roles": "ADMIN"}, {"roles": ["ROOT"]},
    {"roles": ["ADMIN"], "status": "active"}, {"roles": ["USER"], "user_id": "forged"}])
def test_roles_strict_allowlist(admin, payload):
    client, connection, actor, *_ = admin
    assert mutation(client, "PUT", f"/admin/users/{actor}/roles", payload).status_code == 422
    assert connection.execute(select(AdminAuditLog.id)).all() == []


@pytest.mark.integration
@pytest.mark.parametrize("identity", ["anonymous", "user"])
def test_role_put_no_privilege_escalation(blog, identity):
    client, connection, actor, *_ = blog
    if identity == "anonymous": client.cookies.clear()
    assert mutation(client, "PUT", f"/admin/users/{actor}/roles", {"roles": ["ADMIN"]}).status_code == (401 if identity == "anonymous" else 403)
    assert connection.execute(select(Role.id).where(Role.code == "ADMIN")).all() == []


@pytest.mark.integration
@pytest.mark.parametrize("fault", ["csrf", "origin"])
def test_roles_csrf_and_origin(admin, fault):
    client, _, actor, *_ = admin
    assert mutation(client, "PUT", f"/admin/users/{actor}/roles", {"roles": ["ADMIN"]},
        token="bad" if fault == "csrf" else csrf(client), origin="https://evil.example" if fault == "origin" else "https://testserver").status_code == 403


@pytest.mark.integration
def test_role_noop_preserves_grant_times_and_sessions(admin):
    client, connection, actor, *_ = admin
    before = connection.execute(select(UserRole.__table__).where(UserRole.user_id == actor)).all()
    assert mutation(client, "PUT", f"/admin/users/{actor}/roles", {"roles": ["USER", "ADMIN", "ADMIN"]}).status_code == 200
    assert connection.execute(select(UserRole.__table__).where(UserRole.user_id == actor)).all() == before
    assert set(connection.scalars(select(AuthSession.revoked_at))) == {None}
    assert connection.scalar(select(AdminAuditLog.after_json))["roles_changed"] is False


@pytest.mark.integration
def test_roles_revoke_sessions_and_empty_contract(admin):
    from fastapi.testclient import TestClient
    from app.main import app
    client, connection, actor, *_ = admin
    ident = mutation(client, "POST", "/admin/users", PAYLOAD).json()["id"]
    other = TestClient(app, base_url="https://testserver")
    try:
        assert login(other, email=PAYLOAD["email"], password=PAYLOAD["password"]).status_code == 200
        response = mutation(client, "PUT", f"/admin/users/{ident}/roles", {"roles": []})
        assert response.status_code == 200 and response.json()["roles"] == []
        assert other.get("/api/v1/users/me").status_code == 401
        assert connection.scalar(select(AuthSession.revoked_at).where(AuthSession.user_id == UUID(ident))) is not None
    finally:
        other.close()
    assert mutation(client, "PUT", f"/admin/users/{uuid4()}/roles", {"roles": []}).status_code == 404
    assert mutation(client, "PUT", "/admin/users/bad/roles", {"roles": []}).status_code == 422
    assert mutation(client, "DELETE", "/admin/users/" + ident).status_code == 204
    assert mutation(client, "PUT", f"/admin/users/{ident}/roles", {"roles": ["ADMIN"]}).status_code == 404


@pytest.mark.integration
def test_locked_admin_does_not_count_as_surviving_admin(admin):
    client, connection, actor, *_ = admin
    ident = mutation(client, "POST", "/admin/users", PAYLOAD | {"roles": ["ADMIN"]}).json()["id"]
    assert mutation(client, "PATCH", "/admin/users/" + ident, {"status": "locked"}).status_code == 200
    assert mutation(client, "PUT", f"/admin/users/{actor}/roles", {"roles": []}).status_code == 409


@pytest.mark.integration
def test_audit_failure_restores_roles_and_session(admin):
    from fastapi.testclient import TestClient
    from app.main import app
    client, connection, actor, *_ = admin
    ident = mutation(client, "POST", "/admin/users", PAYLOAD).json()["id"]
    other = TestClient(app, base_url="https://testserver")
    try:
        assert login(other, email=PAYLOAD["email"], password=PAYLOAD["password"]).status_code == 200
        connection.exec_driver_sql("CREATE FUNCTION m41b_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic role audit rejection'; END $$")
        connection.exec_driver_sql("CREATE TRIGGER m41b_audit_fail BEFORE INSERT ON admin_audit_logs FOR EACH ROW EXECUTE FUNCTION m41b_audit_fail()")
        assert mutation(client, "PUT", f"/admin/users/{ident}/roles", {"roles": ["ADMIN"]}).status_code == 500
        assert other.get("/api/v1/users/me").json()["roles"] == ["USER"]
        assert connection.scalar(select(AuthSession.revoked_at).where(AuthSession.user_id == UUID(ident))) is None
    finally:
        other.close()


@pytest.mark.integration
@pytest.mark.parametrize("target", ["self", "other"])
@pytest.mark.parametrize("second_action", ["role", "lock", "delete"])
def test_roles_compete_with_roles_or_status_without_losing_admin(admins, target, second_action):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    from sqlalchemy import event
    first, second, ids, engine, tag = admins
    tokens = [csrf(first), csrf(second)]
    acquired, release = Event(), Event()
    def pause(conn, cursor, statement, parameters, context, executemany):
        if "FROM roles" in statement and "FOR UPDATE" in statement and not acquired.is_set():
            acquired.set()
            assert release.wait(7)
    event.listen(engine, "after_cursor_execute", pause)
    def change(index):
        ident = ids[index if target == "self" else 1-index]
        action = "role" if index == 0 else second_action
        return mutation([first, second][index], {"role": "PUT", "lock": "PATCH", "delete": "DELETE"}[action],
            f"/admin/users/{ident}" + ("/roles" if action == "role" else ""),
            {"roles": ["USER"]} if action == "role" else {"status": "locked"} if action == "lock" else None, tokens[index])
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(change, 0)
            try:
                assert acquired.wait(5)
                b = pool.submit(change, 1)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with engine.connect() as connection:
                        waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:tag AND wait_event_type='Lock'"), {"tag": tag})
                    if waiting: break
                    time.sleep(0.02)
                assert waiting
            finally:
                release.set()
            assert a.result(timeout=15).status_code == 200
            assert b.result(timeout=15).status_code == (409 if target == "self" else 401)
        with engine.connect() as connection:
            assert len(list(connection.scalars(select(User.id).join(UserRole).join(Role).where(User.status == "active", Role.code == "ADMIN")))) == 1
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause)


@pytest.mark.integration
def test_roles_deferred_commit_failure_is_atomic(admins):
    first, second, ids, engine, _ = admins
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m41b_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred roles audit'; END $$")
            connection.exec_driver_sql("CREATE CONSTRAINT TRIGGER m41b_commit_fail AFTER INSERT ON admin_audit_logs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m41b_commit_fail()")
        assert mutation(first, "PUT", f"/admin/users/{ids[1]}/roles", {"roles": ["USER"]}).status_code == 500
        with engine.connect() as connection:
            assert len(list(connection.scalars(select(UserRole.user_id).join(Role).where(Role.code == "ADMIN")))) == 2
            assert set(connection.scalars(select(AuthSession.revoked_at))) == {None}
            assert list(connection.scalars(select(AdminAuditLog.id))) == []
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER m41b_commit_fail ON admin_audit_logs")
            connection.exec_driver_sql("DROP FUNCTION m41b_commit_fail()")
