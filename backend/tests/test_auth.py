"""Authentication against real PostgreSQL; each normal case rolls back its writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings, load_settings
from app.db import create_db_engine
from app.main import app
from app.models import AuthSession, Profile, Role, User, UserRole
from test_migrations import TABLES, REVISION, development_inventory
from schema_guard import assert_auxiliary_objects


ORIGIN = "https://testserver"
PASSWORD = "Correct horse battery staple!"
ACCOUNT = dict(username="alice_auth", email="alice@example.com", password=PASSWORD, display_name="Alice")


@pytest.fixture(scope="module")
def migrated():
    """Auth tests require the existing schema; they never upgrade/drop/reset tables."""
    import os
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL missing; PostgreSQL Auth was NOT TESTED")
    engine = create_db_engine(Settings(_env_file=None, database_url=url))
    dev = create_db_engine(load_settings())
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT current_database()")).scalar_one() == "aurameme_test"
            assert connection.execute(text("SELECT current_schema()")).scalar_one() == "public"
            from sqlalchemy import inspect
            assert set(inspect(connection).get_table_names()) == TABLES | {"alembic_version"}
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
            assert_auxiliary_objects(connection)
            assert connection.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname='public'")).scalar_one() == 0
            for table in TABLES:
                assert connection.execute(text('SELECT count(*) FROM "' + table + '"')).scalar_one() == 0, "Existing data; refusing Auth tests"
        before = development_inventory(dev)
        yield engine
        with engine.connect() as connection:
            for table in TABLES:
                assert connection.execute(text('SELECT count(*) FROM "' + table + '"')).scalar_one() == 0, "Auth test data leaked"
        assert development_inventory(dev) == before
    finally:
        engine.dispose()
        dev.dispose()


@pytest.fixture
def auth(migrated, monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    with migrated.connect() as connection, connection.begin() as transaction:
        with TestClient(app, base_url=ORIGIN) as client:
            client.app.state.auth_session_factory = lambda: Session(bind=connection, join_transaction_mode="create_savepoint")
            client.app.state.auth.now = lambda: datetime(2026, 11, 4, tzinfo=timezone.utc)
            yield client, connection
        transaction.rollback()


def csrf(client):
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def post(client, path, payload=None, token=None, origin=ORIGIN):
    return client.post("/api/v1/auth/" + path, json=payload,
                       headers={"Origin": origin, "X-CSRF-Token": token or csrf(client)})


def register(client, **changes):
    return post(client, "register", ACCOUNT | changes)


def login(client, **changes):
    return post(client, "login", {"email": ACCOUNT["email"], "password": PASSWORD} | changes)


@pytest.mark.integration
def test_register_hash_role_profile_no_auto_login(auth):
    client, connection = auth
    response = register(client, email=" Alice@EXAMPLE.com ")
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"
    assert response.json()["roles"] == ["USER"]
    assert "am_session" not in client.cookies
    with Session(connection) as db:
        user = db.scalars(select(User)).one()
        assert user.password_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
        assert client.app.state.auth.hasher.verify(user.password_hash, PASSWORD)
        assert db.get(Profile, user.id).display_name == "Alice"
        assert db.scalars(select(Role.code)).all() == ["USER"]
        assert db.scalars(select(UserRole.user_id)).all() == [user.id]
    assert PASSWORD not in response.text and "password_hash" not in response.text


@pytest.mark.integration
@pytest.mark.parametrize("changes,status", [
    ({"username": "Bad Name"}, 422), ({"username": "a"}, 422),
    ({"password": "short"}, 422), ({"password": "x" * 129}, 422),
    ({"display_name": "   "}, 422), ({"email": "bad"}, 422),
])
def test_registration_validation(auth, changes, status):
    client, connection = auth
    response = register(client, **changes)
    assert response.status_code == status
    assert set(response.json()["error"]) >= {"code", "message", "request_id"}
    assert PASSWORD not in response.text
    assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


@pytest.mark.integration
@pytest.mark.parametrize("changes", [{"email": "other@example.com"}, {"username": "other_auth"}])
def test_duplicates(auth, changes):
    client, _ = auth
    assert register(client).status_code == 201
    assert register(client, **changes).status_code == 409


@pytest.mark.integration
def test_login_cookie_and_two_devices_logout(auth):
    client, connection = auth
    assert register(client).status_code == 201
    pre = csrf(client)
    assert login(client).status_code == 200
    first = client.cookies.get("am_session")
    # A separate browser profile starts with a fresh pre-session.
    with TestClient(app, base_url=ORIGIN) as other:
        other.app.state.auth_session_factory = lambda: Session(bind=connection, join_transaction_mode="create_savepoint")
        other.app.state.auth.now = lambda: datetime(2026, 11, 4, tzinfo=timezone.utc)
        login_response = login(other)
        assert login_response.status_code == 200
        second = other.cookies.get("am_session")
        assert first != second
        headers = login_response.headers["set-cookie"]
        for flag in ["HttpOnly", "Secure", "SameSite=lax", "Path=/"]:
            assert flag in headers
        assert "Domain=" not in headers
        assert first not in login_response.text and second not in login_response.text
        assert post(client, "logout", token=pre).status_code == 403
        wrong_session = csrf(other)
        assert post(client, "logout", token=wrong_session).status_code == 403
        assert post(client, "logout").status_code == 204
        client.cookies.set("am_session", first, domain="testserver.local", path="/")
        assert post(client, "logout", token=wrong_session).status_code == 401
        assert post(other, "logout").status_code == 204
    digests = connection.execute(text("SELECT token_hash FROM auth_sessions")).scalars().all()
    assert first not in digests and second not in digests
    assert len(digests) == 2 and all(len(value) == 64 for value in digests)


@pytest.mark.integration
def test_wrong_credentials_and_locked_deleted(auth):
    client, connection = auth
    assert register(client).status_code == 201
    wrong = login(client, password="wrong"); missing = login(client, email="nobody@example.com")
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]
    connection.execute(text("UPDATE users SET status='locked'"))
    assert login(client).status_code == 401
    connection.execute(text("UPDATE users SET status='deleted',deleted_at=created_at"))
    assert login(client).status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize("endpoint", ["register", "login", "logout"])
def test_csrf_and_origin_rejections(auth, endpoint):
    client, _ = auth
    assert register(client).status_code == 201
    if endpoint == "logout":
        assert login(client).status_code == 200
    payload = ACCOUNT if endpoint == "register" else {"email": ACCOUNT["email"], "password": PASSWORD}
    assert client.post("/api/v1/auth/" + endpoint, json=payload, headers={"Origin": ORIGIN}).status_code == 403
    assert post(client, endpoint, payload, token="forged").status_code == 403
    assert post(client, endpoint, payload, origin="https://evil.test").status_code == 403
    assert client.post("/api/v1/auth/" + endpoint, json=payload, headers={"X-CSRF-Token": csrf(client)}).status_code == 403


@pytest.mark.integration
def test_pre_session_bound_expires_and_is_consumed(auth):
    client, _ = auth
    old = csrf(client)
    client.cookies.clear()
    assert post(client, "register", ACCOUNT, token=old).status_code == 403
    csrf(client)
    assert post(client, "register", ACCOUNT, token=old).status_code == 403
    assert register(client).status_code == 201
    old = csrf(client); pre_cookie = client.cookies.get(client.app.state.auth.pre_cookie)
    assert login(client).status_code == 200
    client.cookies.clear()
    client.cookies.set(client.app.state.auth.pre_cookie, pre_cookie, domain="testserver.local", path="/")
    assert post(client, "login", ACCOUNT, token=old).status_code == 403
    fresh = csrf(client)
    client.app.state.auth.now = lambda: datetime(2026, 11, 4, tzinfo=timezone.utc) + timedelta(minutes=11)
    assert post(client, "login", ACCOUNT, token=fresh).status_code == 403
    assert csrf(client) != fresh  # Public GET renews an expired pre-session.


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["idle", "absolute", "revoked", "cookie"])
def test_session_expiry(auth, kind):
    client, connection = auth
    assert register(client).status_code == 201
    assert login(client).status_code == 200
    token = csrf(client)
    if kind == "idle":
        client.app.state.auth.now = lambda: datetime(2026, 11, 4, tzinfo=timezone.utc) + timedelta(minutes=30)
    elif kind == "absolute":
        connection.execute(text("UPDATE auth_sessions SET created_at=created_at-interval '12 hours',expires_at=expires_at+interval '12 hours'"))
    elif kind == "revoked":
        connection.execute(text("UPDATE auth_sessions SET revoked_at=created_at"))
    else:
        client.cookies.clear()
    assert post(client, "logout", token=token).status_code == 401


@pytest.mark.integration
def test_sliding_session_and_absolute_cap(auth):
    client, connection = auth
    assert register(client).status_code == 201
    assert login(client).status_code == 200
    clock = datetime(2026, 11, 4, tzinfo=timezone.utc)
    client.app.state.auth.now = lambda: clock + timedelta(minutes=20)
    csrf(client)
    expiry = connection.execute(text("SELECT expires_at FROM auth_sessions")).scalar_one()
    assert expiry == clock + timedelta(minutes=50)
    connection.execute(text("UPDATE auth_sessions SET created_at=created_at-interval '11 hours 30 minutes'"))
    client.app.state.auth.now = lambda: clock + timedelta(minutes=25)
    csrf(client)
    assert connection.execute(text("SELECT expires_at FROM auth_sessions")).scalar_one() == clock + timedelta(minutes=30)


@pytest.mark.integration
def test_rate_limit_has_429_and_retry_after(auth):
    client, _ = auth
    responses = [login(client, password="wrong") for _ in range(11)]
    assert responses[-1].status_code == 429
    assert int(responses[-1].headers["retry-after"]) > 0


@pytest.mark.integration
def test_transaction_rolls_back_profile_failure(auth):
    client, connection = auth
    # A real PostgreSQL trigger raises after the user and role inserts; transaction must undo all.
    connection.exec_driver_sql("CREATE FUNCTION public.m21_fail_profile() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$")
    connection.exec_driver_sql("CREATE TRIGGER m21_fail BEFORE INSERT ON profiles FOR EACH ROW EXECUTE FUNCTION public.m21_fail_profile()")
    response = register(client)
    assert response.status_code == 500
    assert "synthetic failure" not in response.text
    for table in ["users", "roles", "profiles", "user_roles"]:
        assert connection.execute(text("SELECT count(*) FROM " + table)).scalar_one() == 0


def test_missing_auth_key_is_fail_safe(monkeypatch):
    from app.config import AuthSettings
    from pydantic import ValidationError
    monkeypatch.delenv("AUTH_SIGNING_KEY", raising=False)
    with pytest.raises(ValidationError):
        AuthSettings(_env_file=None)


@pytest.mark.integration
def test_parallel_first_registrations_create_one_user_role(migrated, monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    names = ["parallel_" + uuid4().hex[:16] for _ in range(4)]
    with TestClient(app, base_url=ORIGIN):
        app.state.auth_session_factory = lambda: Session(migrated)
        clients = [TestClient(app, base_url=ORIGIN) for _ in names]
        with migrated.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM roles")).scalar_one() == 0
        try:
            for client in clients:
                csrf(client)
            def create(item):
                client, name = item
                return register(client, username=name, email=name + "@example.com")
            with ThreadPoolExecutor(max_workers=4) as executor:
                responses = list(executor.map(create, zip(clients, names)))
            assert [response.status_code for response in responses] == [201] * 4
            with Session(migrated) as db:
                assert db.scalars(select(Role.code)).all() == ["USER"]
                users = db.scalars(select(User).where(User.username.in_(names))).all()
                assert len(users) == 4
                assert len(db.scalars(select(UserRole).where(UserRole.user_id.in_([u.id for u in users]))).all()) == 4
            # Session updates and logout race over real independent DB connections.
            first = clients[0]
            assert login(first, email=names[0] + "@example.com").status_code == 200
            token = csrf(first)
            raw = first.cookies.get("am_session")
            second = clients[1]
            second.cookies.set("am_session", raw, domain="testserver.local", path="/")
            with ThreadPoolExecutor(max_workers=2) as executor:
                a = executor.submit(first.get, "/api/v1/auth/csrf")
                b = executor.submit(post, second, "logout", None, token)
                assert a.result().status_code == 200
                assert b.result().status_code == 204
            assert post(first, "logout", token=token).status_code == 401
        finally:
            # Only UUID-prefixed test identities created above; never reset unrelated data.
            with Session(migrated) as db, db.begin():
                ids = db.scalars(select(User.id).where(User.username.in_(names))).all()
                for model, column in [(AuthSession, AuthSession.user_id), (UserRole, UserRole.user_id), (Profile, Profile.user_id), (User, User.id)]:
                    db.execute(model.__table__.delete().where(column.in_(ids)))
                role = db.scalars(select(Role).where(Role.code == "USER")).one_or_none()
                if role and db.scalars(select(UserRole).where(UserRole.role_id == role.id)).first() is None:
                    db.delete(role)
            for client in clients:
                client.close()
