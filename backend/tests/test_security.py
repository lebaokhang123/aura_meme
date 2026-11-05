"""Small deterministic tests for secret validation and bounded auth primitives."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr, ValidationError
from fastapi.testclient import TestClient

from app.config import AuthSettings
from app.main import app
from app.security import AuthError, AuthRuntime, RateLimiter


KEY = "synthetic-only-random-like-key-at-least-32-bytes"


def runtime():
    return AuthRuntime(AuthSettings(_env_file=None, auth_signing_key=SecretStr(KEY)))


@pytest.mark.parametrize("changes", [
    {"auth_signing_key": "short"},
    {"auth_signing_key": "CHANGE_ME_TO_A_RANDOM_SECRET_OF_AT_LEAST_32_BYTES"},
    {"auth_allowed_origins": ["*"]}, {"auth_allowed_origins": []},
    {"auth_allowed_origins": ["http://localhost:8000"]},
    {"auth_allowed_origins": ["https://example.com/path"]},
    {"auth_environment": "development", "auth_allowed_origins": ["http://example.com"]},
])
def test_auth_configuration_fails_closed(changes):
    with pytest.raises(ValidationError) as error:
        AuthSettings(_env_file=None, **({"auth_signing_key": KEY} | changes))
    assert KEY not in str(error.value)


def test_csrf_is_bound_to_server_session_and_rejects_malformed_tokens():
    auth = runtime()
    token = auth.csrf("session:one")
    auth.verify_csrf(token, "session:one")
    for candidate in [token, "x", "é" * 108, "a" * 108, None]:
        with pytest.raises(AuthError) as error:
            auth.verify_csrf(candidate, "session:two")
        assert error.value.status == 403


def test_presession_expires_is_consumed_and_memory_is_bounded():
    auth = runtime()
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    auth.now = lambda: now
    raw = auth.pre_session(None, create=True)
    assert auth.pre_session(raw) == raw
    auth.consume_pre(raw)
    with pytest.raises(AuthError):
        auth.pre_session(raw)
    raw = auth.pre_session(None, create=True)
    auth.now = lambda: now + timedelta(seconds=600)
    with pytest.raises(AuthError):
        auth.pre_session(raw)
    assert auth.pre_session(None, create=True) != raw
    auth.pre_sessions = {str(n): auth.now().timestamp() + 600 for n in range(4096)}
    with pytest.raises(AuthError) as error:
        auth.pre_session(None, create=True)
    assert error.value.status == 429


def test_limiter_window_recovers_without_sleep_and_capacity_fails_closed():
    limiter = RateLimiter()
    limiter.clock = lambda: 10
    limiter.check("key", 1, 60)
    with pytest.raises(AuthError) as error:
        limiter.check("key", 1, 60)
    assert error.value.retry_after == 60
    limiter.clock = lambda: 70
    limiter.check("key", 1, 60)
    for n in range(4095):
        limiter.check(str(n), 1, 60)
    with pytest.raises(AuthError) as error:
        limiter.check("extra", 1, 60)
    assert error.value.status == 429


def test_passwords_are_not_silently_truncated():
    auth = runtime()
    raw = "Đ" * 128
    encoded = auth.hasher.hash(raw)
    assert auth.verify_password(encoded, raw)
    assert not auth.verify_password(encoded, raw + "a")
    assert not auth.verify_password(encoded, raw[:-1])


@pytest.mark.parametrize("mode,base_url,expected,secure", [
    ("production", "http://localhost:8000", 403, False),
    ("production", "https://localhost:8000", 200, True),
    ("development", "http://localhost:8000", 200, False),
])
def test_cookie_transport_and_origin_policy(monkeypatch, mode, base_url, expected, secure):
    monkeypatch.setenv("AUTH_SIGNING_KEY", KEY)
    monkeypatch.setenv("AUTH_ENVIRONMENT", mode)
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["' + ("http://localhost:8000" if mode == "development" else "https://localhost:8000") + '"]')
    with TestClient(app, base_url=base_url) as client:
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == expected
        if expected == 200:
            assert ("Secure" in response.headers["set-cookie"]) == secure
            assert "HttpOnly" in response.headers["set-cookie"]
            assert "Domain=" not in response.headers["set-cookie"]
            assert response.headers["cache-control"] == "no-store"
            assert client.post("/api/v1/auth/register", content=b"x" * 16385).status_code == 422
            assert client.post("/api/v1/auth/register", content=iter([b"x" * 9000, b"y" * 9000])).status_code == 422


def test_unavailable_database_and_malformed_request_do_not_expose_secrets(monkeypatch, caplog):
    monkeypatch.setenv("AUTH_SIGNING_KEY", KEY)
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://localhost:8000"]')
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:synthetic-secret-marker@127.0.0.1:1/aurameme_test")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "1")
    with TestClient(app, base_url="https://localhost:8000") as client:
        token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        headers = {"Origin": "https://localhost:8000", "X-CSRF-Token": token}
        response = client.post("/api/v1/auth/register", headers=headers, json={
            "username": "alice", "email": "alice@example.com", "password": "synthetic-password-marker", "display_name": "Alice"})
        assert response.status_code == 500
        assert not any(value in response.text + caplog.text for value in [KEY, "synthetic-secret-marker", "synthetic-password-marker", "Traceback", "postgresql+"])
        response = client.post("/api/v1/auth/register", headers=headers, content='{"password":"synthetic-password-marker"')
        assert response.status_code == 422
        assert "synthetic-password-marker" not in response.text


def test_auth_startup_configuration_failure_redacts_secret(monkeypatch):
    from app.config import ConfigurationError
    monkeypatch.setenv("AUTH_SIGNING_KEY", "short-secret")
    with pytest.raises(ConfigurationError) as error:
        with TestClient(app):
            pass
    assert "short-secret" not in str(error.value)


def test_invalid_unicode_password_is_rejected_before_hashing():
    from app.auth_schemas import LoginInput
    with pytest.raises(ValidationError):
        LoginInput(email="alice@example.com", password="\ud800" * 12)


def test_origin_and_referer_require_exact_trusted_origin():
    from types import SimpleNamespace
    from starlette.requests import Request
    from app.auth import origin_guard
    auth = runtime()
    for headers, valid in [
        ({"origin": "https://localhost:8000"}, True),
        ({"referer": "https://localhost:8000/login?from=home"}, True),
        ({"origin": "null"}, False),
        ({"origin": "https://localhost:8000.evil.com"}, False),
        ({"origin": "https://evil.com", "referer": "https://localhost:8000/"}, False),
        ({"referer": "https://[broken"}, False),
        ({}, False),
    ]:
        request = Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace(auth=auth)),
                           "headers": [(key.encode(), value.encode()) for key, value in headers.items()]})
        if valid:
            origin_guard(request)
        else:
            with pytest.raises(AuthError):
                origin_guard(request)
