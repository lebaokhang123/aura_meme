import {test} from 'node:test';
import assert from 'node:assert/strict';
import {relativeTime} from '../src/relative-time.js';

test('relativeTime: edge cases return Just now / Vua xong safely', () => {
  assert.equal(relativeTime(null, 'vi'), 'Vừa xong');
  assert.equal(relativeTime(null, 'en'), 'Just now');
  assert.equal(relativeTime(undefined, 'vi'), 'Vừa xong');
  assert.equal(relativeTime(undefined, 'en'), 'Just now');
  assert.equal(relativeTime('', 'vi'), 'Vừa xong');
  assert.equal(relativeTime('', 'en'), 'Just now');
  assert.equal(relativeTime('invalid-date', 'vi'), 'Vừa xong');
  assert.equal(relativeTime('invalid-date', 'en'), 'Just now');
  assert.equal(relativeTime(NaN, 'vi'), 'Vừa xong');
  assert.equal(relativeTime(NaN, 'en'), 'Just now');
  assert.equal(relativeTime(Date.now() + 60000, 'vi'), 'Vừa xong');
  assert.equal(relativeTime(Date.now() + 60000, 'en'), 'Just now');
  assert.equal(relativeTime(Date.now(), 'vi'), 'Vừa xong');
  assert.equal(relativeTime(Date.now(), 'en'), 'Just now');
});

test('relativeTime: seconds scaling', () => {
  const fiveSecAgo = Date.now() - 5000;
  assert.equal(relativeTime(fiveSecAgo, 'vi'), '5 giây trước');
  assert.equal(relativeTime(fiveSecAgo, 'en'), '5 seconds ago');
});

test('relativeTime: minutes scaling', () => {
  const fortyMinAgo = Date.now() - 40 * 60 * 1000;
  assert.equal(relativeTime(fortyMinAgo, 'vi'), '40 phút trước');
  assert.equal(relativeTime(fortyMinAgo, 'en'), '40 minutes ago');
});

test('relativeTime: hours scaling', () => {
  const sixHoursAgo = Date.now() - 6 * 3600 * 1000;
  assert.equal(relativeTime(sixHoursAgo, 'vi'), '6 giờ trước');
  assert.equal(relativeTime(sixHoursAgo, 'en'), '6 hours ago');
});

test('relativeTime: days scaling', () => {
  const tenDaysAgo = Date.now() - 10 * 86400 * 1000;
  assert.equal(relativeTime(tenDaysAgo, 'vi'), '10 ngày trước');
  assert.equal(relativeTime(tenDaysAgo, 'en'), '10 days ago');
});

test('relativeTime: months scaling', () => {
  const fourMonthsAgo = Date.now() - 4 * 30 * 86400 * 1000;
  assert.equal(relativeTime(fourMonthsAgo, 'vi'), '4 tháng trước');
  assert.equal(relativeTime(fourMonthsAgo, 'en'), '4 months ago');
});

test('relativeTime: years scaling', () => {
  const tenYearsAgo = Date.now() - 10 * 365 * 86400 * 1000;
  assert.equal(relativeTime(tenYearsAgo, 'vi'), '10 năm trước');
  assert.equal(relativeTime(tenYearsAgo, 'en'), '10 years ago');
});

test('relativeTime: accepts ISO string timestamps', () => {
  const twoHoursAgoISO = new Date(Date.now() - 2 * 3600 * 1000).toISOString();
  assert.equal(relativeTime(twoHoursAgoISO, 'vi'), '2 giờ trước');
  assert.equal(relativeTime(twoHoursAgoISO, 'en'), '2 hours ago');
});
