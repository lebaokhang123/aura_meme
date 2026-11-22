import { jsPDF } from 'jspdf';

/**
 * Safely parses any date representation (ISO string, unix seconds, milliseconds, or null)
 * and formats it as DD/MM/YYYY HH:mm:ss.
 * Under no circumstances does this ever return "Invalid Date".
 */
export function formatReceiptDate(val) {
  if (!val) return formatDateObj(new Date());
  let d;
  if (typeof val === 'number') {
    d = new Date(val < 1e11 ? val * 1000 : val);
  } else if (typeof val === 'string') {
    const num = Number(val);
    if (!isNaN(num) && num > 0) {
      d = new Date(num < 1e11 ? num * 1000 : num);
    } else {
      d = new Date(val);
    }
  } else if (val instanceof Date) {
    d = val;
  }
  if (!d || isNaN(d.getTime())) {
    d = new Date();
  }
  return formatDateObj(d);
}

function formatDateObj(d) {
  const pad = (n) => String(n).padStart(2, '0');
  const day = pad(d.getDate());
  const month = pad(d.getMonth() + 1);
  const year = d.getFullYear();
  const hours = pad(d.getHours());
  const minutes = pad(d.getMinutes());
  const seconds = pad(d.getSeconds());
  return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
}

/**
 * Downloads an authentic, clean, SaaS-style A4 PDF receipt for AuraMeme memberships.
 * Inspired by OpenAI / Stripe modern invoices:
 * - Pure white A4 portrait (210mm x 297mm)
 * - 100% direct vector & text primitives via jsPDF (fully selectable/copyable text)
 * - No raster canvas screenshot, no poster borders, no artificial stamps
 * - Clean metadata, itemized table, totals, payment history, and sandbox notice
 *
 * @param {Object} order - Order details from API or receipt state
 * @param {Object} [user] - Active authenticated user details
 */
export function downloadReceiptPdf(order, user) {
  if (!order) return false;

  const orderCode = order.order_code || order.orderCode || 'AM-ORDER';
  const tier = (order.tier || order.tierName || 'plus').toLowerCase().replace('aura ', '');
  const isPrime = tier === 'prime';
  const tierTitle = isPrime ? 'Aura Prime' : 'Aura Plus';
  const durationDays = order.duration_days || order.durationDays || (isPrime ? 365 : 30);
  const boostMultiplier = order.boost_multiplier || (isPrime ? 3 : 2);

  // Exact USD and VND amounts
  const amountUsdValue = isPrime ? '50.00' : '5.00';
  const amountUsdFormatted = `${amountUsdValue} USD`;
  const amountVndFormatted = isPrime ? '1.250.000 VNĐ' : '130.000 VNĐ';

  const provider = order.provider === 'paypal_sandbox' ? 'PayPal Sandbox v2' : 'Thanh toan Thu nghiem';
  const txnId = order.paypal_order_id || order.provider_txn_id || orderCode;
  const username = user?.username || user?.displayName || 'khang_dev';

  const rawDate = order.completed_at || order.activatedAt || order.created_at;
  const dateFormatted = formatReceiptDate(rawDate);
  const dateOnly = dateFormatted.split(' ')[0];

  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  // 1. Header Top
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(22);
  doc.setTextColor(17, 24, 39);
  doc.text('AURAMEME', 20, 26);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(107, 114, 128);
  doc.text('Cyberpunk Cultivation Platform', 20, 31);
  doc.text('https://aurameme.me · support@aurameme.me', 20, 35.5);

  // Right Header - Receipt Title
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(22);
  doc.setTextColor(17, 24, 39);
  doc.text('RECEIPT', 190, 26, { align: 'right' });

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(107, 114, 128);
  doc.text('BIEN LAI THANH TOAN', 190, 31, { align: 'right' });

  // Paid Status Badge
  doc.setFillColor(236, 253, 245); // emerald-50
  doc.setDrawColor(16, 185, 129); // emerald-500
  doc.setLineWidth(0.3);
  doc.roundedRect(152, 34.5, 38, 6.5, 1.5, 1.5, 'FD');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(4, 120, 87); // emerald-700
  doc.text('PAID / DA THANH TOAN', 171, 39, { align: 'center' });

  // Top Divider Line
  doc.setDrawColor(229, 231, 235); // gray-200
  doc.setLineWidth(0.3);
  doc.line(20, 44, 190, 44);

  // 2. Metadata Columns (Issuer on left, Order details on right)
  // Left: Issuer info
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text('ISSUED BY / DON VI PHAT HANH', 20, 51);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9.5);
  doc.setTextColor(31, 41, 55);
  doc.text('AuraMeme Global Inc.', 20, 56.5);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(75, 85, 99);
  doc.text('Cyberpunk Cultivation Meme Community', 20, 61);
  doc.text('Sandbox Gateway Operations', 20, 65.5);
  doc.text('support@aurameme.me', 20, 70);

  // Right: Transaction & Customer info
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text('TRANSACTION DETAILS / THONG TIN DON HANG', 105, 51);

  const metaFields = [
    ['Order Code / Ma don:', orderCode],
    ['Date / Ngay thanh toan:', dateFormatted],
    ['Payment Method / Cong:', provider],
    ['Customer / Khach hang:', '@' + username],
    ['Transaction Ref / Ma GD:', txnId.length > 28 ? txnId.substring(0, 28) + '...' : txnId],
  ];

  metaFields.forEach(([lbl, val], idx) => {
    const curY = 56.5 + idx * 4.5;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(107, 114, 128);
    doc.text(lbl, 105, curY);

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8.5);
    doc.setTextColor(17, 24, 39);
    doc.text(val, 190, curY, { align: 'right' });
  });

  // 3. Highlight Payment Line (Clean SaaS summary block)
  doc.setFillColor(249, 250, 251);
  doc.setDrawColor(229, 231, 235);
  doc.roundedRect(20, 82, 170, 14, 2, 2, 'FD');

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(13);
  doc.setTextColor(17, 24, 39);
  doc.text(`${amountUsdFormatted} paid on ${dateOnly}`, 25, 90.5);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(107, 114, 128);
  doc.text(`(Ty gia tham chieu: ~${amountVndFormatted})`, 185, 90.5, { align: 'right' });

  // 4. Itemized Table
  const tableY = 103;
  doc.setFillColor(243, 244, 246);
  doc.rect(20, tableY, 170, 7, 'F');
  doc.setDrawColor(209, 213, 219);
  doc.line(20, tableY, 190, tableY);
  doc.line(20, tableY + 7, 190, tableY + 7);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(75, 85, 99);
  doc.text('DESCRIPTION / DICH VU', 23, tableY + 4.8);
  doc.text('DURATION', 105, tableY + 4.8);
  doc.text('QTY', 130, tableY + 4.8, { align: 'center' });
  doc.text('UNIT PRICE', 155, tableY + 4.8, { align: 'right' });
  doc.text('AMOUNT', 187, tableY + 4.8, { align: 'right' });

  // Table Row Item
  const rowY = tableY + 7;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9.5);
  doc.setTextColor(17, 24, 39);
  doc.text(`${tierTitle} Membership Subscription`, 23, rowY + 5.5);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(107, 114, 128);
  const tierBenefit = isPrime
    ? `EXP Multiplier x${boostMultiplier} · Gold Diamond Avatar Glow & Identity`
    : `EXP Multiplier x${boostMultiplier} · Cyan Badge Avatar Ring & Identity`;
  doc.text(tierBenefit, 23, rowY + 9.5);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(55, 65, 81);
  doc.text(`${durationDays} days (${durationDays} ngay)`, 105, rowY + 6.5);
  doc.text('1', 130, rowY + 6.5, { align: 'center' });
  doc.text(amountUsdFormatted, 155, rowY + 6.5, { align: 'right' });

  doc.setFont('helvetica', 'bold');
  doc.text(amountUsdFormatted, 187, rowY + 6.5, { align: 'right' });

  doc.setDrawColor(229, 231, 235);
  doc.line(20, rowY + 12, 190, rowY + 12);

  // 5. Totals Section (Right Aligned)
  const totalStartY = rowY + 16;
  const totals = [
    ['Subtotal / Tam tinh:', amountUsdFormatted],
    ['Tax / Thue (0%):', '0.00 USD'],
    ['Total / Tong thanh toan:', amountUsdFormatted],
    ['Amount Paid / Da thanh toan:', amountUsdFormatted],
  ];

  totals.forEach(([lbl, val], idx) => {
    const curY = totalStartY + idx * 5;
    const isFinal = idx >= 2;
    doc.setFont('helvetica', isFinal ? 'bold' : 'normal');
    doc.setFontSize(isFinal ? 9.5 : 8.5);
    doc.setTextColor(
      isFinal ? (idx === 3 ? 4 : 17) : 107,
      isFinal ? (idx === 3 ? 120 : 24) : 114,
      isFinal ? (idx === 3 ? 87 : 39) : 128
    );
    doc.text(lbl, 115, curY);
    doc.text(val, 187, curY, { align: 'right' });
  });

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(156, 163, 175);
  doc.text(`Ref VND / Tham chieu: ~${amountVndFormatted}`, 187, totalStartY + 23, { align: 'right' });

  // 6. Payment History Block
  const histY = totalStartY + 31;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8.5);
  doc.setTextColor(31, 41, 55);
  doc.text('PAYMENT HISTORY / LICH SU THANH TOAN', 20, histY);

  doc.setDrawColor(209, 213, 219);
  doc.line(20, histY + 2, 190, histY + 2);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(107, 114, 128);
  doc.text('PAYMENT METHOD', 23, histY + 6.5);
  doc.text('DATE', 85, histY + 6.5);
  doc.text('AMOUNT PAID', 135, histY + 6.5, { align: 'right' });
  doc.text('STATUS / REFERENCE', 187, histY + 6.5, { align: 'right' });

  doc.setDrawColor(243, 244, 246);
  doc.line(20, histY + 8.5, 190, histY + 8.5);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(55, 65, 81);
  doc.text(provider, 23, histY + 13);
  doc.text(dateFormatted, 85, histY + 13);
  doc.text(amountUsdFormatted, 135, histY + 13, { align: 'right' });
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(4, 120, 87);
  doc.text(`SUCCESS / ${orderCode.substring(0, 16)}...`, 187, histY + 13, { align: 'right' });

  doc.setDrawColor(229, 231, 235);
  doc.line(20, histY + 16, 190, histY + 16);

  // 7. Footer Note & Page Number
  doc.setDrawColor(229, 231, 235);
  doc.setLineWidth(0.2);
  doc.line(20, 272, 190, 272);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text('Bien lai dien tu tao tu dong tu Cong thanh toan Thu nghiem AuraMeme PayPal Sandbox.', 20, 277);
  doc.text('Moi truong thu nghiem sandbox phuc vu nghiem thu - Khong phat sinh chi phi tien that.', 20, 281);
  doc.text('Page 1 of 1', 190, 277, { align: 'right' });

  // Save PDF file
  doc.save(`aurameme-receipt-${orderCode}.pdf`);
  return true;
}
