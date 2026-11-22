import { jsPDF } from 'jspdf';

/**
 * Renders and downloads an authentic, beautifully styled PDF receipt for AuraMeme memberships.
 * Uses high-DPI HTML5 Canvas for flawless Vietnamese typography and SaaS styling,
 * embedded into a standard vector PDF page.
 *
 * @param {Object} order - Order details from API or receipt state
 * @param {Object} [user] - Active authenticated user details
 */
export function downloadReceiptPdf(order, user) {
  if (!order) return;

  const orderCode = order.order_code || order.orderCode || 'AM-ORDER';
  const tier = (order.tier || order.tierName || 'plus').toLowerCase().replace('aura ', '');
  const isPrime = tier === 'prime';
  const tierTitle = isPrime ? 'Aura Prime' : 'Aura Plus';
  const durationDays = order.duration_days || order.durationDays || (isPrime ? 365 : 30);
  const boostMultiplier = order.boost_multiplier || (isPrime ? 3 : 2);
  const amountVnd = order.amount_vnd_formatted || order.amountVnd || (isPrime ? '1.250.000 VNĐ' : '130.000 VNĐ');
  const amountUsd = order.amount_usd_formatted || order.amountUsd || (isPrime ? '$50' : '$5');
  const provider = order.provider === 'paypal_sandbox' ? 'PayPal Sandbox' : 'Thanh toán Thử nghiệm';
  const txnId = order.paypal_order_id || order.provider_txn_id || orderCode;
  const username = user?.username || user?.displayName || 'Thành viên Aura';
  const displayDate = order.completed_at || order.activatedAt || order.created_at || new Date().toISOString();
  const dateFormatted = new Date(displayDate).toLocaleString('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  // A4 dimensions at 2x resolution (for crisp 300DPI equivalent)
  const canvas = document.createElement('canvas');
  const scale = 2;
  const width = 800 * scale;
  const height = 1131 * scale;
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  if (ctx) {
    // 1. Background
    ctx.fillStyle = '#0c0d14';
    ctx.fillRect(0, 0, width, height);

    // Subtle background mesh/glow
    const bgGlow = ctx.createRadialGradient(
      width / 2,
      200 * scale,
      10 * scale,
      width / 2,
      200 * scale,
      450 * scale
    );
    if (isPrime) {
      bgGlow.addColorStop(0, 'rgba(251, 191, 36, 0.15)');
      bgGlow.addColorStop(1, 'rgba(12, 13, 20, 0)');
    } else {
      bgGlow.addColorStop(0, 'rgba(56, 189, 248, 0.15)');
      bgGlow.addColorStop(1, 'rgba(12, 13, 20, 0)');
    }
    ctx.fillStyle = bgGlow;
    ctx.fillRect(0, 0, width, height);

    // Outer decorative border
    ctx.strokeStyle = isPrime ? 'rgba(251, 191, 36, 0.35)' : 'rgba(56, 189, 248, 0.35)';
    ctx.lineWidth = 2 * scale;
    ctx.strokeRect(28 * scale, 28 * scale, (800 - 56) * scale, (1131 - 56) * scale);

    // 2. Header Brand
    ctx.fillStyle = '#ffffff';
    ctx.font = `bold ${24 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('AURAMEME', 48 * scale, 75 * scale);

    // Accent line next to brand
    ctx.fillStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.fillRect(195 * scale, 58 * scale, 3 * scale, 20 * scale);

    ctx.fillStyle = isPrime ? '#fef08a' : '#bae6fd';
    ctx.font = `600 ${12 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('CYBERPUNK CULTIVATION', 208 * scale, 73 * scale);

    // Document Title
    ctx.fillStyle = '#e3e1ed';
    ctx.font = `bold ${20 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('BIÊN LAI THANH TOÁN HỘI VIÊN AURAMEME', 48 * scale, 125 * scale);

    ctx.fillStyle = '#948f9a';
    ctx.font = `500 ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('OFFICIAL MEMBERSHIP SUBSCRIPTION RECEIPT · VERIFIED ELECTRONIC DOCUMENT', 48 * scale, 145 * scale);

    // Top Divider
    ctx.strokeStyle = '#292932';
    ctx.lineWidth = 1 * scale;
    ctx.beginPath();
    ctx.moveTo(48 * scale, 165 * scale);
    ctx.lineTo((800 - 48) * scale, 165 * scale);
    ctx.stroke();

    // 3. Information Grid (2 Columns)
    // Left Box
    const drawInfoBox = (x, y, w, h) => {
      ctx.fillStyle = '#14151f';
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = '#232433';
      ctx.lineWidth = 1 * scale;
      ctx.strokeRect(x, y, w, h);
    };

    const boxW = 340 * scale;
    const boxH = 150 * scale;
    const boxY = 185 * scale;

    // Box 1: Transaction details
    drawInfoBox(48 * scale, boxY, boxW, boxH);
    ctx.fillStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.font = `bold ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('THÔNG TIN GIAO DỊCH', 64 * scale, (boxY / scale + 24) * scale);

    const leftFields = [
      ['Mã đơn hàng:', orderCode],
      ['Ngày giờ GD:', dateFormatted],
      ['Cổng thanh toán:', provider],
      ['Mã tham chiếu:', txnId.length > 24 ? txnId.substring(0, 24) + '...' : txnId],
    ];
    leftFields.forEach(([lbl, val], idx) => {
      const curY = (boxY / scale + 48 + idx * 24) * scale;
      ctx.fillStyle = '#948f9a';
      ctx.font = `500 ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
      ctx.fillText(lbl, 64 * scale, curY);

      ctx.fillStyle = '#e3e1ed';
      ctx.font = `600 ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
      ctx.fillText(val, 160 * scale, curY);
    });

    // Box 2: Customer & Status
    drawInfoBox((48 + 364) * scale, boxY, boxW, boxH);
    ctx.fillStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.font = `bold ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('THÔNG TIN KHÁCH HÀNG', (48 + 364 + 16) * scale, (boxY / scale + 24) * scale);

    const rightFields = [
      ['Tài khoản:', `@${username}`],
      ['Đặc quyền EXP:', `×${boostMultiplier} Level Multiplier`],
      ['Thời hạn kích hoạt:', `${durationDays} ngày`],
      ['Trạng thái:', 'ĐÃ KÍCH HOẠT (ACTIVE)'],
    ];
    rightFields.forEach(([lbl, val], idx) => {
      const curY = (boxY / scale + 48 + idx * 24) * scale;
      ctx.fillStyle = '#948f9a';
      ctx.font = `500 ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
      ctx.fillText(lbl, (48 + 364 + 16) * scale, curY);

      if (lbl === 'Trạng thái:') {
        ctx.fillStyle = '#4ade80';
        ctx.font = `bold ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
      } else {
        ctx.fillStyle = '#e3e1ed';
        ctx.font = `600 ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
      }
      ctx.fillText(val, (48 + 364 + 130) * scale, curY);
    });

    // 4. Itemized Table
    const tableY = 365 * scale;
    ctx.fillStyle = '#181926';
    ctx.fillRect(48 * scale, tableY, (800 - 96) * scale, 34 * scale);

    ctx.fillStyle = '#cac4d0';
    ctx.font = `bold ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('DANH MỤC / GÓI HỘI VIÊN', 64 * scale, (tableY / scale + 22) * scale);
    ctx.fillText('THỜI HẠN', 420 * scale, (tableY / scale + 22) * scale);
    ctx.fillText('ĐƠN GIÁ', 560 * scale, (tableY / scale + 22) * scale);
    ctx.fillText('THÀNH TIỀN', 670 * scale, (tableY / scale + 22) * scale);

    // Row item
    const rowY = tableY + 34 * scale;
    ctx.fillStyle = '#10111a';
    ctx.fillRect(48 * scale, rowY, (800 - 96) * scale, 56 * scale);

    ctx.fillStyle = '#ffffff';
    ctx.font = `bold ${13 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText(tierTitle, 64 * scale, (rowY / scale + 25) * scale);

    ctx.fillStyle = '#948f9a';
    ctx.font = `500 ${10.5 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText(
      isPrime
        ? 'Gói VIP Thượng Thừa · Avatar Hào Quang Vàng · Biểu tượng Kim Cương'
        : 'Gói Tiêu Chuẩn · Avatar Viền Xanh Ngọc · Biểu tượng Huy Hiệu',
      64 * scale,
      (rowY / scale + 42) * scale
    );

    ctx.fillStyle = '#e3e1ed';
    ctx.font = `600 ${12 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText(`${durationDays} ngày`, 420 * scale, (rowY / scale + 30) * scale);
    ctx.fillText(amountVnd, 560 * scale, (rowY / scale + 30) * scale);

    ctx.fillStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.font = `bold ${12 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText(amountVnd, 670 * scale, (rowY / scale + 30) * scale);

    // Table bottom border
    ctx.strokeStyle = '#292932';
    ctx.lineWidth = 1 * scale;
    ctx.strokeRect(48 * scale, tableY, (800 - 96) * scale, 90 * scale);

    // 5. Total Calculation Box
    const totalY = rowY + 56 * scale + 20 * scale;
    ctx.fillStyle = '#14151f';
    ctx.fillRect(470 * scale, totalY, 282 * scale, 90 * scale);
    ctx.strokeStyle = isPrime ? 'rgba(251, 191, 36, 0.4)' : 'rgba(56, 189, 248, 0.4)';
    ctx.strokeRect(470 * scale, totalY, 282 * scale, 90 * scale);

    ctx.fillStyle = '#948f9a';
    ctx.font = `500 ${11 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('Tạm tính:', 490 * scale, (totalY / scale + 26) * scale);
    ctx.fillStyle = '#e3e1ed';
    ctx.fillText(`${amountVnd} (${amountUsd})`, 630 * scale, (totalY / scale + 26) * scale);

    ctx.fillStyle = '#948f9a';
    ctx.fillText('Thuế / Phí:', 490 * scale, (totalY / scale + 48) * scale);
    ctx.fillStyle = '#4ade80';
    ctx.fillText('0 VNĐ (Miễn phí)', 630 * scale, (totalY / scale + 48) * scale);

    ctx.fillStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.font = `bold ${13 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('TỔNG CỘNG:', 490 * scale, (totalY / scale + 74) * scale);
    ctx.fillText(amountVnd, 630 * scale, (totalY / scale + 74) * scale);

    // 6. Cyberpunk Badge / Seal
    const sealX = 64 * scale;
    const sealY = totalY + 15 * scale;
    ctx.fillStyle = isPrime ? 'rgba(251, 191, 36, 0.08)' : 'rgba(56, 189, 248, 0.08)';
    ctx.fillRect(sealX, sealY, 240 * scale, 60 * scale);
    ctx.strokeStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.lineWidth = 1 * scale;
    ctx.strokeRect(sealX, sealY, 240 * scale, 60 * scale);

    ctx.fillStyle = isPrime ? '#fbbf24' : '#38bdf8';
    ctx.font = `bold ${10 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('★ AURAMEME VERIFIED RECEIPT', sealX + 16 * scale, (sealY / scale + 24) * scale);

    ctx.fillStyle = '#cac4d0';
    ctx.font = `500 ${9.5 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('Giao dịch hợp lệ trên Sandbox Gateway', sealX + 16 * scale, (sealY / scale + 44) * scale);

    // 7. Security Notice & Footer
    const footerY = 560 * scale;
    ctx.fillStyle = '#14151f';
    ctx.fillRect(48 * scale, footerY, (800 - 96) * scale, 60 * scale);
    ctx.strokeStyle = '#292932';
    ctx.strokeRect(48 * scale, footerY, (800 - 96) * scale, 60 * scale);

    ctx.fillStyle = '#fde047';
    ctx.font = `bold ${10 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText('LƯU Ý NGHIỆM THU / SANDBOX POLICY:', 64 * scale, (footerY / scale + 24) * scale);

    ctx.fillStyle = '#948f9a';
    ctx.font = `500 ${9.5 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText(
      'Đây là biên lai của hệ thống thanh toán thử nghiệm / sandbox. Không có giao dịch tiền thật nào phát sinh.',
      64 * scale,
      (footerY / scale + 42) * scale
    );

    // Bottom brand mark
    ctx.fillStyle = '#49454f';
    ctx.font = `500 ${9 * scale}px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
    ctx.fillText(
      `© ${new Date().getFullYear()} AuraMeme. All rights reserved. Generated automatically for Order ID ${orderCode}`,
      48 * scale,
      650 * scale
    );

    // Generate jsPDF document and add high-res raster image
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });

    const imgData = canvas.toDataURL('image/png');
    pdf.addImage(imgData, 'PNG', 0, 0, 210, 297, undefined, 'FAST');
    pdf.save(`aurameme-receipt-${orderCode}.pdf`);
    return true;
  }

  // Fallback if canvas is unavailable: Generate standard vector text PDF
  const fallbackPdf = new jsPDF();
  fallbackPdf.setFont('helvetica', 'bold');
  fallbackPdf.setFontSize(18);
  fallbackPdf.text('AURAMEME - BIEN LAI THANH TOAN HOI VIEN', 20, 25);
  fallbackPdf.setFontSize(11);
  fallbackPdf.setFont('helvetica', 'normal');
  fallbackPdf.text(`Ma don hang: ${orderCode}`, 20, 40);
  fallbackPdf.text(`Goi: ${tierTitle} (${durationDays} ngay)`, 20, 48);
  fallbackPdf.text(`So tien: ${amountVnd} (${amountUsd})`, 20, 56);
  fallbackPdf.text(`Phuong thuc: ${provider}`, 20, 64);
  fallbackPdf.text(`Trang thai: DA KICH HOAT (ACTIVE)`, 20, 72);
  fallbackPdf.text(`Ngay gio: ${dateFormatted}`, 20, 80);
  fallbackPdf.text(`Ghi chu: Day la bien lai cua he thong thanh toan thu nghiem / sandbox.`, 20, 95);
  fallbackPdf.save(`aurameme-receipt-${orderCode}.pdf`);
  return true;
}
