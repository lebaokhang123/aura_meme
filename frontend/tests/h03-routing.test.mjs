import test from 'node:test';
import assert from 'node:assert/strict';

test('runtime route allowlist rejects unknown paths and accepts valid routes', async () => {
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
  const { isKnownRoute } = await import('../src/runtime.js');

  for (const valid of [
    '/',
    '/explore',
    '/about',
    '/contact',
    '/rank',
    '/vault',
    '/login',
    '/register',
    '/forgot-password',
    '/reset-password',
    '/verify-email',
    '/premium',
    '/premium/checkout',
    '/premium/history',
    '/admin',
    '/admin/contacts',
    '/profile',
    '/profile/khang_dev',
    '/u/sim_user_001',
  ]) {
    assert.equal(isKnownRoute(valid), true, `Expected ${valid} to be known`);
  }

  for (const invalid of [
    '/khong-ton-tai',
    '/admin/secret',
    '/u',
    '/profile/a/b',
    '/profile/Invalid!User',
    '/explore/extra',
  ]) {
    assert.equal(isKnownRoute(invalid), false, `Expected ${invalid} to be unknown (404)`);
  }
});
