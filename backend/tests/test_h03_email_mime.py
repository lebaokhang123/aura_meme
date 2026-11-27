"""MIME tree, inline CID, disposition, and attachment regression tests for H03.2."""
from __future__ import annotations

from email import message_from_bytes
from email.policy import default as default_policy

from app.config import EmailSettings
from app.email_service import EmailAttachment, EmailService, LOGO_CID


def _make_service() -> EmailService:
    return EmailService(
        EmailSettings(
            email_mode="sandbox",
            email_from_address="noreply@example.com",
            email_from_name="AuraMeme",
            app_public_url="https://aurameme.example.com",
        )
    )


def _assert_clean_inline_logo(raw_mime: bytes, *, expect_pdf: bool = False) -> None:
    parsed = message_from_bytes(raw_mime, policy=default_policy)
    html_part = parsed.get_body(preferencelist=("html",))
    text_part = parsed.get_body(preferencelist=("plain",))
    assert text_part is not None
    assert html_part is not None
    assert f"cid:{LOGO_CID}" in html_part.get_content()
    assert "http://localhost" not in html_part.get_content()
    assert "data:image/" not in html_part.get_content()

    image_parts = [p for p in parsed.walk() if p.get_content_type() == "image/png"]
    assert len(image_parts) == 1
    img = image_parts[0]
    assert img.get("Content-ID") == f"<{LOGO_CID}>"
    assert img.get("X-Attachment-Id") == LOGO_CID
    assert img.get_content_disposition() == "inline"
    assert img.get_filename() is None

    attachments = list(parsed.iter_attachments())
    if expect_pdf:
        pdf_parts = [p for p in attachments if p.get_content_type() == "application/pdf"]
        assert len(pdf_parts) == 1
        assert pdf_parts[0].get_filename() == "AuraMeme-Receipt-AM-H03.pdf"
        assert not any(p.get_content_type() == "image/png" for p in attachments)
    else:
        assert len(attachments) == 0


def test_h03_verification_reset_contact_mime_have_inline_logo_and_no_attachments():
    svc = _make_service()
    svc.send_account_verification_email(
        to_email="user@example.com",
        display_name="Tester",
        verify_url="https://aurameme.example.com/verify-email?token=tok1",
    )
    svc.send_password_reset_email(
        to_email="user@example.com",
        display_name="Tester",
        reset_url="https://aurameme.example.com/reset-password?token=tok2",
    )
    svc.send_contact_emails(
        contact_id="c-123",
        sender_name="Tester",
        sender_email="user@example.com",
        subject_line="Hello",
        message_body="Body",
    )
    assert len(svc.sandbox_outbox) == 3
    for item in svc.sandbox_outbox:
        _assert_clean_inline_logo(item["raw_mime"], expect_pdf=False)


def test_h03_premium_receipt_preserves_pdf_attachment_and_inline_logo():
    svc = _make_service()
    res = svc.send(
        to_email="buyer@example.com",
        subject="Biên nhận thanh toán Aura Prime",
        text_body="Receipt",
        html_body=f'<img src="cid:{LOGO_CID}" alt="AuraMeme" /><p>Receipt</p>',
        attachments=[
            EmailAttachment(
                filename="AuraMeme-Receipt-AM-H03.pdf",
                content=b"%PDF-1.4\n%test\n",
                maintype="application",
                subtype="pdf",
            )
        ],
    )
    assert res.status == "sandbox_captured"
    _assert_clean_inline_logo(svc.sandbox_outbox[0]["raw_mime"], expect_pdf=True)
