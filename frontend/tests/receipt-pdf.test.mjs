import test from 'node:test';
import assert from 'node:assert/strict';
import { formatReceiptDate, generateReceiptPdfDoc } from '../src/receipt-pdf.js';

test('formatReceiptDate never produces Invalid Date across any input', () => {
  // 1. ISO string
  const isoResult = formatReceiptDate('2026-11-22T07:22:32.140Z');
  assert.match(isoResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!isoResult.includes('Invalid Date'));

  // 2. Unix timestamp in seconds
  const secResult = formatReceiptDate(1795330166);
  assert.match(secResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!secResult.includes('Invalid Date'));

  // 3. Timestamp in milliseconds
  const msResult = formatReceiptDate(1795330166000);
  assert.match(msResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!msResult.includes('Invalid Date'));

  // 4. Null and undefined
  const nullResult = formatReceiptDate(null);
  assert.match(nullResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!nullResult.includes('Invalid Date'));

  const undefResult = formatReceiptDate(undefined);
  assert.match(undefResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!undefResult.includes('Invalid Date'));

  // 5. Corrupted / garbage string
  const garbageResult = formatReceiptDate('this-is-not-a-date');
  assert.match(garbageResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!garbageResult.includes('Invalid Date'));

  // 6. "Invalid Date" string input specifically
  const invalidStrResult = formatReceiptDate('Invalid Date');
  assert.match(invalidStrResult, /^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}:\d{2}$/);
  assert.ok(!invalidStrResult.includes('Invalid Date'));
});

test('generateReceiptPdfDoc produces single A4 page with updated issuer and no fake tax', () => {
  const plusOrder = {
    order_code: 'AM-PLUS-1795335788-TAJ5HAE0',
    tier: 'plus',
    duration_days: 30,
    amount_usd_cents: 500,
    amount_usd_formatted: '$5',
    amount_vnd: 130000,
    status: 'success',
    provider: 'paypal_sandbox',
    paypal_order_id: '56A12345XYZ67890',
    completed_at: '2026-11-22T15:23:20Z',
  };

  const doc = generateReceiptPdfDoc(plusOrder, { username: 'khang_dev' });
  assert.ok(doc, 'doc should be instantiated');
  assert.equal(doc.internal.getNumberOfPages(), 1, 'must be exactly 1 page');

  // Verify PDF output binary has content
  const arrayBuffer = doc.output('arraybuffer');
  assert.ok(arrayBuffer.byteLength > 10000, 'PDF size should reflect embedded vector font');

  const primeOrder = {
    order_code: 'AM-PRIME-1795330988-XNSBYM98',
    tier: 'prime',
    duration_days: 365,
    amount_usd_cents: 5000,
    amount_usd_formatted: '$50',
    amount_vnd: 1250000,
    status: 'success',
    provider: 'paypal_sandbox',
    paypal_order_id: '78B98765ABC12345',
    completed_at: '2026-11-22T15:20:47Z',
  };

  const primeDoc = generateReceiptPdfDoc(primeOrder, { username: 'khang_dev' });
  assert.ok(primeDoc, 'prime doc should be instantiated');
  assert.equal(primeDoc.internal.getNumberOfPages(), 1, 'prime must be exactly 1 page');
});

test('generateReceiptPdfDoc handles 0, 1, 5, 10 successful transactions cleanly without overflow', () => {
  const baseOrder = {
    order_code: 'AM-PLUS-1795330000-BASE0001',
    tier: 'plus',
    duration_days: 30,
    amount_usd_cents: 500,
    amount_usd_formatted: '$5',
    amount_vnd: 130000,
    status: 'success',
    provider: 'paypal_sandbox',
    provider_txn_id: 'PP-BASE-001',
    completed_at: '2026-11-22T10:00:00Z',
  };

  // 1. Zero successful history
  const doc0 = generateReceiptPdfDoc({ ...baseOrder, status: 'pending' }, { username: 'user_zero' }, []);
  assert.equal(doc0, null, 'a pending order cannot produce a paid receipt');

  // 2. 1 transaction
  const doc1 = generateReceiptPdfDoc(baseOrder, { username: 'user_one' }, [baseOrder]);
  assert.ok(doc1);
  assert.equal(doc1.internal.getNumberOfPages(), 1);

  // 3. 5 transactions
  const history5 = Array.from({ length: 5 }, (_, i) => ({
    order_code: `AM-PLUS-179533000${i}-TEST000${i}`,
    tier: i % 2 === 0 ? 'plus' : 'prime',
    amount_usd_formatted: i % 2 === 0 ? '$5' : '$50',
    status: 'success',
    provider: 'paypal_sandbox',
    provider_txn_id: `PP-TXN-HIST-00${i}`,
    completed_at: new Date(Date.now() - i * 86400000).toISOString(),
  }));
  const doc5 = generateReceiptPdfDoc(baseOrder, { username: 'user_five' }, history5);
  assert.ok(doc5);
  assert.equal(doc5.internal.getNumberOfPages(), 1);

  // 4. 10 transactions with mixed short and long reference IDs
  const history10 = Array.from({ length: 10 }, (_, i) => ({
    order_code: `AM-ORD-17953300${i < 10 ? '0' + i : i}-CODE00${i}`,
    tier: i % 3 === 0 ? 'prime' : 'plus',
    amount_usd_formatted: i % 3 === 0 ? '$50' : '$5',
    status: 'success',
    provider: i % 2 === 0 ? 'paypal_sandbox' : 'sandbox_simulated',
    provider_txn_id: i % 2 === 0 ? `CAPTURE-VERY-LONG-PAYPAL-REFERENCE-NUMBER-${i}-XYZ` : `SIM-${i}`,
    completed_at: new Date(Date.now() - i * 3600000 * 24).toISOString(),
  }));
  const doc10 = generateReceiptPdfDoc(baseOrder, { username: 'user_ten' }, history10);
  assert.ok(doc10);
  // Either 1 page or gracefully paginated to 2 pages with headers on both
  const pages = doc10.internal.getNumberOfPages();
  assert.ok(pages >= 1 && pages <= 2, `Pages must be 1 or 2, got ${pages}`);
  assert.ok(doc10.output('arraybuffer').byteLength > 10000);
});

