import test from 'node:test';
import assert from 'node:assert/strict';
import { startPresenceHeartbeat, HEARTBEAT_INTERVAL_MS } from '../src/presence.js';
import { adminPresence } from '../src/admin-api.js';

function createFakeAuth(initial = { status: 'guest', user: null }) {
  let state = initial;
  const listeners = new Set();
  const calls = [];
  return {
    calls,
    snapshot: () => state,
    subscribe: (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    setState(next) {
      state = next;
      for (const fn of listeners) fn();
    },
    async read(path, opts) {
      calls.push({ path, opts });
      if (this.nextError) {
        const err = this.nextError;
        this.nextError = null;
        throw err;
      }
      return { status: 'ok', interval_seconds: 30, window_seconds: 90 };
    },
  };
}

function createFakeDoc(initialVisibility = 'visible') {
  const listeners = new Map();
  return {
    visibilityState: initialVisibility,
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(fn);
    },
    removeEventListener(type, fn) {
      listeners.get(type)?.delete(fn);
    },
    setVisibility(val) {
      this.visibilityState = val;
      for (const fn of listeners.get('visibilitychange') || []) fn();
    },
  };
}

test('startPresenceHeartbeat avoids duplicate timers, pauses when hidden, and cleans up', async () => {
  const auth = createFakeAuth();
  const doc = createFakeDoc('visible');
  const timers = new Map();
  let nextId = 1;
  const stop = startPresenceHeartbeat({
    authClient: auth,
    documentObj: doc,
    setIntervalFn: (fn, ms) => {
      assert.equal(ms, HEARTBEAT_INTERVAL_MS);
      const id = nextId++;
      timers.set(id, fn);
      return id;
    },
    clearIntervalFn: (id) => {
      timers.delete(id);
    },
  });

  // Initial heartbeat + single active timer
  await Promise.resolve();
  assert.equal(auth.calls.length, 1);
  assert.equal(auth.calls[0].path, '/presence/heartbeat');
  assert.equal(timers.size, 1);

  // Tick interval once
  const [tickFn] = timers.values();
  await tickFn();
  assert.equal(auth.calls.length, 2);

  // Hidden tab pauses timer; becoming visible resumes and does not duplicate timers
  doc.setVisibility('hidden');
  assert.equal(timers.size, 0);
  doc.setVisibility('visible');
  await Promise.resolve();
  assert.equal(timers.size, 1);
  assert.equal(auth.calls.length, 3);

  // Auth transition triggers heartbeat
  auth.setState({ status: 'authenticated', user: { id: 'u-1' } });
  await Promise.resolve();
  assert.equal(auth.calls.length, 4);

  // Cleanup clears timer
  stop();
  assert.equal(timers.size, 0);
});

test('startPresenceHeartbeat respects HTTP 429 Retry-After without retry storm', async () => {
  const auth = createFakeAuth();
  const doc = createFakeDoc('visible');
  let now = 10000;
  let tickFn = null;
  auth.nextError = Object.assign(new Error('RATE_LIMITED'), { status: 429, retryAfter: 45 });

  const stop = startPresenceHeartbeat({
    authClient: auth,
    documentObj: doc,
    nowFn: () => now,
    setIntervalFn: (fn) => {
      tickFn = fn;
      return 1;
    },
    clearIntervalFn: () => {},
  });

  await Promise.resolve();
  assert.equal(auth.calls.length, 1);

  // Within 45s cooldown -> skipped
  now += 30000;
  await tickFn();
  assert.equal(auth.calls.length, 1);

  // After 45s cooldown -> allowed again
  now += 20000;
  await tickFn();
  assert.equal(auth.calls.length, 2);
  stop();
});

test('adminPresence validates aggregate response contract strictly', () => {
  const valid = adminPresence({
    active_total: 5,
    active_users: 3,
    active_guests: 2,
    window_seconds: 90,
    generated_at: '2026-11-27T05:00:00Z',
  });
  assert.equal(valid.active_total, 5);
  assert.equal(valid.window_seconds, 90);

  assert.throws(() =>
    adminPresence({
      active_total: 6,
      active_users: 3,
      active_guests: 2,
      window_seconds: 90,
      generated_at: '2026-11-27T05:00:00Z',
    })
  );
  assert.throws(() =>
    adminPresence({
      active_total: -1,
      active_users: -1,
      active_guests: 0,
      window_seconds: 90,
      generated_at: '2026-11-27T05:00:00Z',
    })
  );
});
