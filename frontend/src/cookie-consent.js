// Cookie consent storage & policy helper for AuraMeme (Task 8).
// Essential cookies (am_session HttpOnly auth, CSRF pre-session) are always active and never blocked.
// AuraMeme currently runs zero third-party analytics/marketing scripts; optional preferences default to false.

export const COOKIE_CONSENT_KEY = 'aurameme-cookie-consent-v1';
export const COOKIE_CONSENT_VERSION = 1;

export function readCookieConsent(storage = typeof localStorage !== 'undefined' ? localStorage : null) {
  if (!storage) return null;
  try {
    const raw = storage.getItem(COOKIE_CONSENT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      !parsed ||
      parsed.version !== COOKIE_CONSENT_VERSION ||
      parsed.essential !== true ||
      typeof parsed.optional !== 'boolean' ||
      typeof parsed.updatedAt !== 'string' ||
      !Number.isFinite(Date.parse(parsed.updatedAt))
    ) {
      return null;
    }
    return {
      version: COOKIE_CONSENT_VERSION,
      essential: true,
      optional: parsed.optional,
      updatedAt: parsed.updatedAt,
    };
  } catch {
    return null;
  }
}

export function saveCookieConsent(
  { optional = false } = {},
  storage = typeof localStorage !== 'undefined' ? localStorage : null,
  now = new Date(),
) {
  const record = {
    version: COOKIE_CONSENT_VERSION,
    essential: true,
    optional: Boolean(optional),
    updatedAt: now.toISOString(),
  };
  try {
    storage?.setItem(COOKIE_CONSENT_KEY, JSON.stringify(record));
  } catch {
    // Tolerate blocked storage without breaking session or UI.
  }
  return record;
}

export function hasOptionalConsent(storage) {
  const record = readCookieConsent(storage);
  return Boolean(record && record.optional === true);
}
