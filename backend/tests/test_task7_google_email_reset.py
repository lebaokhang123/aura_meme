"""Unit & security contract tests for Task 7: Google Auth, Password Reset, and Transactional Email."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.config import EmailSettings, GoogleAuthSettings
from app.email_service import EmailService
from app.google_auth import GoogleTokenVerifier, VerifiedGoogleClaims
from app.password_reset import (
    GOOGLE_ONLY_PASSWORD_PREFIX,
    NEUTRAL_FORGOT_MESSAGE,
    ForgotPasswordInput,
    ResetPasswordInput,
    is_google_only_account,
)
from app.security import AuthError, digest


# ============================================================================
# 1. Google Identity / OIDC Claim Verification Security Tests
# ============================================================================

def test_google_token_claims_validation_strict():
    now_ts = 1_795_000_000
    client_id = "test-client-123.apps.googleusercontent.com"
    valid_claims = {
        "aud": client_id,
        "iss": "https://accounts.google.com",
        "sub": "109876543210987654321",
        "email": "User.Test@Gmail.com",
        "email_verified": "true",
        "exp": str(now_ts + 300),
        "name": "Aura Cultivator",
        "nonce": "nonce-abc-123",
    }

    parsed = GoogleTokenVerifier.validate_claims(
        valid_claims, client_id=client_id, now_ts=now_ts, expected_nonce="nonce-abc-123"
    )
    assert parsed == VerifiedGoogleClaims(
        sub="109876543210987654321",
        email="user.test@gmail.com",
        email_verified=True,
        name="Aura Cultivator",
        nonce="nonce-abc-123",
    )

    # Wrong audience
    with pytest.raises(AuthError) as exc:
        GoogleTokenVerifier.validate_claims({**valid_claims, "aud": "evil-client"}, client_id=client_id, now_ts=now_ts)
    assert exc.value.code == "GOOGLE_TOKEN_INVALID"

    # Wrong issuer
    with pytest.raises(AuthError) as exc:
        GoogleTokenVerifier.validate_claims({**valid_claims, "iss": "https://evil.example"}, client_id=client_id, now_ts=now_ts)
    assert exc.value.code == "GOOGLE_TOKEN_INVALID"

    # Expired token
    with pytest.raises(AuthError) as exc:
        GoogleTokenVerifier.validate_claims({**valid_claims, "exp": str(now_ts - 1)}, client_id=client_id, now_ts=now_ts)
    assert exc.value.code == "GOOGLE_TOKEN_EXPIRED"

    # Unverified email rejected
    with pytest.raises(AuthError) as exc:
        GoogleTokenVerifier.validate_claims({**valid_claims, "email_verified": False}, client_id=client_id, now_ts=now_ts)
    assert exc.value.code == "GOOGLE_EMAIL_UNVERIFIED"

    # Nonce mismatch rejected (anti-replay / login CSRF)
    with pytest.raises(AuthError) as exc:
        GoogleTokenVerifier.validate_claims(valid_claims, client_id=client_id, now_ts=now_ts, expected_nonce="other-nonce")
    assert exc.value.code == "GOOGLE_NONCE_MISMATCH"


def test_google_unconfigured_fails_closed_503():
    verifier = GoogleTokenVerifier(GoogleAuthSettings(google_client_id=None))
    assert verifier.configured is False
    with pytest.raises(AuthError) as exc:
        verifier.verify_id_token("fake-token-payload-1234567890", now_ts=1_795_000_000)
    assert exc.value.status == 503
    assert exc.value.code == "GOOGLE_AUTH_NOT_CONFIGURED"


# ============================================================================
# 2. Password Recovery Policy & Google-Only Account Safety
# ============================================================================

def test_password_reset_input_enforces_password_policy_and_google_sentinel():
    assert is_google_only_account(GOOGLE_ONLY_PASSWORD_PREFIX + "abcdef") is True
    assert is_google_only_account("$argon2id$v=19$m=65536,t=3,p=4$salt$hash") is False
    assert is_google_only_account(None) is False

    # Normalizes email
    inp = ForgotPasswordInput(email="  Alice@Example.COM ")
    assert inp.email == "alice@example.com"

    # Rejects short password (< 12 chars)
    with pytest.raises(ValueError):
        ResetPasswordInput(token="a" * 32, new_password="short")

    # Accepts compliant 12+ char password and keeps SecretStr masked
    ok = ResetPasswordInput(token="a" * 32, new_password="CorrectHorseBattery123!")
    assert "CorrectHorseBattery123!" not in repr(ok)
    assert ("a" * 32) not in repr(ok)


def test_forgot_password_neutral_response_and_hashed_token_only():
    from app.password_reset import forgot_password, reset_password

    email_service = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="sandbox@test.local",
            email_domain_verified=False,
            app_public_url="https://aurameme.local",
        )
    )
    now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
    user_id = uuid4()
    active_user = SimpleNamespace(
        id=user_id,
        username="alice",
        email="alice@example.com",
        status="active",
        password_hash="$argon2id$valid",
        updated_at=now,
    )
    google_user = SimpleNamespace(
        id=uuid4(),
        username="guser",
        email="guser@example.com",
        status="active",
        password_hash=GOOGLE_ONLY_PASSWORD_PREFIX + "deadbeef",
        updated_at=now,
    )
    added_records = []

    def make_request(found_user):
        db = MagicMock()
        db.__enter__.return_value = db
        db.__exit__.return_value = False
        db.begin.return_value.__enter__.return_value = db
        db.begin.return_value.__exit__.return_value = False
        db.scalar.return_value = found_user
        db.get.return_value = SimpleNamespace(display_name="Alice")
        db.add.side_effect = lambda obj: added_records.append(obj)

        req = MagicMock()
        req.client.host = "127.0.0.1"
        req.app.state.auth = SimpleNamespace(
            now=lambda: now,
            limiter=SimpleNamespace(check=lambda *a, **kw: None),
            hasher=SimpleNamespace(hash=lambda pw: f"$argon2id$hashed:{len(pw)}"),
        )
        req.app.state.auth_session_factory = lambda: db
        req.app.state.email_service = email_service
        return req

    # 1. Existing local user -> neutral message + hashed token stored + 1 sandbox email
    res_existing = forgot_password(ForgotPasswordInput(email="alice@example.com"), make_request(active_user), pre="pre")
    # 2. Non-existent email -> IDENTICAL neutral message, 0 new emails
    res_missing = forgot_password(ForgotPasswordInput(email="nobody@example.com"), make_request(None), pre="pre")
    # 3. Google-only account -> IDENTICAL neutral message, 0 new emails
    res_google = forgot_password(ForgotPasswordInput(email="guser@example.com"), make_request(google_user), pre="pre")

    assert res_existing.message == NEUTRAL_FORGOT_MESSAGE
    assert res_missing.message == NEUTRAL_FORGOT_MESSAGE
    assert res_google.message == NEUTRAL_FORGOT_MESSAGE
    assert len(email_service.sandbox_outbox) == 1
    assert len(added_records) == 1

    # Extract token from email link and verify ONLY its SHA-256 digest is stored in DB
    mail = email_service.sandbox_outbox[0]
    assert "reset-password?token=" in mail["text"]
    raw_token = mail["text"].split("reset-password?token=")[1].splitlines()[0].strip()
    token_row = added_records[0]
    assert token_row.token_hash == digest(raw_token)
    assert token_row.token_hash != raw_token
    assert token_row.expires_at == now + timedelta(minutes=30)

    # 4. Valid reset_password updates password, marks used_at, and revokes sessions (db.execute called)
    reset_db = MagicMock()
    reset_db.__enter__.return_value = reset_db
    reset_db.__exit__.return_value = False
    reset_db.begin.return_value.__enter__.return_value = reset_db
    reset_db.begin.return_value.__exit__.return_value = False
    reset_db.scalar.side_effect = [token_row, active_user]
    reset_req = make_request(active_user)
    reset_req.app.state.auth_session_factory = lambda: reset_db

    reset_res = reset_password(
        ResetPasswordInput(token=raw_token, new_password="BrandNewPassword123!"),
        reset_req,
        pre="pre",
    )
    assert reset_res.ok is True
    assert token_row.used_at == now
    assert active_user.password_hash.startswith("$argon2id$hashed:")
    assert reset_db.execute.called  # Revoked existing sessions

    # 5. Reusing the same token is rejected with 400 INVALID_RESET_TOKEN
    reset_db.scalar.side_effect = [token_row]
    with pytest.raises(AuthError) as exc:
        reset_password(ResetPasswordInput(token=raw_token, new_password="AnotherPassword123!"), reset_req, pre="pre")
    assert exc.value.code == "INVALID_RESET_TOKEN"


# ============================================================================
# 3. Transactional Email Service Security, Templates & Idempotency Tests
# ============================================================================

def test_email_service_refuses_unverified_aurameme_domain():
    svc = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="no-reply@aurameme.com",
            email_domain_verified=False,
        )
    )
    res = svc.send(to_email="u@example.com", subject="Hi", text_body="Hello", html_body="<p>Hello</p>")
    assert res.status == "failed"
    assert res.error_code == "EMAIL_DOMAIN_UNVERIFIED"
    assert len(svc.sandbox_outbox) == 0

    verified_svc = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="no-reply@aurameme.com",
            email_domain_verified=True,
        )
    )
    ok = verified_svc.send(to_email="u@example.com", subject="Hi", text_body="Hello", html_body="<p>Hello</p>")
    assert ok.status == "sandbox_captured"
    assert "no-reply@aurameme.com" in verified_svc.sandbox_outbox[0]["from"]


def test_email_service_templates_and_receipt_idempotency():
    svc = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="sandbox@test.local",
            email_admin_inbox="admin@test.local",
            app_public_url="https://aurameme.local",
        )
    )

    # Contact sends a SINGLE confirmation email to sender (no duplicate admin email)
    contact_res = svc.send_contact_emails(
        contact_id="cnt-001",
        sender_name="Minh",
        sender_email="minh@example.com",
        subject_line="Góp ý giao diện",
        message_body="Giao diện Sáng Thế Thần rất đẹp!",
    )
    assert "admin" not in contact_res
    assert contact_res["ack"].status == "sandbox_captured"
    assert len(svc.sandbox_outbox) == 1
    contact_mail = svc.sandbox_outbox[0]
    assert contact_mail["subject"] == "[AuraMeme] - Tiếp nhận góp ý"
    assert "cid:aurameme-logo" in contact_mail["html"]
    assert contact_mail["inline_logo_size"] > 1000
    # Order: Mã tham chiếu -> Chủ đề -> Nội dung
    assert contact_mail["text"].index("cnt-001") < contact_mail["text"].index("Góp ý giao diện") < contact_mail["text"].index("Giao diện Sáng Thế Thần rất đẹp!")

    # Premium receipt sends ONCE per order_code; duplicate webhook callback is deduplicated
    r1 = svc.send_premium_receipt_email(
        to_email="buyer@example.com",
        display_name="Buyer",
        order_code="AM-PRIME-001",
        tier="prime",
        amount_vnd_formatted="1.250.000 VNĐ",
        amount_usd_formatted="$50",
        provider="paypal_sandbox",
        completed_at_iso="2026-11-22T12:00:00+00:00",
        username="buyer_tag",
    )
    r2 = svc.send_premium_receipt_email(
        to_email="buyer@example.com",
        display_name="Buyer",
        order_code="AM-PRIME-001",
        tier="prime",
        amount_vnd_formatted="1.250.000 VNĐ",
        amount_usd_formatted="$50",
        provider="paypal_sandbox",
        completed_at_iso="2026-11-22T12:00:00+00:00",
        username="buyer_tag",
    )
    assert r1.status == "sandbox_captured"
    assert r2.status == "duplicate_skipped"
    receipt_mail = svc.sandbox_outbox[-1]
    assert receipt_mail["subject"] == "[AuraMeme] - Biên nhận thanh toán Aura Prime"
    assert "AM-PRIME-001" in receipt_mail["html"]
    assert "PayPal Sandbox" in receipt_mail["text"]
    assert "<script" not in receipt_mail["html"].lower()
    assert len(receipt_mail["attachments"]) == 1
    assert receipt_mail["attachments"][0]["filename"] == "AuraMeme-Receipt-AM-PRIME-001.pdf"
    assert receipt_mail["attachments"][0]["content_type"] == "application/pdf"
    assert receipt_mail["attachments"][0]["size"] > 10000


def test_email_disabled_mode_is_safe_noop():
    svc = EmailService(EmailSettings(email_mode="disabled"))
    res = svc.send_password_reset_email(
        to_email="u@example.com", display_name="U", reset_url="https://aurameme.local/reset-password?token=abc"
    )
    assert res.status == "disabled"
    assert len(svc.sandbox_outbox) == 0

def test_smtp_starttls_receipt_and_transactional_templates(monkeypatch):
    from io import BytesIO
    from pypdf import PdfReader

    sent = []
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ("smtp.example.test", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, *, context):
            assert context.check_hostname
            calls.append("starttls")

        def login(self, username, password):
            assert (username, password) == ("fixture-user", "fixture-credential")
            calls.append("login")

        def send_message(self, message):
            assert calls[-4:] == ["ehlo", "starttls", "ehlo", "login"]
            sent.append(message)

    monkeypatch.setattr("app.email_service.smtplib.SMTP", FakeSMTP)
    svc = EmailService(EmailSettings(
        _env_file=None, email_mode="smtp", smtp_host="smtp.example.test",
        smtp_username="fixture-user", smtp_password="fixture-credential",
        email_from_address="sender@example.test",
    ))
    receipt = dict(to_email="buyer@example.test", display_name="Buyer", order_code="AM-PLUS-SMTPFIX",
                   tier="plus", amount_vnd_formatted="130.000 VNĐ", amount_usd_formatted="$5",
                   provider="paypal_sandbox", provider_txn_id="SIM-PP-TEST123",
                   completed_at_iso="2026-11-24T00:00:00+00:00")
    assert svc.send_premium_receipt_email(**receipt).status == "sent"
    assert svc.send_premium_receipt_email(**receipt).status == "duplicate_skipped"
    assert svc.send_password_reset_email(to_email="buyer@example.test", display_name="Buyer",
                                         reset_url="https://example.test/reset").status == "sent"
    assert svc.send_account_verification_email(to_email="buyer@example.test", display_name="Buyer",
                                       verify_url="https://example.test/verify").status == "sent"
    assert svc.send_contact_emails(contact_id="contact-smoke", sender_name="Buyer", sender_email="buyer@example.test",
                                   subject_line="Fixture", message_body="Hello")["ack"].status == "sent"

    assert len(sent) == 4
    plain = sent[0].get_body(preferencelist=("plain",)).get_content()
    assert "PayPal Sandbox" in plain and "Mô phỏng PayPal nội bộ." in plain
    attachment, = sent[0].iter_attachments()
    assert attachment.get_filename() == "AuraMeme-Receipt-AM-PLUS-SMTPFIX.pdf"
    text = "".join(page.extract_text() for page in PdfReader(BytesIO(attachment.get_payload(decode=True))).pages)
    for expected in ("AM-PLUS-SMTPFIX", "SIM-PP-TEST123", "PayPal Sandbox"):
        assert expected in text


def test_receipt_email_formats_timestamp_in_asia_ho_chi_minh():
    from app.email_service import format_receipt_timestamp

    # 1. UTC ISO conversion to Asia/Ho_Chi_Minh (+7 hours)
    formatted = format_receipt_timestamp("2026-11-24T16:00:17+00:00")
    assert formatted == "23:00:17 - 24/11/2026"

    # 2. 'Z' suffix handled
    formatted_z = format_receipt_timestamp("2026-11-24T16:00:17Z")
    assert formatted_z == "23:00:17 - 24/11/2026"

    # 3. Invalid or empty string fallbacks safely
    assert format_receipt_timestamp("") == ""
    assert format_receipt_timestamp("not-a-timestamp") == "not-a-timestamp"

    # 4. Email template renders formatted timestamp in both plain text and HTML
    svc = EmailService(EmailSettings(email_mode="sandbox", email_from_address="test@example.com"))
    res = svc.send_premium_receipt_email(
        to_email="buyer@example.com",
        display_name="Cultivator",
        order_code="AM-RECEIPT-VN-TIME",
        tier="plus",
        amount_vnd_formatted="130.000 VNĐ",
        amount_usd_formatted="$5.00",
        provider="paypal_sandbox",
        completed_at_iso="2026-11-24T16:00:17+00:00",
    )
    assert res.status == "sandbox_captured"
    mail = svc.sandbox_outbox[-1]
    assert "Thời gian: 23:00:17 - 24/11/2026" in mail["text"]
    assert "23:00:17 - 24/11/2026" in mail["html"]
