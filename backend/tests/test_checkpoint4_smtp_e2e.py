"""Targeted mocked service-flow and security unit/integration tests for Task 12:
- Account registration with mandatory email verification
- One-time verification token consumption & anti-replay
- Password reset flow with neutral notice, session revocation & one-time token
- Google OAuth login, onboarding, anti-takeover collision guard, and account linking
Note: These tests use MockSession and sandbox captured SMTP outbox (mocked service-flow), not live external SMTP or persistent DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.auth import login, register, resend_verification, verify_email
from app.auth_schemas import LoginInput, RegisterInput, ResendVerificationInput, VerifyEmailInput
from app.config import EmailSettings, GoogleAuthSettings
from app.email_service import EmailResult, EmailService, format_receipt_timestamp
from app.google_auth import (
    GoogleLinkInput,
    GoogleLoginInput,
    GoogleOnboardingInput,
    GoogleTokenVerifier,
    VerifiedGoogleClaims,
    google_link_account,
    google_login,
    google_onboarding,
)
from app.models import (
    AccountVerification,
    AuthSession,
    PasswordResetToken,
    Profile,
    Role,
    User,
    UserOAuthIdentity,
    UserRole,
)
from app.password_reset import (
    ForgotPasswordInput,
    ResetPasswordInput,
    forgot_password,
    is_google_only_account,
    reset_password,
)
from app.security import AuthError, RateLimiter, digest


def test_smtp_end_to_end_registration_and_verification_flow():
    now = datetime(2026, 11, 25, 5, 0, 0, tzinfo=timezone.utc)
    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            email_domain_verified=False,
            app_public_url="http://localhost:5173",
            email_verification_required=True,
        )
    )

    db_store: dict[type, list[Any]] = {
        User: [],
        Profile: [],
        UserRole: [],
        AccountVerification: [],
    }

    class MockSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def begin(self):
            return self
        def scalar(self, query):
            # Inspect AccountVerification lookups
            query_str = str(query).lower()
            if "account_verifications" in query_str:
                for row in db_store[AccountVerification]:
                    if "token_hash" in query_str:
                        return row
            if "users" in query_str:
                # Check for existing email/username
                for u in db_store[User]:
                    return u
            return None
        def flush(self):
            pass
        def execute(self, stmt):
            pass
        def scalars(self, query):
            mock = MagicMock()
            mock.one.return_value = uuid4()
            return mock
        def add(self, obj):
            for t in db_store:
                if isinstance(obj, t):
                    db_store[t].append(obj)
        def add_all(self, objs):
            for o in objs:
                self.add(o)

    runtime = SimpleNamespace(
        now=lambda: now,
        hasher=SimpleNamespace(
            hash=lambda pw: f"$argon2id$v=19$m=65536,t=3,p=4${pw}",
            verify=lambda pw, h: h.endswith(f"${pw}"),
        ),
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        consume_pre=lambda pre: None,
        key=b"test-secret-signing-key-for-auth-runtime!",
    )

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = runtime
    req.app.state.auth_session_factory = lambda: MockSession()
    req.app.state.email_service = email_service

    # Step 1: Register with verification required
    reg_input = RegisterInput(
        email="new_cultivator@example.com",
        username="cultivator_test",
        display_name="Dao Gia Test",
        password=SecretStr("SecretPassword123!"),
    )
    reg_res = register(reg_input, req, pre="pre-cookie")
    assert reg_res.status == "pending_verification"
    assert reg_res.email == "new_cultivator@example.com"
    assert len(email_service.sandbox_outbox) == 1

    # Step 2: Extract verify token from the sent email
    mail = email_service.sandbox_outbox[0]
    assert mail["subject"] == "[AuraMeme] - Xác minh địa chỉ email"
    assert "noreply@example.com" in mail["from"]
    assert "/verify-email?token=" in mail["text"]
    raw_token = mail["text"].split("/verify-email?token=")[1].splitlines()[0].strip()
    token_hash = digest(raw_token)

    # Step 3: Verify the token in AccountVerification record
    assert len(db_store[AccountVerification]) == 1
    verif_row = db_store[AccountVerification][0]
    assert verif_row.token_hash == token_hash
    assert verif_row.email == "new_cultivator@example.com"
    assert verif_row.username == "cultivator_test"
    assert verif_row.verified_at is None

    # Step 4: Verify email through API
    with patch("app.aura_lock.lock_aura_mutation"), patch("app.aura_runtime.initialize_progress"):
        verify_input = VerifyEmailInput(token=raw_token)
        v_res = verify_email(verify_input, req, pre="pre-cookie")
        assert v_res.status == "verified"
        assert verif_row.verified_at == now
        assert len(db_store[User]) == 1
        created_user = db_store[User][0]
        assert created_user.username == "cultivator_test"

    # Step 5: Token cannot be reused (one-time usage constraint)
    with pytest.raises(AuthError) as err:
        verify_email(VerifyEmailInput(token=raw_token), req, pre="pre-cookie")
    assert err.value.status in (400, 409)


def test_smtp_end_to_end_password_reset_flow():
    now = datetime(2026, 11, 25, 5, 0, 0, tzinfo=timezone.utc)
    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            app_public_url="http://localhost:5173",
        )
    )

    user_id = uuid4()
    local_user = User(
        id=user_id,
        username="kiem_tu",
        email="kiemtu@example.com",
        password_hash="$argon2id$old_hash",
        status="active",
        created_at=now,
        updated_at=now,
    )
    reset_tokens = []
    revoked_sessions = []

    class MockSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def begin(self):
            return self
        def scalar(self, query):
            q_str = str(query).lower()
            if "users" in q_str:
                return local_user
            if "password_reset_tokens" in q_str:
                if reset_tokens:
                    return reset_tokens[-1]
            return None
        def get(self, model, ident):
            if model == Profile:
                return Profile(user_id=user_id, display_name="Kiếm Tu")
            return None
        def add(self, obj):
            if isinstance(obj, PasswordResetToken):
                reset_tokens.append(obj)
        def flush(self):
            pass
        def execute(self, stmt):
            revoked_sessions.append(stmt)

    hasher_mock = MagicMock()
    hasher_mock.hash.side_effect = lambda pw: f"$argon2id$new_hash_for_{pw}"
    runtime = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        hasher=hasher_mock,
    )

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = runtime
    req.app.state.auth_session_factory = lambda: MockSession()
    req.app.state.email_service = email_service

    # Step 1: Request password reset
    forgot_res = forgot_password(ForgotPasswordInput(email="kiemtu@example.com"), req, pre="pre")
    assert forgot_res.ok is True
    assert len(email_service.sandbox_outbox) == 1
    mail = email_service.sandbox_outbox[0]
    assert mail["subject"] == "[AuraMeme] - Đặt lại mật khẩu"
    assert "/reset-password?token=" in mail["text"]
    raw_token = mail["text"].split("/reset-password?token=")[1].splitlines()[0].strip()

    # Step 2: Reset password with new compliant password
    reset_res = reset_password(
        ResetPasswordInput(token=raw_token, new_password="BrandNewSecurePassword123!"),
        req,
        pre="pre",
    )
    assert reset_res.ok is True
    assert local_user.password_hash == "$argon2id$new_hash_for_BrandNewSecurePassword123!"
    assert reset_tokens[-1].used_at == now
    assert len(revoked_sessions) > 0  # Prior sessions revoked

    # Step 3: Reusing the same token is rejected
    with pytest.raises(AuthError) as err:
        reset_password(
            ResetPasswordInput(token=raw_token, new_password="AnotherNewPassword123!"),
            req,
            pre="pre",
        )
    assert err.value.status == 400
    assert err.value.code == "INVALID_RESET_TOKEN"


def test_google_oauth_complete_flow_and_anti_takeover():
    now = datetime(2026, 11, 25, 5, 0, 0, tzinfo=timezone.utc)
    user_id = uuid4()
    existing_user = User(
        id=user_id,
        username="truong_lao",
        email="truonglao@example.com",
        password_hash="$argon2id$valid_pw",
        status="active",
        created_at=now,
        updated_at=now,
    )

    verifier = MagicMock()
    verifier.verify_id_token.return_value = VerifiedGoogleClaims(
        sub="google-uid-9999",
        email="truonglao@example.com",
        email_verified=True,
        name="Trưởng Lão",
        nonce="test-nonce-123",
    )

    # 1. Anti-takeover collision test: Email matches local account but not linked
    db_collision = MagicMock()
    db_collision.__enter__.return_value = db_collision
    db_collision.__exit__.return_value = False
    db_collision.begin.return_value.__enter__.return_value = db_collision
    db_collision.begin.return_value.__exit__.return_value = False
    db_collision.scalar.side_effect = [None, existing_user]  # identity=None, user found

    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
    )
    req.app.state.google_auth = verifier
    req.app.state.auth_session_factory = lambda: db_collision

    login_input = GoogleLoginInput(id_token=SecretStr("mock-google-id-token"), nonce="test-nonce-123")
    with pytest.raises(AuthError) as exc:
        google_login(login_input, req, MagicMock(), pre="pre")
    assert exc.value.status == 409
    assert exc.value.code == "ACCOUNT_LINK_REQUIRED"

    # 2. Account linking with password verification
    db_link = MagicMock()
    db_link.scalar.return_value = None
    linked_objs = []
    db_link.add.side_effect = lambda obj: linked_objs.append(obj)

    req_link = MagicMock()
    req_link.app.state.auth = SimpleNamespace(
        now=lambda: now,
        limiter=SimpleNamespace(check=lambda *a, **kw: None),
        verify_password=lambda h, p: p == "CorrectPass123!",
    )
    req_link.app.state.google_auth = verifier

    # Bad password rejected
    with pytest.raises(AuthError) as link_err:
        google_link_account(
            GoogleLinkInput(id_token=SecretStr("mock-google-id-token"), current_password=SecretStr("WrongPass!")),
            req_link,
            account=SimpleNamespace(user=existing_user, db=db_link),
        )
    assert link_err.value.status == 403

    # Correct password succeeds
    link_res = google_link_account(
        GoogleLinkInput(id_token=SecretStr("mock-google-id-token"), current_password=SecretStr("CorrectPass123!")),
        req_link,
        account=SimpleNamespace(user=existing_user, db=db_link),
    )
    assert link_res.linked is True
    assert len(linked_objs) == 1
    assert linked_objs[0].provider_sub == "google-uid-9999"


def _make_verification_harness(email_service, initial_now=None):
    state = {
        "now": initial_now or datetime(2026, 11, 26, 1, 0, 0, tzinfo=timezone.utc),
        "mono": 1000.0,
    }
    db_store: dict[type, list] = {
        User: [],
        Profile: [],
        UserRole: [],
        AccountVerification: [],
    }
    limiter = RateLimiter()
    limiter.clock = lambda: state["mono"]

    class VerifSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def begin(self):
            return self
        def scalar(self, query):
            q_str = str(query).lower()
            compiled = query.compile()
            params = list(compiled.params.values())
            if "account_verifications" in q_str:
                for row in db_store[AccountVerification]:
                    if "token_hash" in q_str and row.token_hash in params:
                        return row
                    if "account_verifications.email =" in q_str and row.email in params:
                        if "verified_at is null" in q_str and row.verified_at is not None:
                            continue
                        return row
                    if "account_verifications.username =" in q_str and row.username in params:
                        if "verified_at is null" in q_str and row.verified_at is not None:
                            continue
                        if "expires_at >" in q_str and row.expires_at <= state["now"]:
                            continue
                        if "email !=" in q_str and row.email in params:
                            continue
                        return row
            if "users" in q_str:
                for u in db_store[User]:
                    if "users.email =" in q_str and u.email in params:
                        return u.id if "users.id" in q_str.split("from")[0] else u
                    if "users.username =" in q_str and u.username in params:
                        return u.id if "users.id" in q_str.split("from")[0] else u
            return None
        def flush(self):
            pass
        def execute(self, stmt):
            pass
        def scalars(self, query):
            mock = MagicMock()
            mock.one.return_value = uuid4()
            return mock
        def add(self, obj):
            for t in db_store:
                if isinstance(obj, t):
                    db_store[t].append(obj)
        def add_all(self, objs):
            for o in objs:
                self.add(o)

    runtime = SimpleNamespace(
        now=lambda: state["now"],
        hasher=SimpleNamespace(
            hash=lambda pw: f"$argon2id$v=19$m=65536,t=3,p=4${pw}",
            verify=lambda pw, h: h.endswith(f"${pw}"),
        ),
        limiter=limiter,
        consume_pre=lambda pre: None,
        key=b"test-secret-signing-key-for-auth-runtime!",
    )
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.app.state.auth = runtime
    req.app.state.auth_session_factory = lambda: VerifSession()
    req.app.state.email_service = email_service
    return state, db_store, req


def test_fail_closed_when_verification_required_and_email_disabled(monkeypatch):
    # Case 1: email_mode = "disabled" with email_verification_required = True
    disabled_service = EmailService(
        EmailSettings(email_mode="disabled", email_verification_required=True)
    )
    _, db_store, req = _make_verification_harness(disabled_service)
    reg_input = RegisterInput(
        email="failclosed@example.com",
        username="failclosed_user",
        display_name="Fail Closed",
        password=SecretStr("SecretPassword123!"),
    )
    with pytest.raises(AuthError) as exc:
        register(reg_input, req, pre="pre")
    assert exc.value.status == 503
    assert exc.value.code == "EMAIL_SERVICE_UNAVAILABLE"
    assert len(db_store[User]) == 0
    assert len(db_store[AccountVerification]) == 0

    # Case 2: email_service is None when EMAIL_VERIFICATION_REQUIRED=true
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    _, db_store2, req2 = _make_verification_harness(None)
    with pytest.raises(AuthError) as exc2:
        register(reg_input, req2, pre="pre")
    assert exc2.value.status == 503
    assert exc2.value.code == "EMAIL_SERVICE_UNAVAILABLE"
    assert len(db_store2[User]) == 0


def test_smtp_failed_never_returns_success_and_allows_resend_recovery():
    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            app_public_url="http://localhost:5173",
            email_verification_required=True,
        )
    )
    state, db_store, req = _make_verification_harness(email_service)

    # Simulate SMTP delivery failure on register
    with patch.object(
        email_service,
        "send_account_verification_email",
        return_value=EmailResult(status="failed", dedupe_key="verify:x", error_code="SMTP_CONN_ERR"),
    ):
        reg_input = RegisterInput(
            email="recover@example.com",
            username="recover_user",
            display_name="Recover User",
            password=SecretStr("SecretPassword123!"),
        )
        with pytest.raises(AuthError) as exc:
            register(reg_input, req, pre="pre")
        assert exc.value.status == 503
        assert exc.value.code == "EMAIL_DELIVERY_FAILED"

    # Active user was NOT created, pending verification record is preserved for recovery
    assert len(db_store[User]) == 0
    assert len(db_store[AccountVerification]) == 1

    # After 31s, SMTP recovers -> resend succeeds and activates account
    state["now"] += timedelta(seconds=31)
    state["mono"] += 31.0
    resend_res = resend_verification(ResendVerificationInput(email="recover@example.com"), req, pre="pre")
    assert resend_res.status == "sent"
    assert len(email_service.sandbox_outbox) == 1
    token = email_service.sandbox_outbox[0]["text"].split("/verify-email?token=")[1].splitlines()[0].strip()

    with patch("app.aura_lock.lock_aura_mutation"), patch("app.aura_runtime.initialize_progress"):
        verify_res = verify_email(VerifyEmailInput(token=token), req, pre="pre")
    assert verify_res.status == "verified"
    assert len(db_store[User]) == 1
    assert db_store[User][0].status == "active"


def test_resend_cooldown_and_register_cannot_bypass_rate_limit():
    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            app_public_url="http://localhost:5173",
            email_verification_required=True,
        )
    )
    state, db_store, req = _make_verification_harness(email_service)
    reg_input = RegisterInput(
        email="ratelimit@example.com",
        username="ratelimit_user",
        display_name="Rate Limit",
        password=SecretStr("SecretPassword123!"),
    )

    # 1. Initial register succeeds
    res = register(reg_input, req, pre="pre")
    assert res.status == "pending_verification"

    # 2. Resend before 30s is rejected
    state["now"] += timedelta(seconds=5)
    state["mono"] += 5.0
    with pytest.raises(AuthError) as resend_err:
        resend_verification(ResendVerificationInput(email="ratelimit@example.com"), req, pre="pre")
    assert resend_err.value.status == 429
    assert resend_err.value.code == "RATE_LIMITED"
    assert resend_err.value.retry_after == 25

    # 3. Register again before 30s cannot bypass cooldown
    state["now"] += timedelta(seconds=5)
    state["mono"] += 5.0
    with pytest.raises(AuthError) as reg_err:
        register(reg_input, req, pre="pre")
    assert reg_err.value.status == 429
    assert reg_err.value.code == "RATE_LIMITED"
    assert reg_err.value.retry_after == 20

    # 4. Shared email rate limit (5 per 600s) blocks 6th attempt even after 30s cooldowns
    # (Steps 1, 2, 3 already consumed 3 slots in the shared limiter)
    for _ in range(2):
        state["now"] += timedelta(seconds=31)
        state["mono"] += 31.0
        resend_verification(ResendVerificationInput(email="ratelimit@example.com"), req, pre="pre")

    state["now"] += timedelta(seconds=31)
    state["mono"] += 31.0
    with pytest.raises(AuthError) as limit_err:
        register(reg_input, req, pre="pre")
    assert limit_err.value.status == 429
    assert limit_err.value.code == "RATE_LIMITED"
    assert limit_err.value.retry_after > 59


def test_valid_resend_invalidates_old_token_and_new_token_activates():
    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            app_public_url="http://localhost:5173",
            email_verification_required=True,
        )
    )
    state, db_store, req = _make_verification_harness(email_service)
    reg_input = RegisterInput(
        email="tokenswap@example.com",
        username="tokenswap_user",
        display_name="Token Swap",
        password=SecretStr("SecretPassword123!"),
    )

    register(reg_input, req, pre="pre")
    old_token = email_service.sandbox_outbox[0]["text"].split("/verify-email?token=")[1].splitlines()[0].strip()

    state["now"] += timedelta(seconds=31)
    state["mono"] += 31.0
    resend_verification(ResendVerificationInput(email="tokenswap@example.com"), req, pre="pre")
    new_token = email_service.sandbox_outbox[1]["text"].split("/verify-email?token=")[1].splitlines()[0].strip()
    assert new_token != old_token

    # Old token is invalidated
    with pytest.raises(AuthError) as old_err:
        verify_email(VerifyEmailInput(token=old_token), req, pre="pre")
    assert old_err.value.code == "INVALID_VERIFICATION_TOKEN"

    # New token activates the exact account
    with patch("app.aura_lock.lock_aura_mutation"), patch("app.aura_runtime.initialize_progress"):
        verify_res = verify_email(VerifyEmailInput(token=new_token), req, pre="pre")
    assert verify_res.status == "verified"
    assert len(db_store[User]) == 1
    assert db_store[User][0].email == "tokenswap@example.com"
    assert db_store[User][0].username == "tokenswap_user"
