"""Separate real PostgreSQL connections exercise password/session serialization."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.main import app
from app.models import AuthSession, Profile, Role, User, UserRole
from test_auth import ORIGIN, PASSWORD, csrf, login, migrated, register
from test_account import account_request


@pytest.mark.integration
@pytest.mark.parametrize("race", ["password", "login"])
def test_password_session_races_are_atomic(migrated, monkeypatch, race):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    username = "race_" + uuid4().hex[:16]
    email = username + "@example.com"
    engine = create_engine(migrated.url, hide_parameters=True,
                           connect_args={"options": "-c statement_timeout=10000 -c lock_timeout=3000"})
    user_id = role_id = None
    with TestClient(app, base_url=ORIGIN) as first:
        app.state.auth_session_factory = lambda: Session(engine)
        second = TestClient(app, base_url=ORIGIN)
        try:
            with Session(engine) as db:
                assert db.scalar(select(Role.id).where(Role.code == "USER")) is None
            response = register(first, username=username, email=email)
            assert response.status_code == 201
            user_id = UUID(response.json()["id"])
            with Session(engine) as db:
                role_id = db.scalar(select(Role.id).where(Role.code == "USER"))
            assert login(first, email=email).status_code == 200
            if race == "password":
                assert login(second, email=email).status_code == 200
            a_csrf, b_csrf = csrf(first), csrf(second)
            new_a, new_b = "Alpha replacement password!", "Beta replacement password!"
            with ThreadPoolExecutor(max_workers=2) as executor:
                a = executor.submit(account_request, first, "PUT", "/me/password",
                                    {"current_password": PASSWORD, "new_password": new_a}, a_csrf)
                if race == "password":
                    b = executor.submit(account_request, second, "PUT", "/me/password",
                                        {"current_password": PASSWORD, "new_password": new_b}, b_csrf)
                else:
                    b = executor.submit(second.post, "/api/v1/auth/login", json={"email": email, "password": PASSWORD},
                                        headers={"Origin": ORIGIN, "X-CSRF-Token": b_csrf})
                statuses = [a.result(timeout=15).status_code, b.result(timeout=15).status_code]
            if race == "password":
                assert sorted(statuses) == [204, 401]
                winner = first if statuses[0] == 204 else second
                loser = second if winner is first else first
                winning_password = new_a if winner is first else new_b
                assert winner.get("/api/v1/users/me").status_code == 200
                assert loser.get("/api/v1/users/me").status_code == 401
            else:
                assert statuses[0] == 204 and statuses[1] in {200, 401}
                winning_password = new_a
                assert first.get("/api/v1/users/me").status_code == 200
                if statuses[1] == 200:
                    assert second.get("/api/v1/users/me").status_code == 401
            with Session(engine) as db:
                user = db.get(User, user_id)
                assert app.state.auth.hasher.verify(user.password_hash, winning_password)
                assert not app.state.auth.verify_password(user.password_hash, PASSWORD)
                assert len(db.scalars(select(AuthSession).where(AuthSession.user_id == user_id,
                                                               AuthSession.revoked_at.is_(None))).all()) == 1
        finally:
            with Session(engine) as db, db.begin():
                # Resolve only this UUID-prefixed identity if the request committed before a failure.
                own_id = user_id or db.scalar(select(User.id).where(User.username == username))
                if own_id:
                    for model, column in [(AuthSession, AuthSession.user_id), (UserRole, UserRole.user_id),
                                          (Profile, Profile.user_id), (User, User.id)]:
                        db.execute(model.__table__.delete().where(column == own_id))
                if role_id:
                    assert db.scalar(select(UserRole.user_id).where(UserRole.role_id == role_id)) is None
                    db.execute(Role.__table__.delete().where(Role.id == role_id))
            second.close()
            engine.dispose()
