"""Unit & security contract tests for Task 10: Email Verification & Google Onboarding."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.auth import login, register, verify_email
from app.auth_schemas import LoginInput, RegisterInput, VerifyEmailInput
from app.config import EmailSettings
from app.email_service import EmailService
from app.google_auth import (
    GoogleLoginInput,
    GoogleOnboardingInput,
    create_onboarding_token,
    google_login,
    google_onboarding,
    suggest_tag,
    verify_onboarding_token,
)
from app.models import AccountVerification, AuthSession, User
from app.security import AuthError, digest


def test_registration_email_verification_flow():
    now = datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)
    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            email_domain_verified=True,
            email_verification_required=True,
            app_public_url="https://aurameme.local",
        )
    )

    verif_records = []
    created_users = []

    def make_db():
        db = MagicMock()
        db.__enter__.return_value = db
        db.__exit__.return_value = False
        db.begin.return_value.__enter__.return_value = db
        db.begin.return_value.__exit__.return_value = False
        db.scalars.return_value.one.return_value = uuid4()
        db.scalar.return_value = None

        def add_handler(obj):
            if isinstance(obj, AccountVerification):
                verif_records.append(obj)
            elif isinstance(obj, User):
                created_users.append(obj)

        db.add.side_effect = add_handler
        return db

    db = make_db()
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        hasher=SimpleNamespace(hash=lambda pw: f"$argon2id$hashed:{pw}"),
    )
    req.app.state.auth_session_factory = lambda: db
    req.app.state.email_service = email_service

    reg_input = RegisterInput(
        email="newuser@example.com",
        username="new_cultivator",
        display_name="New Cultivator",
        password=SecretStr("VeryStrongPassword123!"),
    )

    # 1. Register triggers verification email and does NOT immediately create User
    res = register(reg_input, req, pre="pre")
    assert res.status == "pending_verification"
    assert res.email == "newuser@example.com"
    assert len(email_service.sandbox_outbox) == 1
    assert len(verif_records) == 1
    assert len(created_users) == 0

    sent_mail = email_service.sandbox_outbox[0]
    assert "verify-email?token=" in sent_mail["text"]
    raw_token = sent_mail["text"].split("verify-email?token=")[1].splitlines()[0].strip()

    verif_row = verif_records[0]
    assert verif_row.token_hash == digest(raw_token)
    assert verif_row.verified_at is None

    # 2. Login before verification returns 403 ACCOUNT_UNVERIFIED
    login_db = MagicMock()
    login_db.__enter__.return_value = login_db
    login_db.__exit__.return_value = False
    login_db.begin.return_value.__enter__.return_value = login_db
    login_db.begin.return_value.__exit__.return_value = False
    login_db.scalars.return_value.one_or_none.return_value = None  # user not found in User
    login_db.scalar.return_value = verif_row  # found in AccountVerification

    login_req = MagicMock()
    login_req.client.host = "127.0.0.1"
    login_req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        verify_password=lambda h, p: False,
        dummy_hash="dummy",
    )
    login_req.app.state.auth_session_factory = lambda: login_db

    with pytest.raises(AuthError) as login_exc:
        login(LoginInput(email="newuser@example.com", password=SecretStr("VeryStrongPassword123!")), login_req, MagicMock(), pre="pre")
    assert login_exc.value.status == 403
    assert login_exc.value.code == "ACCOUNT_UNVERIFIED"

    # 3. Verify email with valid token
    vdb = make_db()
    # Mock finding the verification record
    vdb.scalar.side_effect = [verif_row, None, uuid4()]

    vreq = MagicMock()
    vreq.client.host = "127.0.0.1"
    vreq.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
    )
    vreq.app.state.auth_session_factory = lambda: vdb

    vres = verify_email(VerifyEmailInput(token=raw_token), vreq, pre="pre")
    assert vres.status == "verified"
    assert verif_row.verified_at == now
    assert len(created_users) == 1
    assert created_users[0].username == "new_cultivator"

    # 4. Verify email with invalid token returns 400
    bad_db = make_db()
    bad_db.scalar.return_value = None
    vreq.app.state.auth_session_factory = lambda: bad_db
    with pytest.raises(AuthError) as bad_exc:
        verify_email(VerifyEmailInput(token="wrong_token_12345678"), vreq, pre="pre")
    assert bad_exc.value.status == 400
    assert bad_exc.value.code == "INVALID_VERIFICATION_TOKEN"


def test_google_onboarding_token_tampering_and_expiration():
    now = datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)
    runtime = SimpleNamespace(
        now=lambda: now,
        key=b"secret-signing-key-minimum-32-bytes-long!",
    )

    token = create_onboarding_token(runtime, sub="google-sub-999", email="player@gmail.com", name="Player One")
    claims = verify_onboarding_token(runtime, token)
    assert claims["sub"] == "google-sub-999"
    assert claims["email"] == "player@gmail.com"
    assert claims["name"] == "Player One"

    # Tampered token rejected
    tampered = token[:-4] + "ffff"
    with pytest.raises(AuthError) as tampered_exc:
        verify_onboarding_token(runtime, tampered)
    assert tampered_exc.value.code == "INVALID_ONBOARDING_TOKEN"

    # Expired token rejected
    future_runtime = SimpleNamespace(
        now=lambda: now + timedelta(minutes=20),
        key=b"secret-signing-key-minimum-32-bytes-long!",
    )
    with pytest.raises(AuthError) as exp_exc:
        verify_onboarding_token(future_runtime, token)
    assert exp_exc.value.code == "ONBOARDING_TOKEN_EXPIRED"


def test_suggest_tag():
    assert suggest_tag("phTrKi3n@student.ptithcm.edu.vn") == "phtrki3n"
    assert suggest_tag("a@gmail.com") == "aura_user"
    assert suggest_tag("cool.cultivator_99@gmail.com") == "cool_cultivator_99"
