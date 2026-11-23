"""Authoritative backend A4 PDF receipt renderer matching frontend/src/receipt-pdf.js.

Uses PyMuPDF (fitz) with the embedded Apache-2.0 Google Roboto Regular & Bold Unicode TTF fonts
so Vietnamese diacritics, layout, issuer metadata, and sandbox disclaimers match the web PDF.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import re
from typing import Any

import pymupdf as fitz

MM = 72.0 / 25.4
A4_WIDTH_PT = 210.0 * MM
A4_HEIGHT_PT = 297.0 * MM

ROBOTO_JS_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "fonts" / "roboto-fonts.js"


@lru_cache(maxsize=1)
def _load_roboto_fonts() -> tuple[bytes, bytes, fitz.Font, fitz.Font]:
    content = ROBOTO_JS_PATH.read_text(encoding="utf-8")
    reg_match = re.search(r'ROBOTO_REGULAR_B64\s*=\s*"([^"]+)"', content)
    bold_match = re.search(r'ROBOTO_BOLD_B64\s*=\s*"([^"]+)"', content)
    if not reg_match or not bold_match:
        raise RuntimeError("Unable to load embedded Roboto fonts from roboto-fonts.js")
    reg_bytes = base64.b64decode(reg_match.group(1))
    bold_bytes = base64.b64decode(bold_match.group(1))
    return reg_bytes, bold_bytes, fitz.Font(fontbuffer=reg_bytes), fitz.Font(fontbuffer=bold_bytes)


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
        if txn.startswith(("SIM-", "MOCK-")):
            return "PayPal mô phỏng nội bộ"
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


def _rgb(r: int, g: int, b: int) -> tuple[float, float, float]:
    return (r / 255.0, g / 255.0, b / 255.0)


def _draw_text(
    page: fitz.Page,
    text: str,
    x_mm: float,
    y_mm: float,
    *,
    bold: bool = False,
    size: float = 8.5,
    color: tuple[int, int, int] = (17, 24, 39),
    align: str = "left",
) -> None:
    _, _, font_reg, font_bold = _load_roboto_fonts()
    font_obj = font_bold if bold else font_reg
    font_name = "RobotoBold" if bold else "Roboto"
    s = str(text or "")
    w = font_obj.text_length(s, fontsize=size)
    x_pt = x_mm * MM
    if align == "right":
        x_pt -= w
    elif align == "center":
        x_pt -= w / 2.0
    page.insert_text(
        fitz.Point(x_pt, y_mm * MM),
        s,
        fontname=font_name,
        fontsize=size,
        color=_rgb(*color),
    )


def _wrap_text(text: str, max_width_mm: float, *, bold: bool = False, size: float = 6.5) -> list[str]:
    _, _, font_reg, font_bold = _load_roboto_fonts()
    font_obj = font_bold if bold else font_reg
    max_pt = max_width_mm * MM
    s = str(text or "")
    if font_obj.text_length(s, fontsize=size) <= max_pt:
        return [s]
    lines: list[str] = []
    cur = ""
    for ch in s:
        if font_obj.text_length(cur + ch, fontsize=size) > max_pt and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines or ["—"]


def generate_receipt_pdf_bytes(
    order: dict[str, Any],
    *,
    username: str = "user",
    recent_successful_orders: list[dict[str, Any]] | None = None,
) -> bytes | None:
    """Generate a single/multi-page A4 PDF receipt identical in content & structure to receipt-pdf.js.

    Returns None if order status is not 'success' or 'completed'.
    """
    status = str(order.get("status") or "").lower()
    if status not in ("success", "completed"):
        return None

    reg_bytes, bold_bytes, _, _ = _load_roboto_fonts()

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

    txn_ref = str(order.get("paypal_order_id") or order.get("provider_txn_id") or order_code)
    provider_name = resolve_payment_method_label(
        order.get("provider"),
        order.get("provider_txn_id"),
        order.get("payment_method"),
    )
    clean_username = str(order.get("owner_username") or username or "user").lstrip("@")

    raw_date = order.get("completed_at") or order.get("created_at")
    date_formatted = format_receipt_date(raw_date)
    date_only = date_formatted.split(" ")[0]

    doc = fitz.open()

    def new_styled_page() -> fitz.Page:
        p = doc.new_page(width=A4_WIDTH_PT, height=A4_HEIGHT_PT)
        p.insert_font(fontname="Roboto", fontbuffer=reg_bytes)
        p.insert_font(fontname="RobotoBold", fontbuffer=bold_bytes)
        return p

    page = new_styled_page()
    accent_color = (245, 158, 11) if is_prime else (6, 182, 212)

    # 1. HEADER
    _draw_text(page, "AURAMEME", 20, 26, bold=True, size=22, color=(17, 24, 39))
    _draw_text(page, "AuraMeme Community", 20, 31.5, bold=False, size=8.5, color=(107, 114, 128))
    _draw_text(page, "https://aurameme.com", 20, 36, bold=False, size=8.5, color=(107, 114, 128))

    _draw_text(page, "BIÊN LAI THANH TOÁN", 190, 25, bold=True, size=18, color=(17, 24, 39), align="right")
    _draw_text(page, "PAYMENT RECEIPT", 190, 30, bold=False, size=8.5, color=(107, 114, 128), align="right")

    # PAID Badge
    badge_rect = fitz.Rect(146 * MM, 33.5 * MM, 190 * MM, 40 * MM)
    page.draw_rect(badge_rect, color=_rgb(16, 185, 129), fill=_rgb(236, 253, 245), width=0.3 * MM, radius=0.15)
    _draw_text(page, "PAID / ĐÃ THANH TOÁN", 168, 38, bold=True, size=7.5, color=(4, 120, 87), align="center")

    page.draw_line(fitz.Point(20 * MM, 43 * MM), fitz.Point(190 * MM, 43 * MM), color=_rgb(229, 231, 235), width=0.3 * MM)

    # 2. METADATA SECTION
    _draw_text(page, "ĐƠN VỊ PHÁT HÀNH / ISSUED BY", 20, 49.5, bold=True, size=7.5, color=(156, 163, 175))
    _draw_text(page, "AuraSpark Global Inc.", 20, 56, bold=True, size=9.5, color=(31, 41, 55))
    _draw_text(page, "AuraMeme Community", 20, 61.5, bold=False, size=8.5, color=(75, 85, 99))
    _draw_text(page, "Hỗ trợ / Support: thothayvtv38@gmail.com", 20, 67, bold=False, size=8.5, color=(75, 85, 99))
    _draw_text(page, "Dự án phi thương mại", 20, 73, bold=False, size=7.5, color=(156, 163, 175))

    _draw_text(page, "THÔNG TIN GIAO DỊCH / TRANSACTION DETAILS", 105, 49.5, bold=True, size=7.5, color=(156, 163, 175))
    meta_rows = [
        ("Mã đơn hàng / Order Code:", order_code),
        ("Ngày thanh toán / Date:", date_formatted),
        ("Phương thức / Method:", provider_name),
        ("Tài khoản / Customer:", f"@{clean_username}"),
        ("Mã tham chiếu / Reference:", txn_ref),
    ]
    for idx, (lbl, val) in enumerate(meta_rows):
        cur_y = 56 + idx * 5.5
        _draw_text(page, lbl, 105, cur_y, bold=False, size=8, color=(107, 114, 128))
        val_size = 7.0 if len(val) > 28 else (7.5 if len(val) > 22 else 8.0)
        _draw_text(page, val, 190, cur_y, bold=True, size=val_size, color=(17, 24, 39), align="right")

    # 3. HIGHLIGHT PAYMENT SUMMARY BLOCK
    summary_rect = fitz.Rect(20 * MM, 88 * MM, 190 * MM, 103 * MM)
    page.draw_rect(summary_rect, color=_rgb(229, 231, 235), fill=_rgb(249, 250, 251), width=0.3 * MM)
    accent_rect = fitz.Rect(20 * MM, 88 * MM, 23 * MM, 103 * MM)
    page.draw_rect(accent_rect, color=_rgb(*accent_color), fill=_rgb(*accent_color))

    _draw_text(page, f"{amount_usd_formatted} paid on {date_only}", 27, 97.5, bold=True, size=12, color=(17, 24, 39))
    _draw_text(page, f"Giá tham khảo: {amount_vnd_formatted}", 186, 97.5, bold=False, size=8.5, color=(107, 114, 128), align="right")

    # 4. ITEMIZED SERVICES TABLE
    table_y = 112.0
    page.draw_rect(fitz.Rect(20 * MM, table_y * MM, 190 * MM, (table_y + 7.5) * MM), color=None, fill=_rgb(243, 244, 246))
    page.draw_line(fitz.Point(20 * MM, table_y * MM), fitz.Point(190 * MM, table_y * MM), color=_rgb(209, 213, 219), width=0.25 * MM)
    page.draw_line(fitz.Point(20 * MM, (table_y + 7.5) * MM), fitz.Point(190 * MM, (table_y + 7.5) * MM), color=_rgb(209, 213, 219), width=0.25 * MM)

    _draw_text(page, "DỊCH VỤ / DESCRIPTION", 23, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99))
    _draw_text(page, "THỜI HẠN / DURATION", 80, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99))
    _draw_text(page, "SL / QTY", 120, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99), align="center")
    _draw_text(page, "ĐƠN GIÁ / PRICE", 153, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99), align="right")
    _draw_text(page, "THÀNH TIỀN / AMOUNT", 188, table_y + 5.2, bold=True, size=7.2, color=(75, 85, 99), align="right")

    row_y = table_y + 7.5
    _draw_text(page, f"Gói hội viên {tier_title}", 23, row_y + 5.5, bold=True, size=9, color=(17, 24, 39))
    tier_benefit = (
        "Hội viên 365 ngày · Dấu ấn Aura Prime hoàng kim"
        if is_prime
        else "Hội viên 30 ngày · Dấu ấn Aura Plus xanh ngọc"
    )
    _draw_text(page, f"{tier_title} Subscription · {tier_benefit}", 23, row_y + 10.5, bold=False, size=7.5, color=(107, 114, 128))
    _draw_text(page, f"{duration_days} ngày ({duration_days}d)", 80, row_y + 7, bold=False, size=8, color=(55, 65, 81))
    _draw_text(page, "1", 120, row_y + 7, bold=False, size=8, color=(55, 65, 81), align="center")
    _draw_text(page, amount_usd_formatted, 153, row_y + 7, bold=False, size=8, color=(55, 65, 81), align="right")
    _draw_text(page, amount_usd_formatted, 188, row_y + 7, bold=True, size=8, color=(17, 24, 39), align="right")
    page.draw_line(fitz.Point(20 * MM, (row_y + 15) * MM), fitz.Point(190 * MM, (row_y + 15) * MM), color=_rgb(229, 231, 235), width=0.25 * MM)

    # 5. TOTALS SECTION
    total_start_y = row_y + 20
    totals = [
        ("Tạm tính / Subtotal:", amount_usd_formatted, False, (107, 114, 128)),
        ("Tổng thanh toán / Total Amount:", amount_usd_formatted, True, (17, 24, 39)),
        ("Đã thanh toán / Amount Paid:", amount_usd_formatted, True, (4, 120, 87)),
    ]
    for idx, (lbl, val, is_final, col) in enumerate(totals):
        cur_y = total_start_y + idx * 5.5
        _draw_text(page, lbl, 112, cur_y, bold=is_final, size=9 if is_final else 8, color=col)
        _draw_text(page, val, 187, cur_y, bold=is_final, size=9 if is_final else 8, color=col, align="right")

    _draw_text(page, f"Giá tham khảo: ~{amount_vnd_formatted}", 187, total_start_y + 19, bold=False, size=7.5, color=(156, 163, 175), align="right")

    # 6. PAYMENT HISTORY SECTION (up to 10 recent successful orders)
    hist_y = total_start_y + 27
    _draw_text(page, "LỊCH SỬ THANH TOÁN / PAYMENT HISTORY (10 GẦN NHẤT / LATEST 10)", 20, hist_y, bold=True, size=8.5, color=(31, 41, 55))
    page.draw_line(fitz.Point(20 * MM, (hist_y + 2.5) * MM), fitz.Point(190 * MM, (hist_y + 2.5) * MM), color=_rgb(209, 213, 219), width=0.25 * MM)

    def draw_hist_header(p: fitz.Page, start_y: float) -> None:
        p.draw_rect(fitz.Rect(20 * MM, (start_y + 3) * MM, 190 * MM, (start_y + 9) * MM), color=None, fill=_rgb(249, 250, 251))
        _draw_text(p, "PHƯƠNG THỨC / METHOD", 23, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128))
        _draw_text(p, "NGÀY / DATE", 62, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128))
        _draw_text(p, "SỐ TIỀN / AMOUNT", 113, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128), align="right")
        _draw_text(p, "TRẠNG THÁI / STATUS", 132, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128), align="center")
        _draw_text(p, "MÃ THAM CHIẾU / REF", 188, start_y + 7.2, bold=True, size=6.8, color=(107, 114, 128), align="right")
        p.draw_line(fitz.Point(20 * MM, (start_y + 9) * MM), fitz.Point(190 * MM, (start_y + 9) * MM), color=_rgb(243, 244, 246), width=0.2 * MM)

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
            page = new_styled_page()
            cur_y = 20.0
            _draw_text(page, "LỊCH SỬ THANH TOÁN / PAYMENT HISTORY (Tiếp theo / Continued)", 20, cur_y, bold=True, size=8.5, color=(31, 41, 55))
            page.draw_line(fitz.Point(20 * MM, (cur_y + 2.5) * MM), fitz.Point(190 * MM, (cur_y + 2.5) * MM), color=_rgb(209, 213, 219), width=0.25 * MM)
            draw_hist_header(page, cur_y)
            cur_y += 9.0

        text_y = cur_y + 4.2
        _draw_text(page, h_provider, 23, text_y, bold=False, size=7.0, color=(55, 65, 81))
        _draw_text(page, h_date, 62, text_y, bold=False, size=7.2, color=(55, 65, 81))
        _draw_text(page, h_amount, 113, text_y, bold=False, size=7.5, color=(55, 65, 81), align="right")
        _draw_text(page, "HOÀN TẤT", 132, text_y, bold=True, size=7.2, color=(4, 120, 87), align="center")

        for l_idx, line_str in enumerate(ref_lines):
            _draw_text(page, line_str, 188, text_y + l_idx * 2.7, bold=False, size=6.5, color=(75, 85, 99), align="right")

        page.draw_line(fitz.Point(20 * MM, (cur_y + row_h) * MM), fitz.Point(190 * MM, (cur_y + row_h) * MM), color=_rgb(229, 231, 235), width=0.2 * MM)
        cur_y += row_h

    # 7. FOOTER ON ALL PAGES
    total_pages = len(doc)
    for p_idx in range(total_pages):
        p = doc[p_idx]
        p.draw_line(fitz.Point(20 * MM, 268 * MM), fitz.Point(190 * MM, 268 * MM), color=_rgb(229, 231, 235), width=0.2 * MM)
        _draw_text(
            p,
            "Biên lai giao dịch thử nghiệm/mô phỏng — Không có giá trị xác nhận thanh toán thực tế.",
            20,
            273.5,
            bold=False,
            size=7.5,
            color=(156, 163, 175),
        )
        _draw_text(
            p,
            "Sandbox transaction receipt — For development and verification purposes only.",
            20,
            277.5,
            bold=False,
            size=7.5,
            color=(156, 163, 175),
        )
        _draw_text(
            p,
            f"Trang {p_idx + 1} / {total_pages}  (Page {p_idx + 1} of {total_pages})",
            190,
            273.5,
            bold=False,
            size=7.5,
            color=(156, 163, 175),
            align="right",
        )

    pdf_bytes = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return pdf_bytes
