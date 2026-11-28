import { safeReturnUrl } from './return-url.js';

const PROTECTED_PATHS = new Set([
  '/admin',
  '/contact',
  '/vault',
  '/admin/contacts',
  '/profile',
  '/premium',
  '/premium/checkout',
  '/premium/history',
]);

const GUEST_ONLY_PATHS = new Set(['/login', '/register']);

/**
 * Resolve server-backed navigation redirects without trusting localStorage.
 * Never redirects away from /verify-email, /reset-password, or /forgot-password.
 */
export function resolveAuthRedirect({ path, search = '', status, mockAuth = false }) {
  if (mockAuth) return null;
  if (PROTECTED_PATHS.has(path) && status === 'guest') {
    return '/login?next=' + encodeURIComponent(safeReturnUrl(path + search));
  }
  if (GUEST_ONLY_PATHS.has(path) && status === 'authenticated') {
    const next = new URLSearchParams(search).get('next');
    return safeReturnUrl(next);
  }
  return null;
}

export function isProtectedPath(path) {
  return PROTECTED_PATHS.has(path);
}
