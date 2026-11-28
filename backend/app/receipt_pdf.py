"""Authoritative backend A4 PDF receipt renderer matching frontend/src/receipt-pdf.js.

Uses ReportLab (BSD) for PDF generation and Pillow (MIT-CMU) for PNG preview rendering,
both using the embedded Apache-2.0 Google Roboto Regular & Bold Unicode TTF fonts so
Vietnamese diacritics, layout, issuer metadata, and sandbox disclaimers match the web PDF.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MM = 72.0 / 25.4
A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
A4_WIDTH_PT = A4_WIDTH_MM * MM
A4_HEIGHT_PT = A4_HEIGHT_MM * MM

ROBOTO_JS_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "fonts" / "roboto-fonts.js"

_FONTS_REGISTERED = False


@lru_cache(maxsize=1)
def _load_roboto_font_bytes() -> tuple[bytes, bytes]:
    content = ROBOTO_JS_PATH.read_text(encoding="utf-8")
    reg_match = re.search(r'ROBOTO_REGULAR_B64\s*=\s*"([^"]+)"', content)
    bold_match = re.search(r'ROBOTO_BOLD_B64\s*=\s*"([^"]+)"', content)
    if not reg_match or not bold_match:
        raise RuntimeError("Unable to load embedded Roboto fonts from roboto-fonts.js")
    return base64.b64decode(reg_match.group(1)), base64.b64decode(bold_match.group(1))


def _ensure_reportlab_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    reg_bytes, bold_bytes = _load_roboto_font_bytes()
    pdfmetrics.registerFont(TTFont("Roboto", BytesIO(reg_bytes)))
    pdfmetrics.registerFont(TTFont("RobotoBold", BytesIO(bold_bytes)))
    _FONTS_REGISTERED = True


def resolve_payment_method_label(
    provider: str | None,
    provider_txn_id: str | None = None,
    payment_method: str | None = None,
) -> str:
    """Authoritative Vietnamese label for payment method in email and PDF receipts."""
    txn = (provider_txn_id or "").strip()
    prov = (provider or "").strip()
    method = (payment_method or "").strip()

    if not prov or prov == "unselected":
        return "Chưa chọn"
    if prov == "sandbox_simulated" or method == "card" or txn.startswith("SIM-CARD-"):
        return "Thẻ mô phỏng nội bộ"
    if prov == "paypal_sandbox":
        return "PayPal Sandbox"
    if prov == "vnpay_sandbox":
        if txn.startswith(("SIM-", "MOCK-")):
            return "VNPAY mô phỏng nội bộ"
        return "VNPAY Sandbox"
    return prov


def format_receipt_date(val: Any) -> str:
    """Safely format any datetime / ISO string / timestamp to DD/MM/YYYY HH:mm:ss."""
    dt: datetime | None = None
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, (int, float)):
        ts = val if val < 1e11 else val / 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            dt = None
    elif isinstance(val, str) and val.strip():
        raw = val.strip()
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
        except Exception:
            dt = None
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def _rl_color(rgb: tuple[int, int, int]) -> Color:
    return Color(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def _wrap_text(text: str, max_width_mm: float, *, bold: bool = False, size: float = 6.5) -> list[str]:
    _ensure_reportlab_fonts()
    font_name = "RobotoBold" if bold else "Roboto"
    max_pt = max_width_mm * MM
    s = str(text or "")
    if pdfmetrics.stringWidth(s, font_name, size) <= max_pt:
        return [s]
    lines: list[str] = []
    cur = ""
    for ch in s:
        if pdfmetrics.stringWidth(cur + ch, font_name, size) > max_pt and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines or ["—"]


def _build_receipt_pages(
    order: dict[str, Any],
    *,
    username: str = "user",
    recent_successful_orders: list[dict[str, Any]] | None = None,
) -> list[list[tuple[Any, ...]]] | None:
    """Build declarative A4 drawing operations for each page of the receipt."""
    status = str(order.get("status") or "").lower()
    if status not in ("success", "completed"):
        return None

    _ensure_reportlab_fonts()

    order_code = str(order.get("order_code") or order.get("orderCode") or "AM-ORDER")
    tier = str(order.get("tier") or "plus").lower().replace("aura ", "")
    is_prime = tier == "prime"
    tier_title = "Aura Prime" if is_prime else "Aura Plus"
    duration_days = int(order.get("duration_days") or (365 if is_prime else 30))

    amount_cents = order.get("amount_usd_cents") or order.get("amount_cents")
    if amount_cents is None:
        amount_cents = 5000 if is_prime else 500
    amount_usd_formatted = f"{int(amount_cents) / 100:.2f} USD"

    amount_vnd = order.get("amount_vnd")
    if amount_vnd is not None:
        amount_vnd_formatted = f"{int(amount_vnd):,}".replace(",", ".") + " VNĐ"
    else:
        amount_vnd_formatted = str(order.get("amount_vnd_formatted") or ("1.250.000 VNĐ" if is_prime else "130.000 VNĐ"))

    txn_ref = str(order.get("provider_txn_id") or order.get("paypal_order_id") or order_code)
    provider_name = resolve_payment_method_label(
        order.get("provider"),
        order.get("provider_txn_id"),
        order.get("payment_method"),
    )
    clean_username = str(order.get("owner_username") or username or "user").lstrip("@")

    raw_date = order.get("completed_at") or order.get("created_at")
    date_formatted = format_receipt_date(raw_date)
    date_only = date_formatted.split(" ")[0]

    pages: list[list[tuple[Any, ...]]] = [[]]
    page = pages[0]

    def draw_text(
        p: list[tuple[Any, ...]],
        text: str,
        x_mm: float,
        y_mm: float,
        *,
        bold: bool = False,
        size: float = 8.5,
        color: tuple[int, int, int] = (17, 24, 39),
        align: str = "left",
    ) -> None:
        p.append(("text", str(text or ""), x_mm, y_mm, bold, size, color, align))

    def draw_rect(
        p: list[tuple[Any, ...]],
        x1_mm: float,
        y1_mm: float,
        x2_mm: float,
        y2_mm: float,
        *,
        stroke: tuple[int, int, int] | None = None,
        fill: tuple[int, int, int] | None = None,
        width_mm: float = 0.25,
        radius_mm: float = 0.0,
    ) -> None:
        p.append(("rect", x1_mm, y1_mm, x2_mm, y2_mm, stroke, fill, width_mm, radius_mm))

    def draw_line(
        p: list[tuple[Any, ...]],
        x1_mm: float,
        y1_mm: float,
        x2_mm: float,
        y2_mm: float,
        *,
        color: tuple[int, int, int],
        width_mm: float = 0.25,
    ) -> None:
        p.append(("line", x1_mm, y1_mm, x2_mm, y2_mm, color, width_mm))

    accent_color = (245, 158, 11) if is_prime else (6, 182, 212)

    # 1. HEADER
    draw_text(page, "AURAMEME", 20, 26, bold=True, size=22, color=(17, 24, 39))
    draw_text(page, "AuraMeme Community", 20, 31.5, bold=False, size=8.5, color=(107, 114, 128))
    draw_text(page, "https://aurameme.com", 20, 36, bold=False, size=8.5, color=(107, 114, 128))

    draw_text(page, "BIÊN LAI THANH TOÁN", 190, 25, bold=True, size=18, color=(17, 24, 39), align="right")
    draw_text(page, "PAYMENT RECEIPT", 190, 30, bold=False, size=8.5, color=(107, 114, 128), align="right")

    # PAID Badge
    draw_rect(page, 146, 33.5, 190, 40, stroke=(16, 185, 129), fill=(236, 253, 245), width_mm=0.3, radius_mm=1.0)
    draw_text(page, "PAID / ĐÃ THANH TOÁN", 168, 38, bold=True, size=7.5, color=(4, 120, 87), align="center")

    draw_line(page, 20, 43, 190, 43, color=(229, 231, 235), width_mm=0.3)

    # 2. METADATA SECTION
    draw_text(page, "ĐƠN VỊ PHÁT HÀNH / ISSUED BY", 20, 49.5, bold=True, size=7.5, color=(156, 163, 175))
    draw_text(page, "AuraSpark Global Inc.", 20, 56, bold=True, size=9.5, color=(31, 41, 55))
    draw_text(page, "AuraMeme Community", 20, 61.5, bold=False, size=8.5, color=(75, 85, 99))
    draw_text(page, "Hỗ trợ / Support: thothayvtv38@gmail.com", 20, 67, bold=False, size=8.5, color=(75, 85, 99))
    draw_text(page, "Dự án phi thương mại", 20, 73, bold=False, size=7.5, color=(156, 163, 175))

    draw_text(page, "THÔNG TIN GIAO DỊCH / TRANSACTION DETAILS", 105, 49.5, bold=True, size=7.5, color=(156, 163, 175))
    meta_rows = [
        ("Mã đơn hàng / Order Code:", order_code),
        ("Ngày thanh toán / Date:", date_formatted),
        ("Phương thức / Method:", provider_name),
        ("Tài khoản / Customer:", f"@{clean_username}"),
        ("Mã tham chiếu / Reference:", txn_ref),
    ]
    for idx, (lbl, val) in enumerate(meta_rows):
        cur_y = 56 + idx * 5.5
        draw_text(page, lbl, 105, cur_y, bold=False, size=8, color=(107, 114, 128))
        val_size = 7.0 if len(val) > 28 else (7.5 if len(val) > 22 else 8.0)
        draw_text(page, val, 190, cur_y, bold=True, size=val_size, color=(17, 24, 39), align="right")

    # 3. HIGHLIGHT PAYMENT SUMMARY BLOCK
    draw_rect(page, 20, 88, 190, 103, stroke=(229, 231, 235), fill=(249, 250, 251), width_mm=0.3)
    draw_rect(page, 20, 88, 23, 103, stroke=accent_color, fill=accent_color, width_mm=0.3)

    draw_text(page, f"{amount_usd_formatted} paid on {date_only}", 27, 97.5, bold=True, size=12, color=(17, 24, 39))
    draw_text(page, f"Giá tham khảo: {amount_vnd_formatted}", 186, 97.5, bold=False, size=8.5, color=(107, 114, 128), align="right")

    # 4. ITEMIZED SERVICES TABLE
    table_y = 112.0
    draw_rect(page, 20, table_y, 190, table_y + 7.5, fill=(243, 244, 246))
    draw_line(page, 20, table_y, 190, table_y, color=(209, 213, 219), width_mm=0.25)
    draw_line(page, 20, table_y + 7.5, 190, table_y + 7.5, color=(209, 213, 219), width_mm=0.25)

    draw_text(page, "DỊCH VỤ / DESCRIPTION", 23, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99))
    draw_text(page, "THỜI HẠN / DURATION", 80, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99))
    draw_text(page, "SL / QTY", 120, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99), align="center")
    draw_text(page, "ĐƠN GIÁ / PRICE", 153, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99), align="right")
    draw_text(page, "THÀNH TIỀN / AMOUNT", 188, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99), align="right")

    row_y = table_y + 7.5
    draw_text(page, f"Gói hội viên {tier_title}", 23, row_y + 5.5, bold=True, size=9, color=(17, 24, 39))
    tier_benefit = (
        "Hội viên 365 ngày · Dấu ấn Aura Prime hoàng kim"
        if is_prime
        else "Hội viên 30 ngày · Dấu ấn Aura Plus xanh ngọc"
    )
    draw_text(page, f"{tier_title} Subscription · {tier_benefit}", 23, row_y + 10.5, bold=False, size=7.5, color=(107, 114, 128))
    draw_text(page, f"{duration_days} ngày ({duration_days}d)", 80, row_y + 7, bold=False, size=8, color=(55, 65, 81))
    draw_text(page, "1", 120, row_y + 7, bold=False, size=8, color=(55, 65, 81), align="center")
    draw_text(page, amount_usd_formatted, 153, row_y + 7, bold=False, size=8, color=(55, 65, 81), align="right")
    draw_text(page, amount_usd_formatted, 188, row_y + 7, bold=True, size=8, color=(17, 24, 39), align="right")
    draw_line(page, 20, row_y + 15, 190, row_y + 15, color=(229, 231, 235), width_mm=0.25)

    # 5. TOTALS SECTION
    total_start_y = row_y + 20
    totals = [
        ("Tạm tính / Subtotal:", amount_usd_formatted, False, (107, 114, 128)),
        ("Tổng thanh toán / Total Amount:", amount_usd_formatted, True, (17, 24, 39)),
        ("Đã thanh toán / Amount Paid:", amount_usd_formatted, True, (4, 120, 87)),
    ]
    for idx, (lbl, val, is_final, col) in enumerate(totals):
        cur_y = total_start_y + idx * 5.5
        draw_text(page, lbl, 112, cur_y, bold=is_final, size=9 if is_final else 8, color=col)
        draw_text(page, val, 187, cur_y, bold=is_final, size=9 if is_final else 8, color=col, align="right")

    draw_text(page, f"Giá tham khảo: ~{amount_vnd_formatted}", 187, total_start_y + 19, bold=False, size=7.5, color=(156, 163, 175), align="right")

    # 6. PAYMENT HISTORY SECTION (up to 10 recent successful orders)
    hist_y = total_start_y + 27
    draw_text(page, "LỊCH SỬ THANH TOÁN / PAYMENT HISTORY (10 GẦN NHẤT / LATEST 10)", 20, hist_y, bold=True, size=8.5, color=(31, 41, 55))
    draw_line(page, 20, hist_y + 2.5, 190, hist_y + 2.5, color=(209, 213, 219), width_mm=0.25)

    def draw_hist_header(p: list[tuple[Any, ...]], start_y: float) -> None:
        draw_rect(p, 20, start_y + 3, 190, start_y + 9, fill=(249, 250, 251))
        draw_text(p, "PHƯƠNG THỨC / METHOD", 23, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128))
        draw_text(p, "NGÀY / DATE", 62, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128))
        draw_text(p, "SỐ TIỀN / AMOUNT", 113, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128), align="right")
        draw_text(p, "TRẠNG THÁI / STATUS", 132, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128), align="center")
        draw_text(p, "MÃ THAM CHIẾU / REF", 188, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128), align="right")
        draw_line(p, 20, start_y + 9, 190, start_y + 9, color=(243, 244, 246), width_mm=0.2)

    draw_hist_header(page, hist_y)

    history_list: list[dict[str, Any]] = []
    if recent_successful_orders:
        seen_codes: set[str] = set()
        for item in recent_successful_orders:
            if not item:
                continue
            st = str(item.get("status") or "").lower()
            if st not in ("success", "completed"):
                continue
            code = str(item.get("order_code") or item.get("orderCode") or item.get("id") or "")
            if code and code not in seen_codes:
                seen_codes.add(code)
                history_list.append(item)

    if not history_list:
        history_list.append(order)

    history_list = history_list[:10]
    cur_y = hist_y + 9

    for hist_item in history_list:
        h_provider = resolve_payment_method_label(
            hist_item.get("provider"),
            hist_item.get("provider_txn_id"),
            hist_item.get("payment_method"),
        )
        h_date = format_receipt_date(hist_item.get("completed_at") or hist_item.get("created_at"))
        h_cents = hist_item.get("amount_usd_cents") or hist_item.get("amount_cents")
        if isinstance(h_cents, int):
            h_amount = f"{h_cents / 100:.2f} USD"
        else:
            h_amount = str(hist_item.get("amount_usd_formatted") or amount_usd_formatted)
        h_ref_parts = [str(x) for x in (hist_item.get("order_code"), hist_item.get("provider_txn_id")) if x]
        h_ref = " / ".join(h_ref_parts) or "—"
        ref_lines = _wrap_text(h_ref, 37.0, bold=False, size=6.5)
        row_h = max(5.8, len(ref_lines) * 2.7 + 3.0)

        if cur_y + row_h > 260:
            page = []
            pages.append(page)
            cur_y = 20.0
            draw_text(page, "LỊCH SỬ THANH TOÁN / PAYMENT HISTORY (Tiếp theo / Continued)", 20, cur_y, bold=True, size=8.5, color=(31, 41, 55))
            draw_line(page, 20, cur_y + 2.5, 190, cur_y + 2.5, color=(209, 213, 219), width_mm=0.25)
            draw_hist_header(page, cur_y)
            cur_y += 9.0

        text_y = cur_y + 4.2
        draw_text(page, h_provider, 23, text_y, bold=False, size=7.0, color=(55, 65, 81))
        draw_text(page, h_date, 62, text_y, bold=False, size=7.2, color=(55, 65, 81))
        draw_text(page, h_amount, 113, text_y, bold=False, size=7.5, color=(55, 65, 81), align="right")
        draw_text(page, "HOÀN TẤT", 132, text_y, bold=True, size=7.2, color=(4, 120, 87), align="center")

        for l_idx, line_str in enumerate(ref_lines):
            draw_text(page, line_str, 188, text_y + l_idx * 2.7, bold=False, size=6.5, color=(75, 85, 99), align="right")

        draw_line(page, 20, cur_y + row_h, 190, cur_y + row_h, color=(229, 231, 235), width_mm=0.2)
        cur_y += row_h

    # 7. FOOTER ON ALL PAGES
    total_pages = len(pages)
    disclaimer_primary = (
        "Mô phỏng PayPal nội bộ — Không có giá trị xác nhận thanh toán thực tế."
        if order.get("provider") == "paypal_sandbox" and txn_ref.startswith(("SIM-", "MOCK-"))
        else "Biên lai giao dịch thử nghiệm/mô phỏng — Không có giá trị xác nhận thanh toán thực tế."
    )
    for p_idx, p in enumerate(pages):
        draw_line(p, 20, 268, 190, 268, color=(229, 231, 235), width_mm=0.2)
        draw_text(p, disclaimer_primary, 20, 273.5, bold=False, size=7.5, color=(156, 163, 175))
        draw_text(
            p,
            "Sandbox transaction receipt — For development and verification purposes only.",
            20,
            277.5,
            bold=False,
            size=7.5,
            color=(156, 163, 175),
        )
        draw_text(
            p,
            f"Trang {p_idx + 1} / {total_pages}  (Page {p_idx + 1} of {total_pages})",
            190,
            273.5,
            bold=False,
            size=7.5,
            color=(156, 163, 175),
            align="right",
        )

    return pages


def generate_receipt_pdf_bytes(
    order: dict[str, Any],
    *,
    username: str = "user",
    recent_successful_orders: list[dict[str, Any]] | None = None,
) -> bytes | None:
    """Generate a single/multi-page A4 PDF receipt using ReportLab (BSD license)."""
    pages = _build_receipt_pages(order, username=username, recent_successful_orders=recent_successful_orders)
    if pages is None:
        return None

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(A4_WIDTH_PT, A4_HEIGHT_PT), pageCompression=1)
    c.setTitle(f"AuraMeme Receipt {order.get('order_code') or order.get('orderCode') or ''}".strip())
    c.setAuthor("AuraMeme Community")

    for p_idx, ops in enumerate(pages):
        if p_idx > 0:
            c.showPage()
        for op in ops:
            kind = op[0]
            if kind == "rect":
                _, x1, y1, x2, y2, stroke, fill, width_mm, radius_mm = op
                x_pt = x1 * MM
                y_pt = (A4_HEIGHT_MM - y2) * MM
                w_pt = (x2 - x1) * MM
                h_pt = (y2 - y1) * MM
                c.setLineWidth(width_mm * MM)
                if stroke is not None:
                    c.setStrokeColor(_rl_color(stroke))
                if fill is not None:
                    c.setFillColor(_rl_color(fill))
                do_stroke = 1 if stroke is not None else 0
                do_fill = 1 if fill is not None else 0
                if radius_mm > 0:
                    c.roundRect(x_pt, y_pt, w_pt, h_pt, radius_mm * MM, stroke=do_stroke, fill=do_fill)
                else:
                    c.rect(x_pt, y_pt, w_pt, h_pt, stroke=do_stroke, fill=do_fill)
            elif kind == "line":
                _, x1, y1, x2, y2, color, width_mm = op
                c.setStrokeColor(_rl_color(color))
                c.setLineWidth(width_mm * MM)
                c.line(x1 * MM, (A4_HEIGHT_MM - y1) * MM, x2 * MM, (A4_HEIGHT_MM - y2) * MM)
            elif kind == "text":
                _, text, x_mm, y_mm, bold, size, color, align = op
                font_name = "RobotoBold" if bold else "Roboto"
                c.setFont(font_name, size)
                c.setFillColor(_rl_color(color))
                x_pt = x_mm * MM
                y_pt = (A4_HEIGHT_MM - y_mm) * MM
                if align == "right":
                    c.drawRightString(x_pt, y_pt, text)
                elif align == "center":
                    c.drawCentredString(x_pt, y_pt, text)
                else:
                    c.drawString(x_pt, y_pt, text)

    c.save()
    return buf.getvalue()


def generate_receipt_png_bytes(
    order: dict[str, Any],
    *,
    username: str = "user",
    recent_successful_orders: list[dict[str, Any]] | None = None,
    dpi: int = 180,
) -> bytes | None:
    """Render page 1 of the A4 receipt to PNG using Pillow (MIT-CMU license)."""
    pages = _build_receipt_pages(order, username=username, recent_successful_orders=recent_successful_orders)
    if not pages:
        return None

    px_per_mm = dpi / 25.4
    px_per_pt = dpi / 72.0
    width_px = round(A4_WIDTH_MM * px_per_mm)
    height_px = round(A4_HEIGHT_MM * px_per_mm)

    img = Image.new("RGB", (width_px, height_px), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    reg_bytes, bold_bytes = _load_roboto_font_bytes()

    @lru_cache(maxsize=32)
    def _pil_font(bold: bool, size_pt: float) -> ImageFont.FreeTypeFont:
        data = bold_bytes if bold else reg_bytes
        return ImageFont.truetype(BytesIO(data), size=max(1, round(size_pt * px_per_pt)))

    for op in pages[0]:
        kind = op[0]
        if kind == "rect":
            _, x1, y1, x2, y2, stroke, fill, width_mm, radius_mm = op
            box = (x1 * px_per_mm, y1 * px_per_mm, x2 * px_per_mm, y2 * px_per_mm)
            w_px = max(1, round(width_mm * px_per_mm)) if stroke is not None else 0
            if radius_mm > 0:
                draw.rounded_rectangle(box, radius=round(radius_mm * px_per_mm), fill=fill, outline=stroke, width=w_px)
            else:
                draw.rectangle(box, fill=fill, outline=stroke, width=w_px)
        elif kind == "line":
            _, x1, y1, x2, y2, color, width_mm = op
            draw.line(
                (x1 * px_per_mm, y1 * px_per_mm, x2 * px_per_mm, y2 * px_per_mm),
                fill=color,
                width=max(1, round(width_mm * px_per_mm)),
            )
        elif kind == "text":
            _, text, x_mm, y_mm, bold, size, color, align = op
            anchor = "rs" if align == "right" else ("ms" if align == "center" else "ls")
            draw.text(
                (x_mm * px_per_mm, y_mm * px_per_mm),
                text,
                font=_pil_font(bold, size),
                fill=color,
                anchor=anchor,
            )

    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
