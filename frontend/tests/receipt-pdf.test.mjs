import test from 'node:test';
import assert from 'node:assert/strict';
import { formatReceiptDate } from '../src/receipt-pdf.js';

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
