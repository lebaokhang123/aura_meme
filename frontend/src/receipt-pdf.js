import { jsPDF } from 'jspdf';
import { registerReceiptFonts } from './fonts/roboto-fonts.js';

/**
 * Safely parses any date representation (ISO string, unix seconds, milliseconds, or Date)
 * and formats it as DD/MM/YYYY HH:mm:ss.
 * Under no circumstances does this ever return "Invalid Date".
 *
 * @param {*} val - Date value to format
 * @returns {string} Formatted date string DD/MM/YYYY HH:mm:ss
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
 * Generates an authentic, clean, SaaS-style A4 jsPDF instance for AuraMeme memberships.
 * Pure vector/text primitives via jsPDF with embedded Unicode Roboto font:
 * - 100% searchable, selectable, copyable text with complete Vietnamese diacritics.
 * - Single A4 page (210mm x 297mm), clean white background, balanced vertical rhythm.
 * - Updated official issuer info: AuraSpark Global Inc. & AuraMeme Community.
 * - Accurate USD pricing ($5.00 / $50.00) and reference VND (~130.000 VNĐ / ~1.250.000 VNĐ).
 * - Separated columns, full order codes without clipping, reusable payment history table.
 * - No fake tax rows, no fake seals/stamps; transparent sandbox receipt notice.
 *
 * @param {Object} order - Order details from API or checkout state
 * @param {Object} [user] - Active authenticated user details
 * @returns {jsPDF|null} Configured jsPDF instance
 */
export function generateReceiptPdfDoc(order, user, recentSuccessfulOrders = null) {
  if (!order) return null;

  const orderCode = order.order_code || order.orderCode || 'AM-ORDER';
  const tier = (order.tier || order.tierName || 'plus').toLowerCase().replace('aura ', '');
  const isPrime = tier === 'prime';
  const tierTitle = isPrime ? 'Aura Prime' : 'Aura Plus';
  const durationDays = order.duration_days || order.durationDays || (isPrime ? 365 : 30);

  // Exact USD and reference VND amounts
  const amountUsdValue = isPrime ? '50.00' : '5.00';
  const amountUsdFormatted = `${amountUsdValue} USD`;
  const amountVndFormatted = isPrime ? '1.250.000 VNĐ' : '130.000 VNĐ';

  // Transaction reference (distinguish PayPal Order ID/Capture ID from AuraMeme order code)
  const txnRef = order.paypal_order_id || order.provider_txn_id || orderCode;

  // Payment provider name
  let providerName = 'Chưa xác định';
  if (order.provider === 'sandbox_simulated' || order.payment_method === 'card' || txnRef.startsWith('SIM-CARD-')) {
    providerName = 'Thẻ';
  } else if (order.provider === 'paypal_sandbox') {
    if (txnRef.startsWith('SIM-') || txnRef.startsWith('MOCK-')) {
      providerName = 'Mô phỏng';
    } else {
      providerName = 'PayPal';
    }
  } else if (order.provider === 'vnpay_sandbox') {
    providerName = 'VNPAY';
  }
  const username = user?.username || user?.displayName || 'khang_dev';

  const rawDate = order.completed_at || order.activatedAt || order.created_at;
  const dateFormatted = formatReceiptDate(rawDate);
  const dateOnly = dateFormatted.split(' ')[0];

  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  // Register embedded Roboto Unicode fonts
  registerReceiptFonts(doc);

  // Brand Accent Colors
  const accentColor = isPrime ? [245, 158, 11] : [6, 182, 212]; // Amber-500 or Cyan-500

  // 1. HEADER (Y: 20 -> 44)
  // Left: Brand Logo & Community
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(22);
  doc.setTextColor(17, 24, 39);
  doc.text('AURAMEME', 20, 26);

  doc.setFont('Roboto', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(107, 114, 128);
  doc.text('AuraMeme Community', 20, 31.5);
  doc.text('https://aurameme.com', 20, 36);

  // Right: Document Title & Status
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(18);
  doc.setTextColor(17, 24, 39);
  doc.text('BIÊN LAI THANH TOÁN', 190, 25, { align: 'right' });

  doc.setFont('Roboto', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(107, 114, 128);
  doc.text('PAYMENT RECEIPT', 190, 30, { align: 'right' });

  // Status Badge: PAID / ĐÃ THANH TOÁN
  doc.setFillColor(236, 253, 245); // emerald-50
  doc.setDrawColor(16, 185, 129); // emerald-500
  doc.setLineWidth(0.3);
  doc.roundedRect(146, 33.5, 44, 6.5, 1.5, 1.5, 'FD');
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(4, 120, 87); // emerald-700
  doc.text('PAID / ĐÃ THANH TOÁN', 168, 38, { align: 'center' });

  // Top Divider Line
  doc.setDrawColor(229, 231, 235);
  doc.setLineWidth(0.3);
  doc.line(20, 43, 190, 43);

  // 2. METADATA SECTION (Y: 48 -> 84)
  // Left Column: Đơn vị phát hành / Issued By
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text('ĐƠN VỊ PHÁT HÀNH / ISSUED BY', 20, 49.5);

  doc.setFont('Roboto', 'bold');
  doc.setFontSize(9.5);
  doc.setTextColor(31, 41, 55);
  doc.text('AuraSpark Global Inc.', 20, 56);

  doc.setFont('Roboto', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(75, 85, 99);
  doc.text('AuraMeme Community', 20, 61.5);
  doc.text('https://aurameme.com', 20, 67);
  doc.text('sammybkhang@gmail.com', 20, 72.5);

  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text('Hệ thống thử nghiệm (Sandbox Environment)', 20, 78);

  // Right Column: Thông tin giao dịch / Transaction Details
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text('THÔNG TIN GIAO DỊCH / TRANSACTION DETAILS', 105, 49.5);

  const metaRows = [
    ['Mã đơn hàng / Order Code:', orderCode],
    ['Ngày thanh toán / Date:', dateFormatted],
    ['Phương thức / Method:', providerName],
    ['Tài khoản / Customer:', '@' + username],
    ['Mã tham chiếu / Reference:', txnRef],
  ];

  metaRows.forEach(([lbl, val], idx) => {
    const curY = 56 + idx * 5.5;
    doc.setFont('Roboto', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(107, 114, 128);
    doc.text(lbl, 105, curY);

    doc.setFont('Roboto', 'bold');
    // Scale down font slightly if order code / reference is very long
    if (val.length > 28) {
      doc.setFontSize(7);
    } else if (val.length > 22) {
      doc.setFontSize(7.5);
    } else {
      doc.setFontSize(8);
    }
    doc.setTextColor(17, 24, 39);
    doc.text(val, 190, curY, { align: 'right' });
  });

  // 3. HIGHLIGHT PAYMENT SUMMARY BLOCK (Y: 88 -> 104)
  doc.setFillColor(249, 250, 251);
  doc.setDrawColor(229, 231, 235);
  doc.roundedRect(20, 88, 170, 15, 2, 2, 'FD');

  // Left accent pill bar
  doc.setFillColor(accentColor[0], accentColor[1], accentColor[2]);
  doc.roundedRect(20, 88, 3, 15, 1, 1, 'F');

  doc.setFont('Roboto', 'bold');
  doc.setFontSize(12);
  doc.setTextColor(17, 24, 39);
  doc.text(`${amountUsdFormatted} paid on ${dateOnly}`, 27, 97.5);

  doc.setFont('Roboto', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(107, 114, 128);
  doc.text(`Giá tham khảo: ${amountVndFormatted}`, 186, 97.5, { align: 'right' });

  // 4. ITEMIZED SERVICES TABLE (Y: 112 -> 142)
  const tableY = 112;

  // Header row
  doc.setFillColor(243, 244, 246);
  doc.rect(20, tableY, 170, 7.5, 'F');
  doc.setDrawColor(209, 213, 219);
  doc.line(20, tableY, 190, tableY);
  doc.line(20, tableY + 7.5, 190, tableY + 7.5);

  doc.setFont('Roboto', 'bold');
  doc.setFontSize(7.2);
  doc.setTextColor(75, 85, 99);
  doc.text('DỊCH VỤ / DESCRIPTION', 23, tableY + 5.2);
  doc.text('THỜI HẠN / DURATION', 80, tableY + 5.2);
  doc.text('SL / QTY', 120, tableY + 5.2, { align: 'center' });
  doc.text('ĐƠN GIÁ / PRICE', 153, tableY + 5.2, { align: 'right' });
  doc.text('THÀNH TIỀN / AMOUNT', 188, tableY + 5.2, { align: 'right' });

  // Data row
  const rowY = tableY + 7.5;
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(9);
  doc.setTextColor(17, 24, 39);
  doc.text(`Gói hội viên ${tierTitle}`, 23, rowY + 5.5);

  doc.setFont('Roboto', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(107, 114, 128);
  const tierBenefit = isPrime
    ? 'Hội viên 365 ngày · Dấu ấn Aura Prime hoàng kim'
    : 'Hội viên 30 ngày · Dấu ấn Aura Plus xanh ngọc';
  doc.text(`${tierTitle} Subscription · ${tierBenefit}`, 23, rowY + 10.5);

  // Duration column (well-separated, never colliding with QTY)
  doc.setFont('Roboto', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(55, 65, 81);
  doc.text(`${durationDays} ngày (${durationDays}d)`, 80, rowY + 7);

  // Qty column
  doc.text('1', 120, rowY + 7, { align: 'center' });

  // Unit Price column
  doc.text(amountUsdFormatted, 153, rowY + 7, { align: 'right' });

  // Amount column
  doc.setFont('Roboto', 'bold');
  doc.text(amountUsdFormatted, 188, rowY + 7, { align: 'right' });

  doc.setDrawColor(229, 231, 235);
  doc.line(20, rowY + 15, 190, rowY + 15);

  // 5. TOTALS SECTION (Y: 140 -> 168)
  const totalStartY = rowY + 20;
  const totals = [
    ['Tạm tính / Subtotal:', amountUsdFormatted, false],
    ['Tổng thanh toán / Total Amount:', amountUsdFormatted, true],
    ['Đã thanh toán / Amount Paid:', amountUsdFormatted, true],
  ];

  totals.forEach(([lbl, val, isFinal], idx) => {
    const curY = totalStartY + idx * 5.5;
    doc.setFont('Roboto', isFinal ? 'bold' : 'normal');
    doc.setFontSize(isFinal ? 9 : 8);
    if (idx === 2) {
      doc.setTextColor(4, 120, 87); // Emerald green for paid amount
    } else if (isFinal) {
      doc.setTextColor(17, 24, 39);
    } else {
      doc.setTextColor(107, 114, 128);
    }
    doc.text(lbl, 112, curY);
    doc.text(val, 187, curY, { align: 'right' });
  });

  // Reference VND Note below total
  doc.setFont('Roboto', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(156, 163, 175);
  doc.text(`Giá tham khảo: ~${amountVndFormatted}`, 187, totalStartY + 19, { align: 'right' });

  // 6. PAYMENT HISTORY SECTION (up to 10 recent successful orders)
  const histY = totalStartY + 27;
  doc.setFont('Roboto', 'bold');
  doc.setFontSize(8.5);
  doc.setTextColor(31, 41, 55);
  doc.text('LỊCH SỬ THANH TOÁN / PAYMENT HISTORY', 20, histY);

  doc.setDrawColor(209, 213, 219);
  doc.line(20, histY + 2.5, 190, histY + 2.5);

  const drawHistHeader = (startY) => {
    doc.setFillColor(249, 250, 251);
    doc.rect(20, startY + 3, 170, 6, 'F');
    doc.setFont('Roboto', 'bold');
    doc.setFontSize(6.8);
    doc.setTextColor(107, 114, 128);
    doc.text('PHƯƠNG THỨC / METHOD', 23, startY + 7.2);
    doc.text('NGÀY / DATE', 58, startY + 7.2);
    doc.text('SỐ TIỀN / AMOUNT', 113, startY + 7.2, { align: 'right' });
    doc.text('TRẠNG THÁI / STATUS', 132, startY + 7.2, { align: 'center' });
    doc.text('MÃ THAM CHIẾU / REF', 188, startY + 7.2, { align: 'right' });
    doc.setDrawColor(243, 244, 246);
    doc.line(20, startY + 9, 190, startY + 9);
  };

  drawHistHeader(histY);

  // Normalize list of recent successful orders
  let historyList = [];
  if (Array.isArray(recentSuccessfulOrders) && recentSuccessfulOrders.length > 0) {
    const seenCodes = new Set();
    for (const item of recentSuccessfulOrders) {
      if (!item) continue;
      const st = String(item.status || '').toLowerCase();
      if (st !== 'success' && st !== 'completed') continue;
      const code = item.order_code || item.orderCode || item.id;
      if (code && !seenCodes.has(code)) {
        seenCodes.add(code);
        historyList.push(item);
      }
    }
  }

  // If no external history list was passed, include current order if successful
  if (historyList.length === 0 && (order.status === 'success' || order.status === 'completed')) {
    historyList.push(order);
  }

  // Cap at maximum 10 items
  historyList = historyList.slice(0, 10);

  let curY = histY + 9;

  if (historyList.length === 0) {
    curY += 5;
    doc.setFont('Roboto', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(156, 163, 175);
    doc.text('Chưa có lịch sử giao dịch thành công nào / No completed transactions.', 23, curY);
    curY += 2;
  } else {
    for (let idx = 0; idx < historyList.length; idx++) {
      const histItem = historyList[idx];
      const hTxn = histItem.provider_txn_id || histItem.order_code || '';
      let hProvider = 'Chưa xác định';
      if (histItem.provider === 'sandbox_simulated' || histItem.payment_method === 'card' || hTxn.startsWith('SIM-CARD-')) {
        hProvider = 'Thẻ';
      } else if (histItem.provider === 'paypal_sandbox') {
        if (hTxn.startsWith('SIM-') || hTxn.startsWith('MOCK-')) {
          hProvider = 'Mô phỏng';
        } else {
          hProvider = 'PayPal';
        }
      } else if (histItem.provider === 'vnpay_sandbox') {
        hProvider = 'VNPAY';
      }
      const hDate = formatReceiptDate(histItem.completed_at || histItem.created_at);
      const isHistPrime = (histItem.tier || '').toLowerCase() === 'prime';
      const hAmount = histItem.amount_usd_formatted || (isHistPrime ? '$50' : '$5');
      const hRef = histItem.provider_txn_id || histItem.order_code || '—';

      // Determine row height needed
      doc.setFont('Roboto', 'normal');
      doc.setFontSize(6.5);
      const hRefWidth = doc.getTextWidth(hRef);
      const isMultiLine = hRefWidth > 37;
      const rowH = isMultiLine ? 8.5 : 5.8;

      // Page overflow check (footer is at 268)
      if (curY + rowH > 260) {
        doc.addPage();
        curY = 20;
        doc.setFont('Roboto', 'bold');
        doc.setFontSize(8.5);
        doc.setTextColor(31, 41, 55);
        doc.text('LỊCH SỬ THANH TOÁN / PAYMENT HISTORY (Tiếp theo / Continued)', 20, curY);
        doc.setDrawColor(209, 213, 219);
        doc.line(20, curY + 2.5, 190, curY + 2.5);
        drawHistHeader(curY);
        curY += 9;
      }

      const textY = curY + 4.2;
      doc.setFont('Roboto', 'normal');
      doc.setFontSize(7.5);
      doc.setTextColor(55, 65, 81);
      doc.text(hProvider, 23, textY);
      doc.text(hDate, 58, textY);
      doc.text(hAmount, 113, textY, { align: 'right' });

      doc.setFont('Roboto', 'bold');
      doc.setTextColor(4, 120, 87);
      doc.text('HOÀN TẤT', 132, textY, { align: 'center' });

      doc.setFont('Roboto', 'normal');
      doc.setTextColor(75, 85, 99);
      if (isMultiLine) {
        doc.setFontSize(6.0);
        doc.text(hRef, 188, textY + 3.2, { align: 'right' });
        doc.setDrawColor(229, 231, 235);
        doc.line(20, textY + 5.2, 190, textY + 5.2);
        curY += 8.5;
      } else {
        doc.setFontSize(6.5);
        doc.text(hRef, 188, textY, { align: 'right' });
        doc.setDrawColor(229, 231, 235);
        doc.line(20, textY + 3.2, 190, textY + 3.2);
        curY += 5.8;
      }
    }
  }

  // 7. FOOTER SECTION ON ALL PAGES (Y: 268 -> 282)
  const totalPages = doc.internal.getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    doc.setDrawColor(229, 231, 235);
    doc.setLineWidth(0.2);
    doc.line(20, 268, 190, 268);

    doc.setFont('Roboto', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(156, 163, 175);
    doc.text('Biên lai giao dịch thử nghiệm — Không phát sinh thanh toán tiền thật.', 20, 273.5);
    doc.text('Sandbox transaction receipt — For development and verification purposes only.', 20, 277.5);
    doc.text(`Trang ${p} / ${totalPages}  (Page ${p} of ${totalPages})`, 190, 273.5, { align: 'right' });
  }

  return doc;
}

/**
 * Downloads the generated PDF receipt in browser environment.
 *
 * @param {Object} order - Order details
 * @param {Object} [user] - User details
 * @param {Array} [recentSuccessfulOrders] - Optional list of recent completed orders
 * @returns {boolean} True if saved
 */
export function downloadReceiptPdf(order, user, recentSuccessfulOrders = null) {
  const doc = generateReceiptPdfDoc(order, user, recentSuccessfulOrders);
  if (!doc) return false;
  const orderCode = order.order_code || order.orderCode || 'AM-ORDER';
  doc.save(`aurameme-receipt-${orderCode}.pdf`);
  return true;
}
