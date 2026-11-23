"""Shared transactional email service for Password Reset, Contact, and Premium Receipts.

Security & operational guarantees:
- Never spoofs an unverified domain (e.g., no-reply@aurameme.com requires email_domain_verified=True).
- Never logs passwords, reset tokens, CVV, or SMTP credentials.
- Supports disabled / sandbox / smtp modes cleanly with bounded retry & idempotency deduplication.
- Email delivery errors never roll back a confirmed payment capture or contact record.
"""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
import logging
import smtplib
import threading
from typing import Literal

from app.config import EmailSettings

logger = logging.getLogger("aurameme.email")

EmailDeliveryStatus = Literal["sent", "sandbox_captured", "disabled", "duplicate_skipped", "failed"]


@dataclass(frozen=True)
class EmailResult:
    status: EmailDeliveryStatus
    dedupe_key: str | None = None
    error_code: str | None = None


def _html_shell(title: str, preheader: str, body_html: str, public_url: str) -> str:
    safe_title = escape(title)
    safe_preheader = escape(preheader)
    safe_url = escape(public_url.rstrip("/"))
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background-color:#12131b;color:#e3e1ed;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{safe_preheader}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#12131b;padding:28px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:580px;background-color:#1a1b23;border:1px solid #292932;border-radius:14px;overflow:hidden;">
          <tr>
            <td style="padding:22px 28px;border-bottom:1px solid #292932;background:linear-gradient(120deg,#1e1f27 0%,#261a47 65%,#12283a 100%);">
              <a href="{safe_url}" style="text-decoration:none;color:#e9ddff;font-size:20px;font-weight:800;letter-spacing:-0.02em;">AuraMeme</a>
              <div style="margin-top:4px;font-size:12px;color:#cac4d0;">{safe_title}</div>
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
        self.sandbox_outbox: list[dict] = []

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

    def send(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        dedupe_key: str | None = None,
        reply_to: str | None = None,
    ) -> EmailResult:
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

        if self.settings.email_mode == "sandbox":
            with self._lock:
                self.sandbox_outbox.append(
                    {
                        "from": formataddr((self.settings.email_from_name, sender_addr)),
                        "to": to_email,
                        "reply_to": effective_reply_to,
                        "subject": subject,
                        "text": text_body,
                        "html": html_body,
                        "dedupe_key": dedupe_key,
                    }
                )
            logger.info("email_captured status=sandbox_captured")
            return EmailResult(status="sandbox_captured", dedupe_key=dedupe_key)

        # SMTP mode with bounded 2-attempt delivery
        if not self.settings.smtp_host:
            self._release_dedupe(dedupe_key)
            return EmailResult(status="failed", dedupe_key=dedupe_key, error_code="SMTP_HOST_MISSING")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((self.settings.email_from_name, sender_addr))
        msg["To"] = to_email
        if effective_reply_to:
            msg["Reply-To"] = effective_reply_to
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

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
    # Domain Templates (A. Password Reset, B. Contact, C. Premium Receipt)
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
        subject = "Đặt lại mật khẩu tài khoản AuraMeme"
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
        html_body = _html_shell("Khôi phục mật khẩu", "Liên kết đặt lại mật khẩu AuraMeme (hiệu lực 30 phút)", body_html, self.settings.app_public_url)
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
        subject = "AuraMeme — Xác minh tài khoản của bạn"
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
        html_body = _html_shell("Xác minh tài khoản", "Kích hoạt tài khoản AuraMeme của bạn", body_html, self.settings.app_public_url)
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
        results: dict[str, EmailResult] = {}
        admin_inbox = (self.settings.email_admin_inbox or "").strip()
        if admin_inbox:
            admin_subject = f"[AuraMeme Contact] {subject_line[:120]}"
            admin_text = (
                f"Liên hệ mới #{contact_id}\n"
                f"Người gửi: {sender_name} <{sender_email}>\n"
                f"Chủ đề: {subject_line}\n\n"
                f"{message_body}\n"
            )
            admin_html = _html_shell(
                "Thông báo Liên hệ / Góp ý mới",
                f"Tin nhắn mới từ {sender_name}",
                f"""
                <p style="margin:0 0 12px;"><strong>Mã tiếp nhận:</strong> <code>{escape(contact_id)}</code></p>
                <p style="margin:0 0 12px;"><strong>Người gửi:</strong> {escape(sender_name)} ({escape(sender_email)})</p>
                <p style="margin:0 0 12px;"><strong>Chủ đề:</strong> {escape(subject_line)}</p>
                <div style="padding:14px;border-radius:10px;background-color:#12131b;border:1px solid #292932;white-space:pre-wrap;">{escape(message_body)}</div>
                """,
                self.settings.app_public_url,
            )
            results["admin"] = self.send(
                to_email=admin_inbox,
                subject=admin_subject,
                text_body=admin_text,
                html_body=admin_html,
                dedupe_key=f"contact:admin:{contact_id}",
                reply_to=sender_email,
            )

        ack_subject = "AuraMeme đã tiếp nhận góp ý của bạn"
        ack_text = (
            f"Xin chào {sender_name},\n\n"
            f"AuraMeme đã tiếp nhận tin nhắn của bạn với chủ đề: {subject_line}\n"
            f"Mã tham chiếu: {contact_id}\n\n"
            f"Đội ngũ quản trị sẽ xem xét và phản hồi trong thời gian sớm nhất.\n"
        )
        ack_html = _html_shell(
            "Xác nhận tiếp nhận liên hệ",
            "AuraMeme đã nhận được góp ý của bạn",
            f"""
            <p style="margin:0 0 12px;">Xin chào <strong>{escape(sender_name)}</strong>,</p>
            <p style="margin:0 0 12px;">Cảm ơn bạn đã gửi góp ý tới AuraMeme. Chúng tôi đã ghi nhận nội dung của bạn với thông tin sau:</p>
            <p style="margin:0 0 8px;"><strong>Chủ đề:</strong> {escape(subject_line)}</p>
            <p style="margin:0 0 16px;"><strong>Mã tham chiếu:</strong> <code>{escape(contact_id)}</code></p>
            <p style="margin:0;color:#cac4d0;">Đội ngũ quản trị sẽ xem xét và phản hồi qua email khi cần thiết.</p>
            """,
            self.settings.app_public_url,
        )
        results["ack"] = self.send(
            to_email=sender_email,
            subject=ack_subject,
            text_body=ack_text,
            html_body=ack_html,
            dedupe_key=f"contact:ack:{contact_id}",
        )
        return results

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
    ) -> EmailResult:
        tier_label = "Aura Prime" if tier == "prime" else "Aura Plus"
        if provider == "paypal_sandbox":
            provider_label = "PayPal Sandbox (Thử nghiệm)"
        elif provider == "sandbox_simulated":
            provider_label = "Thẻ mô phỏng nội bộ (Sandbox)"
        else:
            provider_label = provider
        history_url = f"{self.settings.app_public_url.rstrip('/')}/premium/history"
        subject = f"Biên nhận thanh toán {tier_label} — {order_code}"
        text_body = (
            f"Xin chào {display_name},\n\n"
            f"Giao dịch nâng cấp gói hội viên của bạn đã hoàn tất:\n"
            f"- Mã đơn hàng: {order_code}\n"
            f"- Gói hội viên: {tier_label}\n"
            f"- Số tiền: {amount_vnd_formatted} ({amount_usd_formatted})\n"
            f"- Phương thức: {provider_label}\n"
            f"- Thời gian: {completed_at_iso}\n\n"
            f"Xem lại lịch sử giao dịch và tải biên lai PDF tại: {history_url}\n"
        )
        body_html = f"""
          <p style="margin:0 0 14px;">Xin chào <strong>{escape(display_name)}</strong>,</p>
          <p style="margin:0 0 16px;">Giao dịch nâng cấp hội viên AuraMeme của bạn đã được xác nhận thành công.</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="8" style="background-color:#12131b;border:1px solid #292932;border-radius:10px;margin-bottom:20px;font-size:13px;">
            <tr><td style="color:#948f9a;">Mã đơn hàng</td><td align="right" style="color:#4cd7f6;font-family:monospace;font-weight:700;">{escape(order_code)}</td></tr>
            <tr><td style="color:#948f9a;">Gói hội viên</td><td align="right" style="font-weight:700;">{escape(tier_label)}</td></tr>
            <tr><td style="color:#948f9a;">Số tiền</td><td align="right" style="font-weight:700;">{escape(amount_vnd_formatted)} ({escape(amount_usd_formatted)})</td></tr>
            <tr><td style="color:#948f9a;">Phương thức</td><td align="right">{escape(provider_label)}</td></tr>
            <tr><td style="color:#948f9a;">Thời gian xác nhận</td><td align="right">{escape(completed_at_iso)}</td></tr>
          </table>
          <p style="margin:0;text-align:center;">
            <a href="{escape(history_url)}" style="display:inline-block;padding:11px 22px;border-radius:10px;background-color:#5424af;color:#ffffff;font-weight:700;text-decoration:none;">Xem lịch sử &amp; tải biên lai PDF</a>
          </p>
        """
        html_body = _html_shell("Biên nhận thanh toán hội viên", f"Xác nhận đơn hàng {order_code}", body_html, self.settings.app_public_url)
        return self.send(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            dedupe_key=f"premium:receipt:{order_code}",
        )
