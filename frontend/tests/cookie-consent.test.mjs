import test from 'node:test';
import assert from 'node:assert/strict';
import {
  COOKIE_CONSENT_KEY,
  COOKIE_CONSENT_VERSION,
  readCookieConsent,
  saveCookieConsent,
  hasOptionalConsent,
} from '../src/cookie-consent.js';

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

test('cookie consent persists versioned timestamp, essential always true, and rejects invalid/outdated records', () => {
  const store = memoryStorage();
  assert.equal(readCookieConsent(store), null);
  assert.equal(hasOptionalConsent(store), false);

  const rejected = saveCookieConsent({ optional: false }, store, new Date('2026-11-22T12:00:00Z'));
  assert.deepEqual(rejected, {
    version: COOKIE_CONSENT_VERSION,
    essential: true,
    optional: false,
    updatedAt: '2026-11-22T12:00:00.000Z',
  });
  assert.deepEqual(readCookieConsent(store), rejected);
  assert.equal(hasOptionalConsent(store), false);

  const accepted = saveCookieConsent({ optional: true }, store, new Date('2026-11-22T12:05:00Z'));
  assert.equal(accepted.essential, true);
  assert.equal(accepted.optional, true);
  assert.equal(hasOptionalConsent(store), true);

  // Corrupted or outdated schema is safely ignored
  store.setItem(COOKIE_CONSENT_KEY, JSON.stringify({ version: 99, essential: true, optional: true, updatedAt: '2026-11-22T12:00:00Z' }));
  assert.equal(readCookieConsent(store), null);
  store.setItem(COOKIE_CONSENT_KEY, 'not-json');
  assert.equal(readCookieConsent(store), null);

  // Blocked storage never throws
  const blocked = {
    getItem() { throw new Error('blocked'); },
    setItem() { throw new Error('blocked'); },
  };
  assert.equal(readCookieConsent(blocked), null);
  assert.equal(saveCookieConsent({ optional: false }, blocked).essential, true);
});
