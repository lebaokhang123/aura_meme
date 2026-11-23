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


def test_vault_schema_ready_accepts_0016_migration():
    from app.vault_runtime import schema_ready

    db = MagicMock()
    db.scalars.return_value = ["0016_account_email_verifications"]
    assert schema_ready(db) is True


def test_email_polish_subjects_cid_logo_contact_and_pdf_receipt():
    from email import policy
    from email.parser import BytesParser
    import io
    from pypdf import PdfReader
    from app.email_service import format_email_subject
    from app.receipt_pdf import resolve_payment_method_label

    # 1. Subject normalization & deduplication
    assert format_email_subject("Xác minh địa chỉ email") == "[AuraMeme] - Xác minh địa chỉ email"
    assert format_email_subject("[AuraMeme] - Đặt lại mật khẩu") == "[AuraMeme] - Đặt lại mật khẩu"
    assert format_email_subject("[AuraMeme] - [AuraMeme] - Tiếp nhận góp ý") == "[AuraMeme] - Tiếp nhận góp ý"
    assert format_email_subject("AuraMeme — Xác minh địa chỉ email") == "[AuraMeme] - Xác minh địa chỉ email"

    # 2. Payment method label differentiation
    assert resolve_payment_method_label("sandbox_simulated", "SIM-CARD-123") == "Thẻ mô phỏng nội bộ"
    assert resolve_payment_method_label("paypal_sandbox", "SIM-PP-123") == "PayPal mô phỏng nội bộ"
    assert resolve_payment_method_label("paypal_sandbox", "MOCK-PP-123") == "PayPal mô phỏng nội bộ"
    assert resolve_payment_method_label("paypal_sandbox", "78B98765ABC12345") == "PayPal Sandbox"

    svc = EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="thothayvtv38@gmail.com",
            email_from_name="AuraMeme - No Reply",
            app_public_url="http://localhost:5173",
        )
    )

    # 3. Verification, Reset, Contact, and Receipt emails all embed CID PNG logo and standardized subject
    svc.send_account_verification_email(
        to_email="u1@example.com",
        display_name="User One",
        verify_url="http://localhost:5173/verify-email?token=tok1234567890123456",
    )
    svc.send_password_reset_email(
        to_email="u1@example.com",
        display_name="User One",
        reset_url="http://localhost:5173/reset-password?token=rst1234567890123456",
    )
    svc.send_contact_emails(
        contact_id="c-ref-999",
        sender_name="User One",
        sender_email="u1@example.com",
        subject_line="Hỏi đáp kỹ thuật <script>alert(1)</script>",
        message_body="Dòng 1\nDòng 2 dài tự động xuống dòng",
    )

    # Non-completed orders must NOT send receipt email or attach PDF
    for bad_status in ("pending", "expired", "cancelled", "failed"):
        res_bad = svc.send_premium_receipt_email(
            to_email="u1@example.com",
            display_name="User One",
            order_code=f"AM-BAD-{bad_status.upper()}",
            tier="plus",
            amount_vnd_formatted="130.000 VNĐ",
            amount_usd_formatted="$5",
            provider="sandbox_simulated",
            completed_at_iso="2026-11-23T01:00:00Z",
            order_status=bad_status,
        )
        assert res_bad.status == "disabled"

    # Completed order sends receipt email with inline CID logo + application/pdf attachment
    svc.send_premium_receipt_email(
        to_email="u1@example.com",
        display_name="User One",
        order_code="AM-PRIME-20261123-TEST99",
        tier="prime",
        amount_vnd_formatted="1.250.000 VNĐ",
        amount_usd_formatted="$50",
        provider="sandbox_simulated",
        provider_txn_id="SIM-CARD-999888",
        completed_at_iso="2026-11-23T02:00:00Z",
        username="user_one_tag",
    )

    assert len(svc.sandbox_outbox) == 4
    expected_subjects = [
        "[AuraMeme] - Xác minh địa chỉ email",
        "[AuraMeme] - Đặt lại mật khẩu",
        "[AuraMeme] - Tiếp nhận góp ý",
        "[AuraMeme] - Biên nhận thanh toán Aura Prime",
    ]
    for item, exp_subj in zip(svc.sandbox_outbox, expected_subjects):
        assert item["subject"] == exp_subj
        assert item["inline_logo_cid"] == "aurameme-logo"
        assert item["inline_logo_size"] > 1000
        parsed = BytesParser(policy=policy.default).parsebytes(item["raw_mime"])
        assert parsed["Subject"] == exp_subj
        # Check inline image/png part exists in MIME tree
        png_parts = [p for p in parsed.walk() if p.get_content_type() == "image/png"]
        assert len(png_parts) == 1
        assert "<aurameme-logo>" in (png_parts[0].get("Content-ID") or "")

    # Inspect Contact XSS safety and field order
    contact_item = svc.sandbox_outbox[2]
    assert "<script>" not in contact_item["html"]
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in contact_item["html"]
    assert contact_item["html"].index("c-ref-999") < contact_item["html"].index("Hỏi đáp kỹ thuật") < contact_item["html"].index("Dòng 1")

    # Inspect Receipt MIME PDF attachment and extract text via pypdf
    receipt_item = svc.sandbox_outbox[3]
    assert "Thẻ mô phỏng nội bộ" in receipt_item["text"]
    assert "Thẻ mô phỏng nội bộ (Sandbox)" not in receipt_item["text"]
    parsed_receipt = BytesParser(policy=policy.default).parsebytes(receipt_item["raw_mime"])
    pdf_parts = [p for p in parsed_receipt.walk() if p.get_content_type() == "application/pdf"]
    assert len(pdf_parts) == 1
    assert pdf_parts[0].get_filename() == "AuraMeme-Receipt-AM-PRIME-20261123-TEST99.pdf"
    pdf_payload = pdf_parts[0].get_payload(decode=True)
    reader = PdfReader(io.BytesIO(pdf_payload))
    assert len(reader.pages) == 1
    pdf_text = reader.pages[0].extract_text()
    assert "AM-PRIME-20261123-TEST99" in pdf_text
    assert "@user_one_tag" in pdf_text
    assert "Aura Prime" in pdf_text
    assert "Thẻ mô phỏng nội bộ" in pdf_text
    assert "AuraMeme Community" in pdf_text
    assert "https://aurameme.com" in pdf_text
    assert "AuraSpark Global Inc." in pdf_text
    assert "Hỗ trợ / Support: thothayvtv38@gmail.com" in pdf_text
    assert "Dự án phi thương mại" in pdf_text
    assert "AuraMeme Sandbox" not in pdf_text
    assert "AuraMeme Project" not in pdf_text
    assert "AuraMeme Education & Sandbox" not in pdf_text
    assert "sammybkhang" not in pdf_text


def test_contact_identity_lock_overrides_spoofed_client_fields():
    from uuid import uuid4
    from app.contact import ContactInput, send_contact

    user_id = uuid4()
    fake_user = SimpleNamespace(id=user_id, username="real_cultivator", email="real.user@aurameme.com")
    fake_profile = SimpleNamespace(display_name="Real Cultivator Name")
    added_rows = []
    fake_db = SimpleNamespace(
        get=lambda model, pk: fake_profile if pk == user_id else None,
        add=lambda row: added_rows.append(row),
        flush=lambda: None,
    )
    fake_account = SimpleNamespace(db=fake_db, user=fake_user)
    sent_contacts = []
    fake_request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                auth=SimpleNamespace(
                    limiter=SimpleNamespace(check=lambda *a, **kw: None),
                    now=lambda: datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc),
                ),
                email_service=SimpleNamespace(
                    send_contact_emails=lambda **kw: sent_contacts.append(kw),
                ),
            )
        )
    )

    payload = ContactInput(
        name="Spoofed Attacker Name",
        email="victim@otherdomain.com",
        subject="Báo lỗi kỹ thuật",
        body="Testing identity lock on contact submission.",
    )
    res = send_contact(payload, fake_request, fake_account)
    assert res.status == "new"
    assert len(added_rows) == 1
    saved = added_rows[0]
    assert saved.name == "Real Cultivator Name"
    assert saved.email == "real.user@aurameme.com"
    assert len(sent_contacts) == 1
    assert sent_contacts[0]["sender_name"] == "Real Cultivator Name"
    assert sent_contacts[0]["sender_email"] == "real.user@aurameme.com"


