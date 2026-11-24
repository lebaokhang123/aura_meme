"""Shared transactional email service for Account Verification, Password Reset, Contact, and Premium Receipts.

Security & operational guarantees:
- Never spoofs an unverified domain (e.g., no-reply@aurameme.com requires email_domain_verified=True).
- Never logs passwords, reset tokens, CVV, or SMTP credentials.
- Embeds official AuraMeme logo via inline CID PNG (cid:aurameme-logo) so Gmail renders it without external/localhost links.
- Enforces standardized subject prefix '[AuraMeme] - <Tiêu đề>' across all transactional emails.
- Attaches authoritative A4 PDF receipt ('application/pdf') to completed Premium receipt emails.
- Supports disabled / sandbox / smtp modes cleanly with bounded retry & idempotency deduplication.
- Email delivery errors never roll back a confirmed payment capture or contact record.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from functools import lru_cache
from html import escape
import logging
from pathlib import Path
import re
import smtplib
import threading
from typing import Any, Literal

from app.config import EmailSettings
from app.receipt_pdf import generate_receipt_pdf_bytes, resolve_payment_method_label

logger = logging.getLogger("aurameme.email")

EmailDeliveryStatus = Literal["sent", "sandbox_captured", "disabled", "duplicate_skipped", "failed"]

LOGO_CID = "aurameme-logo"
LOGO_PNG_PATH = Path(__file__).resolve().parents[2] / "frontend" / "public" / "assets" / "brand" / "favicon-64.png"
SUBJECT_PREFIX = "[AuraMeme] - "


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    maintype: str = "application"
    subtype: str = "pdf"

    @property
    def content_type(self) -> str:
        return f"{self.maintype}/{self.subtype}"


@dataclass(frozen=True)
class EmailResult:
    status: EmailDeliveryStatus
    dedupe_key: str | None = None
    error_code: str | None = None


@lru_cache(maxsize=1)
def _load_logo_png_bytes() -> bytes:
    if LOGO_PNG_PATH.is_file():
        return LOGO_PNG_PATH.read_bytes()
    return b""


def format_email_subject(title: str) -> str:
    """Normalize any transactional email subject to '[AuraMeme] - <Tiêu đề>' without duplicate prefixes."""
    cleaned = (title or "").strip()
    cleaned = re.sub(
        r"^(?:\[\s*aurameme(?:\s+contact)?\s*\]\s*[-—:]?\s*|aurameme\s*[-—:]\s*)+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if not cleaned:
        cleaned = "Thông báo hệ thống"
    return f"{SUBJECT_PREFIX}{cleaned}"


def render_email_preview_html(html_body: str) -> str:
    """Replace cid:aurameme-logo with data:image/png;base64,... for local browser QA previewing."""
    logo_bytes = _load_logo_png_bytes()
    if not logo_bytes:
        return html_body
    b64 = base64.b64encode(logo_bytes).decode("ascii")
    return html_body.replace(f"cid:{LOGO_CID}", f"data:image/png;base64,{b64}")


def _html_shell(
    title: str,
    preheader: str,
    body_html: str,
    public_url: str,
    *,
    logo_src: str = f"cid:{LOGO_CID}",
) -> str:
    safe_title = escape(title)
    safe_preheader = escape(preheader)
    safe_url = escape(public_url.rstrip("/"))
    safe_logo_src = escape(logo_src)
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background-color:#12131b;color:#e3e1ed;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{safe_preheader}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#12131b;padding:28px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:580px;background-color:#1a1b23;border:1px solid #292932;border-radius:14px;overflow:hidden;">
          <tr>
            <td style="padding:20px 28px;border-bottom:1px solid #292932;background:linear-gradient(120deg,#1e1f27 0%,#261a47 65%,#12283a 100%);">
              <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td valign="middle" style="padding-right:12px;">
                    <a href="{safe_url}" style="text-decoration:none;display:inline-block;vertical-align:middle;">
                      <img src="{safe_logo_src}" alt="AuraMeme" width="38" height="38" style="display:block;width:38px;height:38px;border:0;border-radius:9px;outline:none;text-decoration:none;background-color:#12131b;color:#e9ddff;font-size:11px;font-weight:700;" />
                    </a>
                  </td>
                  <td valign="middle">
                    <a href="{safe_url}" style="text-decoration:none;color:#e9ddff;font-size:20px;font-weight:800;letter-spacing:-0.02em;line-height:1.2;display:block;">Aura<span style="color:#4cd7f6;">Meme</span></a>
                    <div style="margin-top:3px;font-size:12px;color:#cac4d0;line-height:1.35;">{safe_title}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;font-size:14px;line-height:1.65;color:#e3e1ed;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:18px 28px;border-top:1px solid #292932;font-size:12px;line-height:1.5;color:#948f9a;">
              Email tự động từ hệ thống AuraMeme. Vui lòng không chia sẻ mã bảo mật hoặc liên kết cá nhân cho bất kỳ ai.<br />
              <a href="{safe_url}" style="color:#4cd7f6;text-decoration:none;">{safe_url}</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


class EmailService:
    def __init__(self, settings: EmailSettings, *, max_dedupe: int = 2048):
        self.settings = settings
        self._lock = threading.Lock()
        self._sent_keys: set[str] = set()
        self._max_dedupe = max_dedupe
        self.sandbox_outbox: list[dict[str, Any]] = []

    def resolved_sender(self) -> tuple[str | None, str | None]:
        """Return (from_email, error_code). Refuses unverified aurameme.com spoofing."""
        addr = (self.settings.email_from_address or "").strip()
        if not addr:
            return None, "EMAIL_SENDER_UNCONFIGURED"
        domain = addr.rsplit("@", 1)[-1].lower() if "@" in addr else ""
        if domain == "aurameme.com" and not self.settings.email_domain_verified:
            return None, "EMAIL_DOMAIN_UNVERIFIED"
        return addr, None

    def _claim_dedupe(self, key: str | None) -> bool:
        if not key:
            return True
        with self._lock:
            if key in self._sent_keys:
                return False
            if len(self._sent_keys) >= self._max_dedupe:
                self._sent_keys.clear()
            self._sent_keys.add(key)
            return True

    def _release_dedupe(self, key: str | None) -> None:
        if not key:
            return
        with self._lock:
            self._sent_keys.discard(key)

    def build_mime_message(
        self,
        *,
        sender_addr: str,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> EmailMessage:
        normalized_subject = format_email_subject(subject)
        msg = EmailMessage()
        msg["Subject"] = normalized_subject
        msg["From"] = formataddr((self.settings.email_from_name, sender_addr))
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to

        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        # Embed official AuraMeme PNG logo as inline CID part on the HTML body
        if f"cid:{LOGO_CID}" in html_body:
            logo_bytes = _load_logo_png_bytes()
            html_part = msg.get_body(preferencelist=("html",))
            if html_part is not None and logo_bytes:
                html_part.add_related(
                    logo_bytes,
                    maintype="image",
                    subtype="png",
                    cid=f"<{LOGO_CID}>",
                    filename="aurameme-logo.png",
                    disposition="inline",
                )

        # Attach binary attachments (e.g., application/pdf receipt)
        for att in attachments or ():
            msg.add_attachment(
                att.content,
                maintype=att.maintype,
                subtype=att.subtype,
                filename=att.filename,
            )

        return msg

    def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        dedupe_key: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
    ) -> EmailResult:
        normalized_subject = format_email_subject(subject)

        if self.settings.email_mode == "disabled":
            logger.info("email_skipped status=disabled dedupe=%s", bool(dedupe_key))
            return EmailResult(status="disabled", dedupe_key=dedupe_key)

        if not self._claim_dedupe(dedupe_key):
            logger.info("email_dedupe_skipped dedupe=%s", dedupe_key)
            return EmailResult(status="duplicate_skipped", dedupe_key=dedupe_key)

        sender_addr, sender_err = self.resolved_sender()
        if sender_err or not sender_addr:
            self._release_dedupe(dedupe_key)
            logger.warning("email_sender_rejected code=%s", sender_err)
            return EmailResult(status="failed", dedupe_key=dedupe_key, error_code=sender_err)

        effective_reply_to = reply_to or self.settings.email_reply_to
        msg = self.build_mime_message(
            sender_addr=sender_addr,
            to_email=to_email,
            subject=normalized_subject,
            text_body=text_body,
            html_body=html_body,
            reply_to=effective_reply_to,
            attachments=attachments,
        )

        if self.settings.email_mode == "sandbox":
            logo_bytes = _load_logo_png_bytes()
            with self._lock:
                self.sandbox_outbox.append(
                    {
                        "from": formataddr((self.settings.email_from_name, sender_addr)),
                        "to": to_email,
                        "reply_to": effective_reply_to,
                        "subject": normalized_subject,
                        "text": text_body,
                        "html": html_body,
                        "preview_html": render_email_preview_html(html_body),
                        "dedupe_key": dedupe_key,
                        "inline_logo_cid": LOGO_CID if f"cid:{LOGO_CID}" in html_body and logo_bytes else None,
                        "inline_logo_size": len(logo_bytes) if f"cid:{LOGO_CID}" in html_body else 0,
                        "attachments": [
                            {
                                "filename": att.filename,
                                "content_type": att.content_type,
                                "content": att.content,
                                "size": len(att.content),
                            }
                            for att in (attachments or ())
                        ],
                        "raw_mime": msg.as_bytes(),
                    }
                )
            logger.info("email_captured status=sandbox_captured")
            return EmailResult(status="sandbox_captured", dedupe_key=dedupe_key)

        # SMTP mode with bounded 2-attempt delivery
        if not self.settings.smtp_host:
            self._release_dedupe(dedupe_key)
            return EmailResult(status="failed", dedupe_key=dedupe_key, error_code="SMTP_HOST_MISSING")

        last_err = "SMTP_DELIVERY_FAILED"
        for attempt in range(2):
            try:
                if self.settings.smtp_use_ssl:
                    with smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
                        self._smtp_auth_and_send(client, msg)
                else:
                    with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
                        client.ehlo()
                        if self.settings.smtp_use_tls:
                            client.starttls()
                            client.ehlo()
                        self._smtp_auth_and_send(client, msg)
                logger.info("email_sent status=sent attempt=%d", attempt + 1)
                return EmailResult(status="sent", dedupe_key=dedupe_key)
            except (smtplib.SMTPException, OSError) as exc:
                last_err = type(exc).__name__
                logger.warning("email_smtp_error attempt=%d error_type=%s", attempt + 1, last_err)

        self._release_dedupe(dedupe_key)
        return EmailResult(status="failed", dedupe_key=dedupe_key, error_code=last_err)

    def _smtp_auth_and_send(self, client: smtplib.SMTP, msg: EmailMessage) -> None:
        if self.settings.smtp_username and self.settings.smtp_password:
            client.login(self.settings.smtp_username, self.settings.smtp_password.get_secret_value())
        client.send_message(msg)

    # ------------------------------------------------------------------
    # Domain Templates (Password Reset, Account Verification, Contact, Premium Receipt)
    # ------------------------------------------------------------------

    def send_password_reset_email(
        self,
        *,
        to_email: str,
        display_name: str,
        reset_url: str,
        expires_minutes: int = 30,
        dedupe_key: str | None = None,
    ) -> EmailResult:
        subject = format_email_subject("Đặt lại mật khẩu")
        text_body = (
            f"Xin chào {display_name},\n\n"
            f"Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản AuraMeme của bạn.\n"
            f"Vui lòng mở liên kết sau để đặt mật khẩu mới (có hiệu lực trong {expires_minutes} phút, chỉ dùng một lần):\n"
            f"{reset_url}\n\n"
            f"Nếu bạn không gửi yêu cầu này, hãy bỏ qua email này. Mật khẩu hiện tại của bạn vẫn an toàn.\n"
        )
        safe_name = escape(display_name)
        safe_link = escape(reset_url)
        body_html = f"""
          <p style="margin:0 0 14px;">Xin chào <strong>{safe_name}</strong>,</p>
          <p style="margin:0 0 18px;">Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản AuraMeme của bạn. Liên kết bên dưới chỉ sử dụng <strong>một lần</strong> và có hiệu lực trong <strong>{expires_minutes} phút</strong>:</p>
          <p style="margin:0 0 22px;text-align:center;">
            <a href="{safe_link}" style="display:inline-block;padding:12px 24px;border-radius:10px;background-color:#5424af;color:#ffffff;font-weight:700;text-decoration:none;">Đặt lại mật khẩu</a>
          </p>
          <p style="margin:0 0 12px;font-size:12px;color:#cac4d0;word-break:break-all;">Nếu nút không hoạt động, hãy sao chép liên kết sau vào trình duyệt:<br /><a href="{safe_link}" style="color:#4cd7f6;">{safe_link}</a></p>
          <p style="margin:0;font-size:12.5px;color:#948f9a;">Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này.</p>
        """
        html_body = _html_shell(
            "Đặt lại mật khẩu",
            "Liên kết đặt lại mật khẩu AuraMeme (hiệu lực 30 phút)",
            body_html,
            self.settings.app_public_url,
        )
        return self.send(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body, dedupe_key=dedupe_key)

    def send_account_verification_email(
        self,
        *,
        to_email: str,
        display_name: str,
        verify_url: str,
        expires_hours: int = 24,
        dedupe_key: str | None = None,
    ) -> EmailResult:
        subject = format_email_subject("Xác minh địa chỉ email")
        text_body = (
            f"Xin chào {display_name},\n\n"
            f"Cảm ơn bạn đã đăng ký tài khoản tại AuraMeme — Cyberpunk Cultivation Meme Community Platform.\n"
            f"Vui lòng mở liên kết sau để kích hoạt tài khoản của bạn (có hiệu lực trong {expires_hours} giờ):\n"
            f"{verify_url}\n\n"
            f"Nếu bạn không thực hiện đăng ký tài khoản này, vui lòng bỏ qua email.\n"
        )
        safe_name = escape(display_name)
        safe_link = escape(verify_url)
        body_html = f"""
          <p style="margin:0 0 14px;">Xin chào <strong>{safe_name}</strong>,</p>
          <p style="margin:0 0 18px;">Cảm ơn bạn đã gia nhập thế giới tu chân AuraMeme. Vui lòng bấm nút bên dưới để <strong>kích hoạt tài khoản</strong> (liên kết có hiệu lực trong <strong>{expires_hours} giờ</strong>):</p>
          <p style="margin:0 0 22px;text-align:center;">
            <a href="{safe_link}" style="display:inline-block;padding:12px 28px;border-radius:10px;background:linear-gradient(135deg,#5424af 0%,#00d4ff 100%);color:#ffffff;font-weight:700;text-decoration:none;box-shadow:0 4px 14px rgba(84,36,175,0.4);">Kích hoạt tài khoản</a>
          </p>
          <p style="margin:0 0 12px;font-size:12px;color:#cac4d0;word-break:break-all;">Nếu nút không hoạt động, hãy sao chép liên kết sau vào trình duyệt:<br /><a href="{safe_link}" style="color:#4cd7f6;">{safe_link}</a></p>
          <p style="margin:0;font-size:12.5px;color:#948f9a;">Nếu bạn không đăng ký tài khoản này, vui lòng bỏ qua email này.</p>
        """
        html_body = _html_shell(
            "Xác minh địa chỉ email",
            "Kích hoạt tài khoản AuraMeme của bạn",
            body_html,
            self.settings.app_public_url,
        )
        return self.send(to_email=to_email, subject=subject, text_body=text_body, html_body=html_body, dedupe_key=dedupe_key)

    def send_contact_emails(
        self,
        *,
        contact_id: str,
        sender_name: str,
        sender_email: str,
        subject_line: str,
        message_body: str,
    ) -> dict[str, EmailResult]:
        """Send a single confirmation email to the user with Reference ID -> Subject -> Content."""
        ack_subject = format_email_subject("Tiếp nhận góp ý")
        ack_text = (
            f"Xin chào {sender_name},\n\n"
            f"Cảm ơn bạn đã liên hệ với AuraMeme. Chúng tôi đã tiếp nhận nội dung sau:\n\n"
            f"Mã tham chiếu: {contact_id}\n"
            f"Chủ đề: {subject_line}\n"
            f"Nội dung:\n{message_body}\n\n"
            f"Đội ngũ quản trị sẽ xem xét và phản hồi khi cần thiết.\n"
        )
        safe_name = escape(sender_name)
        safe_id = escape(contact_id)
        safe_subject = escape(subject_line)
        safe_body = escape(message_body)
        ack_html = _html_shell(
            "Tiếp nhận góp ý",
            f"AuraMeme đã tiếp nhận góp ý #{contact_id}",
            f"""
            <p style="margin:0 0 14px;">Xin chào <strong>{safe_name}</strong>,</p>
            <p style="margin:0 0 16px;">Cảm ơn bạn đã liên hệ với AuraMeme. Chúng tôi đã tiếp nhận nội dung sau:</p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#12131b;border:1px solid #292932;border-radius:10px;margin-bottom:18px;font-size:13.5px;">
              <tr>
                <td style="padding:12px 16px;border-bottom:1px solid #292932;">
                  <strong style="color:#948f9a;display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:3px;">Mã tham chiếu</strong>
                  <code style="color:#4cd7f6;font-family:monospace;font-size:13px;font-weight:700;word-break:break-all;">{safe_id}</code>
                </td>
              </tr>
              <tr>
                <td style="padding:12px 16px;border-bottom:1px solid #292932;">
                  <strong style="color:#948f9a;display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:3px;">Chủ đề</strong>
                  <div style="color:#e3e1ed;font-weight:600;word-break:break-word;overflow-wrap:anywhere;">{safe_subject}</div>
                </td>
              </tr>
              <tr>
                <td style="padding:12px 16px;">
                  <strong style="color:#948f9a;display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:5px;">Nội dung</strong>
                  <div style="color:#e3e1ed;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;line-height:1.6;">{safe_body}</div>
                </td>
              </tr>
            </table>
            <p style="margin:0;color:#cac4d0;font-size:13px;">Đội ngũ quản trị sẽ xem xét và phản hồi khi cần thiết.</p>
            """,
            self.settings.app_public_url,
        )
        ack_res = self.send(
            to_email=sender_email,
            subject=ack_subject,
            text_body=ack_text,
            html_body=ack_html,
            dedupe_key=f"contact:ack:{contact_id}",
        )
        return {"ack": ack_res}

    def send_premium_receipt_email(
        self,
        *,
        to_email: str,
        display_name: str,
        order_code: str,
        tier: str,
        amount_vnd_formatted: str,
        amount_usd_formatted: str,
        provider: str,
        completed_at_iso: str,
        provider_txn_id: str | None = None,
        username: str | None = None,
        order_status: str = "success",
        order_data: dict[str, Any] | None = None,
        recent_orders: list[dict[str, Any]] | None = None,
        receipt_pdf_bytes: bytes | None = None,
    ) -> EmailResult:
        effective_status = str((order_data or {}).get("status") or order_status or "").lower()
        if effective_status not in ("success", "completed"):
            return EmailResult(status="disabled", error_code="ORDER_NOT_COMPLETED")

        norm_tier = (tier or "plus").lower().replace("aura ", "")
        is_prime = norm_tier == "prime"
        tier_label = "Aura Prime" if is_prime else "Aura Plus"
        effective_txn_id = provider_txn_id or (order_data or {}).get("provider_txn_id")
        provider_label = resolve_payment_method_label(provider, effective_txn_id)

        history_url = f"{self.settings.app_public_url.rstrip('/')}/premium/history"
        subject = format_email_subject(f"Biên nhận thanh toán {tier_label}")

        pdf_bytes = receipt_pdf_bytes
        if pdf_bytes is None:
            fallback_order = dict(order_data) if order_data else {
                "order_code": order_code,
                "tier": norm_tier,
                "duration_days": 365 if is_prime else 30,
                "amount_usd_cents": 5000 if is_prime else 500,
                "amount_vnd": 1250000 if is_prime else 130000,
                "amount_vnd_formatted": amount_vnd_formatted,
                "amount_usd_formatted": amount_usd_formatted,
                "status": "success",
                "provider": provider,
                "provider_txn_id": effective_txn_id or order_code,
                "completed_at": completed_at_iso,
            }
            pdf_bytes = generate_receipt_pdf_bytes(
                fallback_order,
                username=username or display_name or "user",
                recent_successful_orders=recent_orders,
            )

        attachments: list[EmailAttachment] = []
        if pdf_bytes:
            attachments.append(
                EmailAttachment(
                    filename=f"AuraMeme-Receipt-{order_code}.pdf",
                    content=pdf_bytes,
                    maintype="application",
                    subtype="pdf",
                )
            )

        text_body = (
            f"Xin chào {display_name},\n\n"
            f"Giao dịch nâng cấp gói hội viên của bạn đã hoàn tất:\n"
            f"- Mã đơn hàng: {order_code}\n"
            f"- Gói hội viên: {tier_label}\n"
            f"- Số tiền: {amount_vnd_formatted} ({amount_usd_formatted})\n"
            f"- Phương thức: {provider_label}\n"
            f"- Thời gian: {completed_at_iso}\n\n"
            f"Biên lai PDF đã được đính kèm trực tiếp trong email này (AuraMeme-Receipt-{order_code}.pdf).\n"
            f"Xem lại lịch sử giao dịch và tải biên lai PDF tại: {history_url}\n\n"
            f"Lưu ý: Đây là giao dịch thử nghiệm/mô phỏng trong môi trường Sandbox giáo dục, không có giá trị xác nhận thanh toán thực tế.\n"
        )
        body_html = f"""
          <p style="margin:0 0 14px;">Xin chào <strong>{escape(display_name)}</strong>,</p>
          <p style="margin:0 0 16px;">Giao dịch nâng cấp hội viên AuraMeme của bạn đã được xác nhận thành công. File biên nhận PDF chính thức đã được đính kèm trực tiếp trong email này.</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="8" style="background-color:#12131b;border:1px solid #292932;border-radius:10px;margin-bottom:16px;font-size:13px;">
            <tr><td style="color:#948f9a;">Mã đơn hàng</td><td align="right" style="color:#4cd7f6;font-family:monospace;font-weight:700;">{escape(order_code)}</td></tr>
            <tr><td style="color:#948f9a;">Gói hội viên</td><td align="right" style="font-weight:700;">{escape(tier_label)}</td></tr>
            <tr><td style="color:#948f9a;">Số tiền</td><td align="right" style="font-weight:700;">{escape(amount_vnd_formatted)} ({escape(amount_usd_formatted)})</td></tr>
            <tr><td style="color:#948f9a;">Phương thức</td><td align="right">{escape(provider_label)}</td></tr>
            <tr><td style="color:#948f9a;">Thời gian xác nhận</td><td align="right">{escape(completed_at_iso)}</td></tr>
          </table>
          <p style="margin:0 0 18px;padding:10px 14px;border-radius:8px;background-color:#15161f;border:1px solid #292932;font-size:12px;color:#948f9a;line-height:1.5;">
            Lưu ý: Đây là biên nhận giao dịch <strong>thử nghiệm/mô phỏng</strong> trong môi trường Sandbox giáo dục, <strong>không có giá trị xác nhận thanh toán thực tế</strong>.
          </p>
          <p style="margin:0;text-align:center;">
            <a href="{escape(history_url)}" style="display:inline-block;padding:11px 22px;border-radius:10px;background-color:#5424af;color:#ffffff;font-weight:700;text-decoration:none;">Xem lịch sử &amp; tải biên lai PDF</a>
          </p>
        """
        html_body = _html_shell(
            f"Biên nhận thanh toán {tier_label}",
            f"Xác nhận đơn hàng {order_code}",
            body_html,
            self.settings.app_public_url,
        )
        return self.send(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            dedupe_key=f"premium:receipt:{order_code}",
            attachments=attachments,
        )
