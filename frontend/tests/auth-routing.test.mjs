import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveAuthRedirect, isProtectedPath } from '../src/auth-routing.js';

test('redirects authenticated user away from /login and /register using safeReturnUrl', () => {
  assert.equal(resolveAuthRedirect({ path: '/login', search: '', status: 'authenticated' }), '/');
  assert.equal(resolveAuthRedirect({ path: '/register', search: '?next=%2Fvault', status: 'authenticated' }), '/vault');
  assert.equal(resolveAuthRedirect({ path: '/login', search: '?next=https://evil.example.com', status: 'authenticated' }), '/');
  assert.equal(resolveAuthRedirect({ path: '/login', search: '?next=//evil.example.com', status: 'authenticated' }), '/');
});

test('never redirects away from verify-email, reset-password, or forgot-password', () => {
  assert.equal(resolveAuthRedirect({ path: '/verify-email', search: '?token=abc', status: 'authenticated' }), null);
  assert.equal(resolveAuthRedirect({ path: '/reset-password', search: '?token=abc', status: 'authenticated' }), null);
  assert.equal(resolveAuthRedirect({ path: '/forgot-password', search: '', status: 'authenticated' }), null);
});

test('redirects guest from protected routes to /login?next=...', () => {
  assert.equal(isProtectedPath('/vault'), true);
  assert.equal(isProtectedPath('/admin'), true);
  assert.equal(isProtectedPath('/login'), false);
  const target = resolveAuthRedirect({ path: '/vault', search: '', status: 'guest' });
  assert.ok(target && target.startsWith('/login'));
});

test('returns null in mockAuth mode or while loading', () => {
  assert.equal(resolveAuthRedirect({ path: '/login', search: '', status: 'authenticated', mockAuth: true }), null);
  assert.equal(resolveAuthRedirect({ path: '/login', search: '', status: 'loading' }), null);
  assert.equal(resolveAuthRedirect({ path: '/vault', search: '', status: 'loading' }), null);
});
