"""Targeted unit and security tests for Checkpoint 1: Google OAuth verification, onboarding, linking, and error flows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.auth import login
from app.auth_schemas import LoginInput
from app.config import GoogleAuthSettings
from app.google_auth import (
    GoogleLinkInput,
    GoogleLoginInput,
    GoogleOnboardingInput,
    GoogleTokenVerifier,
    VerifiedGoogleClaims,
    get_google_config,
    google_link_account,
    google_login,
    google_onboarding,
)
from app.models import AuthSession, Profile, Role, User, UserOAuthIdentity, UserRole
from app.security import AuthError


def test_get_google_config_enabled_and_disabled():
    req = MagicMock()
    # 1. Configured
    req.app.state.google_auth = GoogleTokenVerifier(
        GoogleAuthSettings(google_client_id="test-client-123.apps.googleusercontent.com")
    )
    cfg1 = get_google_config(req)
    assert cfg1.enabled is True
    assert cfg1.client_id == "test-client-123.apps.googleusercontent.com"

    # 2. Unconfigured
    req.app.state.google_auth = GoogleTokenVerifier(GoogleAuthSettings(google_client_id=None))
    cfg2 = get_google_config(req)
    assert cfg2.enabled is False
    assert cfg2.client_id is None


def test_google_login_existing_linked_account():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    user_id = uuid4()
    active_user = User(
        id=user_id,
        username="khang_test",
        email="khang@example.com",
        password_hash="$argon2id$hashed",
        status="active",
        created_at=now,
        updated_at=now,
    )
    existing_identity = UserOAuthIdentity(
        id=uuid4(),
        user_id=user_id,
        provider="google",
        provider_sub="google-sub-100",
        email="khang@example.com",
        email_verified=True,
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    db.begin.return_value.__enter__.return_value = db
    db.begin.return_value.__exit__.return_value = False
    # 1. select identity, 2. select user
    db.scalar.side_effect = [existing_identity, active_user]
    db.get.return_value = Profile(user_id=user_id, display_name="Khang Tester", updated_at=now)
    db.scalars.return_value.all.return_value = ["USER"]

    verifier = MagicMock()
    verifier.verify_id_token.return_value = VerifiedGoogleClaims(
        sub="google-sub-100",
        email="khang@example.com",
        email_verified=True,
        name="Khang Tester",
        nonce="test-nonce",
    )

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        consume_pre=lambda pre: None,
        pre_cookie="am_pre",
        cookie_domain=None,
        secure=False,
        secure_cookies=False,
    )
    req.app.state.google_auth = verifier
    req.app.state.auth_session_factory = lambda: db

    resp = MagicMock()
    payload = GoogleLoginInput(id_token=SecretStr("mock-google-id-token-long-enough"), nonce="test-nonce")

    user_dto = google_login(payload, req, resp, pre="pre")
    assert user_dto.id == user_id
    assert user_dto.username == "khang_test"
    assert resp.set_cookie.called


def test_google_login_new_user_returns_needs_onboarding_and_completes_onboarding():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    db.begin.return_value.__enter__.return_value = db
    db.begin.return_value.__exit__.return_value = False
    # No identity, no existing email
    db.scalar.side_effect = [None, None]

    verifier = MagicMock()
    verifier.verify_id_token.return_value = VerifiedGoogleClaims(
        sub="google-sub-200",
        email="newuser@example.com",
        email_verified=True,
        name="New Cultivator",
        nonce="nonce-200",
    )

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        key=b"secret-signing-key-minimum-32-bytes-long!",
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        consume_pre=lambda pre: None,
        pre_cookie="am_pre",
        cookie_domain=None,
        secure=False,
        secure_cookies=False,
    )
    req.app.state.google_auth = verifier
    req.app.state.auth_session_factory = lambda: db

    resp = MagicMock()
    payload = GoogleLoginInput(id_token=SecretStr("mock-google-id-token-long-enough"), nonce="nonce-200")

    # Step 1: Login without username returns needs_onboarding
    res = google_login(payload, req, resp, pre="pre")
    assert res.status == "needs_onboarding"
    assert res.email == "newuser@example.com"
    assert res.suggested_tag == "newuser"
    onboarding_token = res.onboarding_token

    # Step 2: Complete onboarding with selected username
    onboard_db = MagicMock()
    onboard_db.__enter__.return_value = onboard_db
    onboard_db.__exit__.return_value = False
    onboard_db.begin.return_value.__enter__.return_value = onboard_db
    onboard_db.begin.return_value.__exit__.return_value = False
    role_id = uuid4()
    onboard_db.scalar.side_effect = [None, None, None, role_id]

    added = []
    def add_obj(obj):
        added.append(obj)
        if isinstance(obj, User):
            onboard_db.get.return_value = Profile(user_id=obj.id, display_name="New Cultivator", updated_at=now)
            onboard_db.scalars.return_value.all.return_value = ["USER"]

    onboard_db.add.side_effect = add_obj
    onboard_db.add_all.side_effect = lambda objs: [add_obj(o) for o in objs]
    req.app.state.auth_session_factory = lambda: onboard_db

    with patch("app.aura_lock.lock_aura_mutation"), patch("app.aura_runtime.initialize_progress"):
        onboard_payload = GoogleOnboardingInput(onboarding_token=onboarding_token, username="new_cultivator")
        user_dto = google_onboarding(onboard_payload, req, resp, pre="pre")
        assert user_dto.username == "new_cultivator"
        assert any(isinstance(x, User) for x in added)
        assert any(isinstance(x, UserOAuthIdentity) for x in added)
        assert any(isinstance(x, AuthSession) for x in added)


def test_google_login_anti_takeover_requires_account_linking():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    existing_local_user = User(
        id=uuid4(),
        username="existing_member",
        email="conflict@example.com",
        password_hash="$argon2id$hashed",
        status="active",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    db.begin.return_value.__enter__.return_value = db
    db.begin.return_value.__exit__.return_value = False
    # 1. Identity is None, 2. Existing user by email is found!
    db.scalar.side_effect = [None, existing_local_user]

    verifier = MagicMock()
    verifier.verify_id_token.return_value = VerifiedGoogleClaims(
        sub="google-sub-conflict",
        email="conflict@example.com",
        email_verified=True,
        name="Attacker Or Colliding Email",
        nonce="nonce-x",
    )

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
    )
    req.app.state.google_auth = verifier
    req.app.state.auth_session_factory = lambda: db

    payload = GoogleLoginInput(id_token=SecretStr("mock-google-id-token-long-enough"), nonce="nonce-x")
    with pytest.raises(AuthError) as exc:
        google_login(payload, req, MagicMock(), pre="pre")
    assert exc.value.status == 409
    assert exc.value.code == "ACCOUNT_LINK_REQUIRED"


def test_google_link_account_flow():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    user_id = uuid4()
    local_user = User(
        id=user_id,
        username="kien_user",
        email="kien@example.com",
        password_hash="$argon2id$hashed",
        status="active",
        created_at=now,
        updated_at=now,
    )

    account_db = MagicMock()
    account_db.scalar.return_value = None  # No existing Google identity with this sub
    added = []
    account_db.add.side_effect = lambda obj: added.append(obj)

    verifier = MagicMock()
    verifier.verify_id_token.return_value = VerifiedGoogleClaims(
        sub="google-sub-kien",
        email="kien@example.com",
        email_verified=True,
        name="Kien Local",
    )

    runtime = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        verify_password=lambda h, p: p == "ValidPassword123!",
    )

    req = MagicMock()
    req.app.state.auth = runtime
    req.app.state.google_auth = verifier

    account = SimpleNamespace(user=local_user, db=account_db)

    # 1. Wrong password rejected with 403 FORBIDDEN
    bad_payload = GoogleLinkInput(
        id_token=SecretStr("mock-google-id-token-long-enough"),
        current_password=SecretStr("WrongPassword!"),
    )
    with pytest.raises(AuthError) as bad_exc:
        google_link_account(bad_payload, req, account=account)
    assert bad_exc.value.status == 403
    assert bad_exc.value.code == "FORBIDDEN"

    # 2. Correct password links successfully
    good_payload = GoogleLinkInput(
        id_token=SecretStr("mock-google-id-token-long-enough"),
        current_password=SecretStr("ValidPassword123!"),
    )
    link_res = google_link_account(good_payload, req, account=account)
    assert link_res.linked is True
    assert link_res.provider == "google"
    assert len(added) == 1
    assert added[0].user_id == user_id
    assert added[0].provider_sub == "google-sub-kien"


def test_google_token_verification_network_and_status_errors():
    verifier = GoogleTokenVerifier(
        GoogleAuthSettings(google_client_id="valid-client.apps.googleusercontent.com")
    )

    # 1. Network / Transport error -> 502 GOOGLE_VERIFY_UNAVAILABLE
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection failed")):
        with pytest.raises(AuthError) as net_exc:
            verifier.verify_id_token("mock-token-long-enough", now_ts=1_795_000_000)
        assert net_exc.value.status == 502
        assert net_exc.value.code == "GOOGLE_VERIFY_UNAVAILABLE"

    # 2. HTTP 400 from Google tokeninfo endpoint -> 401 GOOGLE_TOKEN_INVALID
    mock_bad_resp = MagicMock(status_code=400)
    with patch("httpx.Client.get", return_value=mock_bad_resp):
        with pytest.raises(AuthError) as token_exc:
            verifier.verify_id_token("mock-token-long-enough", now_ts=1_795_000_000)
        assert token_exc.value.status == 401
        assert token_exc.value.code == "GOOGLE_TOKEN_INVALID"


def test_email_password_login_remains_fully_functional():
    now = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    user_id = uuid4()
    standard_user = User(
        id=user_id,
        username="standard_user",
        email="standard@example.com",
        password_hash="$argon2id$validhash",
        status="active",
        created_at=now,
        updated_at=now,
    )

    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    db.begin.return_value.__enter__.return_value = db
    db.begin.return_value.__exit__.return_value = False
    db.scalars.return_value.one_or_none.return_value = standard_user
    db.get.return_value = Profile(user_id=user_id, display_name="Standard User", updated_at=now)
    db.scalars.return_value.all.return_value = ["USER"]

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        verify_password=lambda h, p: p == "Password123!",
        hasher=SimpleNamespace(check_needs_rehash=lambda h: False),
        dummy_hash="dummy",
        consume_pre=lambda pre: None,
        pre_cookie="am_pre",
        cookie_domain=None,
        secure=False,
        secure_cookies=False,
    )
    req.app.state.auth_session_factory = lambda: db

    resp = MagicMock()
    dto = login(
        LoginInput(email="standard@example.com", password=SecretStr("Password123!")),
        req,
        resp,
        pre="pre",
    )
    assert dto.id == user_id
    assert dto.username == "standard_user"
    assert resp.set_cookie.called
