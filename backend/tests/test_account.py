"""Account/authorization integration uses existing P0 schema and transaction rollback."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.main import app
from app.models import AuthSession, MediaUpload, Profile, Role, User, UserRole
from app.permissions import require_role
from test_auth import ACCOUNT, ORIGIN, PASSWORD, auth, csrf, login, migrated, post, register


PRIVATE = {"id", "username", "email", "display_name", "roles", "status", "birth_year", "address",
           "phone", "bio", "avatar_media_id", "cover_media_id", "avatar_url", "cover_url"}
PUBLIC = {"id", "username", "display_name", "bio", "avatar_url", "cover_url", "created_at"}
NEW_PASSWORD = "Replacement password for test!"


def account_request(client, method, path="/me", payload=None, token=None, origin=ORIGIN):
    return client.request(method, "/api/v1/users" + path, json=payload,
                          headers={"Origin": origin, "X-CSRF-Token": token or csrf(client)})


def signed_in(client):
    created = register(client)
    assert created.status_code == 201
    assert set(created.json()) == {"id", "username", "email", "display_name", "roles", "status"}
    logged_in = login(client)
    assert logged_in.status_code == 200 and set(logged_in.json()) == set(created.json())
    return UUID(created.json()["id"])


@pytest.mark.integration
def test_private_me_route_fields_and_sliding_expiry(auth):
    client, connection = auth
    assert client.get("/api/v1/users/me").status_code == 401
    user_id = signed_in(client)
    clock = client.app.state.auth.now()
    client.app.state.auth.now = lambda: clock + timedelta(minutes=20)
    response = client.get("/api/v1/users/me")
    assert response.status_code == 200 and set(response.json()) == PRIVATE
    assert response.json()["id"] == str(user_id)
    assert response.json()["roles"] == ["USER"]
    assert "password_hash" not in response.text and PASSWORD not in response.text
    assert connection.execute(text("SELECT expires_at FROM auth_sessions")).scalar_one() == clock + timedelta(minutes=50)
    assert "Max-Age=1800" in response.headers["set-cookie"]


@pytest.mark.integration
def test_patch_nullable_omitted_and_owner_only(auth):
    client, connection = auth
    user_id = signed_in(client)
    clock = client.app.state.auth.now
    with TestClient(app, base_url=ORIGIN) as other:
        # Use the same rollback sandbox with independent browser cookies.
        from sqlalchemy.orm import Session
        other.app.state.auth_session_factory = lambda: Session(bind=connection, join_transaction_mode="create_savepoint")
        other.app.state.auth.now = clock
        other_id = UUID(register(other, username="bob_account", email="bob@example.com").json()["id"])
        assert login(other, email="bob@example.com").status_code == 200
        assert account_request(client, "PATCH", payload={"user_id": str(other_id), "display_name": "Hijacked"}).status_code == 422
        response = account_request(client, "PATCH", payload={"display_name": "New Alice", "bio": "Bio", "phone": "123", "birth_year": 1990})
        assert response.status_code == 200
        response = account_request(client, "PATCH", payload={"bio": None, "birth_year": None})
        assert response.status_code == 200 and response.json()["bio"] is None
        assert response.json()["birth_year"] is None
        assert response.json()["phone"] == "123"
        assert connection.execute(text("SELECT display_name FROM profiles WHERE user_id=:id"), {"id": other_id}).scalar_one() == "Alice"
        assert connection.execute(text("SELECT display_name FROM profiles WHERE user_id=:id"), {"id": user_id}).scalar_one() == "New Alice"


@pytest.mark.integration
@pytest.mark.parametrize("payload", [
    {}, {"roles": ["ADMIN"]}, {"status": "active"}, {"user_id": str(uuid4())}, {"unknown": "x"},
    {"email": "changed@example.com"}, {"display_name": "   "}, {"display_name": None},
    {"display_name": "x" * 81}, {"birth_year": 1899}, {"birth_year": 9999}, {"birth_year": True},
    {"bio": "x" * 1001}, {"address": "x" * 256}, {"phone": "x" * 31}, {"bio": "\x00"},
])
def test_patch_rejects_invalid_and_extra_fields(auth, payload):
    client, connection = auth
    signed_in(client)
    before = connection.execute(text("SELECT display_name,bio,birth_year,address,phone FROM profiles")).all()
    response = account_request(client, "PATCH", payload=payload)
    assert response.status_code == 422 and response.json()["error"]["request_id"]
    assert connection.execute(text("SELECT display_name,bio,birth_year,address,phone FROM profiles")).all() == before
    assert connection.execute(text("SELECT code FROM roles")).scalar_one() == "USER"


@pytest.mark.integration
@pytest.mark.parametrize("field", ["avatar_media_id", "cover_media_id"])
@pytest.mark.parametrize("kind", ["owned_ready", "owned_pending", "other_owner", "missing"])
def test_media_owner_and_ready(auth, field, kind):
    client, connection = auth
    user_id = signed_in(client)
    now = client.app.state.auth.now()
    media_id = uuid4()
    owner = user_id
    if kind == "other_owner":
        owner = uuid4()
        connection.execute(User.__table__.insert().values(id=owner, username="foreign_user", email="foreign@example.com",
            password_hash="synthetic-hash", status="active", created_at=now, updated_at=now))
    if kind != "missing":
        connection.execute(MediaUpload.__table__.insert().values(id=media_id, owner_id=owner, object_key="test/" + str(media_id),
            mime="image/png", size_bytes=1, status="pending" if kind == "owned_pending" else "ready", created_at=now, updated_at=now))
    response = account_request(client, "PATCH", payload={field: str(media_id)})
    assert response.status_code == (200 if kind == "owned_ready" else 422)
    if kind == "owned_ready":
        assert response.json()[field] == str(media_id)
        assert account_request(client, "PATCH", payload={field: None}).json()[field] is None


@pytest.mark.integration
@pytest.mark.parametrize("path,method", [("/me", "PATCH"), ("/me/password", "PUT")])
def test_account_mutations_require_csrf_origin(auth, path, method):
    client, _ = auth
    signed_in(client)
    payload = {"bio": "new"} if method == "PATCH" else {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert client.request(method, "/api/v1/users" + path, json=payload, headers={"Origin": ORIGIN}).status_code == 403
    assert account_request(client, method, path, payload, token="forged").status_code == 403
    assert account_request(client, method, path, payload, origin="https://evil.example").status_code == 403
    assert client.request(method, "/api/v1/users" + path, json=payload, headers={"X-CSRF-Token": csrf(client)}).status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize("status", ["active", "locked", "deleted", "missing"])
def test_public_profile_no_pii(auth, status):
    client, connection = auth
    user_id = signed_in(client)
    connection.execute(text("UPDATE profiles SET bio='Public bio',phone='private-phone',address='private-address',birth_year=1990 WHERE user_id=:id"), {"id": user_id})
    if status in ["locked", "deleted"]:
        connection.execute(text("UPDATE users SET status=:status,deleted_at=CASE WHEN :status='deleted' THEN created_at ELSE NULL END WHERE id=:id"), {"status": status, "id": user_id})
    client.cookies.clear()
    response = client.get("/api/v1/users/" + ("unknown_user" if status == "missing" else ACCOUNT["username"]))
    assert response.status_code == (200 if status == "active" else 404)
    if status == "active":
        assert set(response.json()) == PUBLIC and response.json()["avatar_url"] is None
        assert response.json()["bio"] == "Public bio"
    assert not any(secret in response.text for secret in [ACCOUNT["email"], "private-phone", "private-address", "password_hash", "roles", "birth_year"])


@pytest.mark.integration
@pytest.mark.parametrize("status", ["locked", "deleted"])
def test_locked_deleted_cannot_access_private(auth, status):
    client, connection = auth
    signed_in(client)
    token = csrf(client)
    connection.execute(text("UPDATE users SET status=:status,deleted_at=CASE WHEN :status='deleted' THEN created_at ELSE NULL END"), {"status": status})
    assert client.get("/api/v1/users/me").status_code == 401
    assert account_request(client, "PATCH", payload={"bio": "no"}, token=token).status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize("role", [None, "USER", "ADMIN"])
def test_rbac_dependency_with_real_database(auth, role):
    client, connection = auth
    if role:
        user_id = signed_in(client)
        if role == "ADMIN":
            role_id = uuid4()
            connection.execute(Role.__table__.insert().values(id=role_id, code="ADMIN", description="Synthetic test admin"))
            connection.execute(UserRole.__table__.insert().values(user_id=user_id, role_id=role_id, granted_at=client.app.state.auth.now()))
    # Only this local test app has a probe route; no admin/test endpoint is shipped.
    probe = FastAPI()
    probe.state.auth = client.app.state.auth
    probe.state.auth_session_factory = client.app.state.auth_session_factory
    probe.exception_handlers = app.exception_handlers.copy()
    @probe.get("/probe")
    def guarded(account=Depends(require_role("ADMIN"))):
        return {"allowed": True}
    with TestClient(probe, base_url=ORIGIN) as check:
        check.cookies.update(client.cookies)
        response = check.get("/probe")
    assert response.status_code == (401 if role is None else 200 if role == "ADMIN" else 403)
    assert not any("probe" in path for path in app.openapi()["paths"])


@pytest.mark.integration
def test_password_change_preserves_current_and_revokes_other(auth):
    client, connection = auth
    signed_in(client)
    from sqlalchemy.orm import Session
    clock = client.app.state.auth.now
    with TestClient(app, base_url=ORIGIN) as other:
        other.app.state.auth_session_factory = lambda: Session(bind=connection, join_transaction_mode="create_savepoint")
        other.app.state.auth.now = clock
        assert login(other).status_code == 200
        first_raw = client.cookies.get("am_session"); other_csrf = csrf(other)
        response = account_request(client, "PUT", "/me/password", {"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        assert response.status_code == 204 and response.content == b""
        assert client.cookies.get("am_session") == first_raw
        assert client.get("/api/v1/users/me").status_code == 200
        assert account_request(other, "PATCH", payload={"bio": "no"}, token=other_csrf).status_code == 401
        assert connection.execute(text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL")).scalar_one() == 1
        assert post(client, "logout").status_code == 204
        assert login(client, password=PASSWORD).status_code == 401
        assert login(client, password=NEW_PASSWORD).status_code == 200


@pytest.mark.integration
@pytest.mark.parametrize("current,new,status", [("wrong", NEW_PASSWORD, 403), (PASSWORD, "short", 422), (PASSWORD, "x" * 129, 422)])
def test_bad_password_change_does_not_modify_or_revoke(auth, current, new, status):
    client, connection = auth
    user_id = signed_in(client)
    now = client.app.state.auth.now()
    connection.execute(AuthSession.__table__.insert().values(id=uuid4(), user_id=user_id, token_hash=uuid4().hex * 2,
        created_at=now, expires_at=now + timedelta(minutes=30)))
    before = connection.execute(text("SELECT password_hash,updated_at FROM users")).one()
    response = account_request(client, "PUT", "/me/password", {"current_password": current, "new_password": new})
    assert response.status_code == status
    assert connection.execute(text("SELECT password_hash,updated_at FROM users")).one() == before
    assert connection.execute(text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL")).scalar_one() == 0
    assert current not in response.text and new not in response.text


@pytest.mark.integration
def test_password_transaction_failure_rolls_back(auth):
    client, connection = auth
    user_id = signed_in(client)
    now = client.app.state.auth.now()
    connection.execute(AuthSession.__table__.insert().values(id=uuid4(), user_id=user_id, token_hash=uuid4().hex * 2,
        created_at=now, expires_at=now + timedelta(minutes=30)))
    before = connection.execute(text("SELECT password_hash FROM users")).scalar_one()
    connection.exec_driver_sql("CREATE FUNCTION public.m22_fail_password() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$")
    connection.exec_driver_sql("CREATE TRIGGER m22_fail BEFORE UPDATE OF revoked_at ON auth_sessions FOR EACH ROW EXECUTE FUNCTION public.m22_fail_password()")
    response = account_request(client, "PUT", "/me/password", {"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert response.status_code == 500 and "synthetic failure" not in response.text
    assert connection.execute(text("SELECT password_hash FROM users")).scalar_one() == before
    assert connection.execute(text("SELECT count(*) FROM auth_sessions WHERE revoked_at IS NOT NULL")).scalar_one() == 0


@pytest.mark.integration
def test_password_change_rate_limit_and_body_cap(auth):
    client, _ = auth
    signed_in(client)
    token = csrf(client)
    responses = [account_request(client, "PUT", "/me/password", {"current_password": "wrong", "new_password": NEW_PASSWORD}, token=token) for _ in range(6)]
    assert responses[-1].status_code == 429 and int(responses[-1].headers["retry-after"]) > 0
    response = client.patch("/api/v1/users/me", content=b"x" * 16385)
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize("method,path,payload", [
    ("PATCH", "/me", {"bio": "no"}),
    ("PUT", "/me/password", {"current_password": PASSWORD, "new_password": NEW_PASSWORD}),
])
def test_account_mutations_require_authenticated_session(auth, method, path, payload):
    client, _ = auth
    assert account_request(client, method, path, payload).status_code == 401
