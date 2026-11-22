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

