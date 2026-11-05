"""Admin Users on real PostgreSQL, rollback fixtures and PII-safe atomic audit."""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.admin_users import AdminCreateUser
from app.models import AdminAuditLog, AuthSession, Comment, Post, Profile, User, UserRole
from test_auth import auth, csrf, login, migrated, register
from test_blog import admin, blog, mutation


PAYLOAD = dict(username="created_user", email="created-user@example.com", password="Synthetic long password!", display_name="Private Name", roles=["USER"])


@pytest.mark.integration
def test_admin_create_user_and_redacted_audit(admin):
    client, connection, actor, *_ = admin
    payload = dict(username="created_admin", email=" Created@EXAMPLE.com ", password="Synthetic long password!", display_name="Private Name", roles=["USER", "ADMIN"])
    response = mutation(client, "POST", "/admin/users", payload)
    assert response.status_code == 201, response.text
    dto = response.json()
    assert set(dto) == {"id", "username", "email", "display_name", "roles", "status"}
    assert dto["email"] == "created@example.com" and dto["roles"] == ["ADMIN", "USER"]
    row = connection.execute(select(User.__table__).where(User.id == UUID(dto["id"]))).mappings().one()
    assert client.app.state.auth.hasher.verify(row["password_hash"], payload["password"])
    audit = connection.execute(select(AdminAuditLog.__table__).where(AdminAuditLog.target_type == "user")).mappings().one()
    assert audit["actor_id"] == actor and audit["target_id"] == dto["id"]
    assert all(value not in str(audit) for value in [payload["password"], row["password_hash"], dto["email"], payload["display_name"]])


@pytest.mark.integration
def test_last_admin_cannot_be_disabled_or_deleted(admin):
    client, connection, actor, *_ = admin
    for method, payload in [("PATCH", {"status": "locked"}), ("DELETE", None)]:
        response = mutation(client, method, "/admin/users/" + str(actor), payload)
        assert response.status_code == 409, response.text
    assert connection.scalar(select(User.status).where(User.id == actor)) == "active"
    assert connection.execute(select(AdminAuditLog.id)).all() == []


@pytest.mark.integration
@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
@pytest.mark.parametrize("identity", ["anonymous", "user"])
def test_admin_users_rbac(blog, method, identity):
    client, connection, user_id, *_ = blog
    if identity == "anonymous": client.cookies.clear()
    path = "/admin/users" + ("/" + str(user_id) if method in {"PATCH", "DELETE"} else "")
    payload = PAYLOAD if method == "POST" else {"status": "locked"} if method == "PATCH" else None
    if method == "GET": response = client.get("/api/v1" + path)
    else: response = mutation(client, method, path, payload)
    assert response.status_code == (401 if identity == "anonymous" else 403), response.text


@pytest.mark.integration
@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
@pytest.mark.parametrize("problem", ["missing_csrf", "csrf", "origin"])
def test_admin_users_mutation_csrf(admin, method, problem):
    client, _, actor, *_ = admin
    path = "/api/v1/admin/users" + ("/" + str(actor) if method != "POST" else "")
    headers = {"Origin": "https://evil.example" if problem == "origin" else "https://testserver",
               "X-CSRF-Token": "bad" if problem == "csrf" else csrf(client)}
    if problem == "missing_csrf": headers.pop("X-CSRF-Token")
    response = client.request(method, path, json=PAYLOAD if method == "POST" else {"status": "locked"}, headers=headers)
    assert response.status_code == 403


@pytest.mark.integration
def test_list_search_filter_page_and_private_whitelist(admin):
    client, connection, actor, *_ = admin
    for index in range(3):
        assert mutation(client, "POST", "/admin/users", PAYLOAD | {"username": "created_" + str(index), "email": f"created{index}@example.com"}).status_code == 201
    result = client.get("/api/v1/admin/users?search=created&page_size=2").json()
    assert result["pagination"] == dict(page=1, page_size=2, total=3, total_pages=2)
    assert [row["username"] for row in result["items"]] == ["created_0", "created_1"]
    assert all(set(row) == {"id", "username", "email", "display_name", "roles", "status"} for row in result["items"])
    assert client.get("/api/v1/admin/users?search=%25").json()["items"] == []
    assert client.get("/api/v1/admin/users?search=Private%20Name").json()["pagination"]["total"] == 3
    assert client.get("/api/v1/admin/users?search=created0%40example.com").json()["pagination"]["total"] == 1
    assert client.get("/api/v1/admin/users?status=unknown").json()["items"] == []
    assert client.get("/api/v1/admin/users?page=" + str(10**40)).json()["items"] == []
    for query in ("page=0", "page_size=0", "page_size=101", "search=" + "x" * 101):
        assert client.get("/api/v1/admin/users?" + query).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize("payload", [{}, {"status": None}, {"status": "deleted"}, {"roles": ["ADMIN"]},
    {"password": "forged"}, {"user_id": "forged"}, {"display_name": " "}, {"display_name": "x\x00"},
    {"email": None}, {"email": "bad"}])
def test_patch_input_allowlist(admin, payload):
    client, _, actor, *_ = admin
    assert mutation(client, "PATCH", "/admin/users/" + str(actor), payload).status_code == 422


@pytest.mark.integration
def test_patch_identity_revoke_and_soft_delete_preserve_rows(admin):
    client, connection, actor, *_ = admin
    dto = mutation(client, "POST", "/admin/users", PAYLOAD).json()
    ident = UUID(dto["id"])
    from fastapi.testclient import TestClient
    from app.main import app
    other = TestClient(app, base_url="https://testserver")
    try:
        assert login(other, email=PAYLOAD["email"], password=PAYLOAD["password"]).status_code == 200
        assert mutation(client, "PATCH", "/admin/users/" + str(ident), {"status": "locked"}).status_code == 200
        assert other.get("/api/v1/users/me").status_code == 401
        assert connection.scalar(select(AuthSession.revoked_at).where(AuthSession.user_id == ident)) is not None
        response = mutation(client, "PATCH", "/admin/users/" + str(ident), {"status": "active", "email": " New@EXAMPLE.com ", "display_name": "Updated private"})
        assert response.status_code == 200 and response.json()["email"] == "new@example.com"
        assert other.get("/api/v1/users/me").status_code == 401
        post_id, comment_id = uuid4(), uuid4()
        now = client.app.state.auth.now()
        connection.execute(Post.__table__.insert().values(id=post_id, author_id=ident, category_id=admin[3], title="Preserve", content="Text", status="published", created_at=now, updated_at=now))
        connection.execute(Comment.__table__.insert().values(id=comment_id, post_id=post_id, author_id=ident, body="Preserve", status="visible", created_at=now, updated_at=now))
        assert mutation(client, "DELETE", "/admin/users/" + str(ident)).status_code == 204
        row = connection.execute(select(User.__table__).where(User.id == ident)).mappings().one()
        assert row["status"] == "deleted" and row["deleted_at"] == row["updated_at"]
        assert connection.scalar(select(Profile.user_id).where(Profile.user_id == ident)) == ident
        assert connection.scalar(select(UserRole.user_id).where(UserRole.user_id == ident)) == ident
        assert connection.scalar(select(Post.author_id).where(Post.id == post_id)) == ident
        assert connection.scalar(select(Comment.post_id).where(Comment.id == comment_id)) == post_id
        assert mutation(client, "DELETE", "/admin/users/" + str(ident)).status_code == 404
        assert mutation(client, "PATCH", "/admin/users/" + str(ident), {"status": "active"}).status_code == 404
        assert mutation(client, "POST", "/admin/users", PAYLOAD).status_code == 409
        audits = connection.execute(select(AdminAuditLog.__table__)).mappings().all()
        assert all(PII not in str(audits) for PII in ["new@example.com", "Updated private", PAYLOAD["email"], PAYLOAD["password"]])
    finally:
        other.close()


@pytest.mark.integration
@pytest.mark.parametrize("action", ["create", "patch", "delete"])
def test_audit_failure_rolls_back_all_business_changes(admin, action):
    client, connection, actor, *_ = admin
    dto = mutation(client, "POST", "/admin/users", PAYLOAD).json()
    ident = UUID(dto["id"])
    before = dict(connection.execute(select(User.__table__).where(User.id == ident)).mappings().one())
    count = len(connection.execute(select(AdminAuditLog.id)).all())
    connection.exec_driver_sql("CREATE FUNCTION m41a_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit rejection'; END $$")
    connection.exec_driver_sql("CREATE TRIGGER m41a_reject_audit BEFORE INSERT ON admin_audit_logs FOR EACH ROW EXECUTE FUNCTION m41a_reject_audit()")
    if action == "create":
        response = mutation(client, "POST", "/admin/users", PAYLOAD | {"username": "rollback_user", "email": "rollback@example.com"})
        assert connection.scalar(select(User.id).where(User.username == "rollback_user")) is None
    else:
        response = mutation(client, "PATCH" if action == "patch" else "DELETE", "/admin/users/" + str(ident), {"status": "locked", "display_name": "Rollback"} if action == "patch" else None)
    assert response.status_code == 500
    assert dict(connection.execute(select(User.__table__).where(User.id == ident)).mappings().one()) == before
    assert connection.scalar(select(Profile.display_name).where(Profile.user_id == ident)) == PAYLOAD["display_name"]
    assert len(connection.execute(select(AdminAuditLog.id)).all()) == count


@pytest.mark.integration
@pytest.mark.parametrize("changes", [{"roles": ["ROOT"]}, {"status": "active"}, {"author_id": "forged"}, {"display_name": " "}, {"password": "short"}, {"email": "bad"}])
def test_create_allowlist_and_validation(admin, changes):
    client, _, *_ = admin
    assert mutation(client, "POST", "/admin/users", PAYLOAD | changes).status_code == 422


@pytest.mark.integration
def test_duplicates_unknown_targets_and_roles_contract(admin):
    client, connection, actor, *_ = admin
    dto = mutation(client, "POST", "/admin/users", PAYLOAD | {"roles": []}).json()
    assert dto["roles"] == []  # Contract has no minItems; do not silently grant a role.
    assert mutation(client, "POST", "/admin/users", PAYLOAD).status_code == 409
    response = mutation(client, "POST", "/admin/users", PAYLOAD | {"username": "role_dedup", "email": "dedup@example.com", "roles": ["USER", "USER"]})
    assert response.status_code == 201 and response.json()["roles"] == ["USER"]
    assert mutation(client, "PATCH", "/admin/users/" + response.json()["id"], {"email": PAYLOAD["email"]}).status_code == 409
    for method, payload in [("PATCH", {"status": "locked"}), ("DELETE", None)]:
        assert mutation(client, method, "/admin/users/" + str(uuid4()), payload).status_code == 404
        assert mutation(client, method, "/admin/users/not-a-uuid", payload).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize("parameter", ["search", "status"])
def test_list_rejects_nul_before_postgresql(admin, parameter):
    client, _, *_ = admin
    assert client.get("/api/v1/admin/users?" + parameter + "=%00").status_code == 422
