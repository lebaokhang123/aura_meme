import React, { useState, useEffect, useRef } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';

export function EnvelopeIcon({ size = 72 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 72 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ display: 'block', margin: '0 auto' }}
    >
      <defs>
        <linearGradient id="auraEnvelopeGrad" x1="9" y1="17" x2="63" y2="55" gradientUnits="userSpaceOnUse">
          <stop offset="0%" style={{ stopColor: 'var(--am-secondary, #d0bcff)' }} />
          <stop offset="100%" style={{ stopColor: 'var(--am-tertiary-container, #4cd7f6)' }} />
        </linearGradient>
        <filter id="auraEnvelopeGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <rect
        x="9"
        y="17"
        width="54"
        height="38"
        rx="6"
        stroke="url(#auraEnvelopeGrad)"
        strokeWidth="2.5"
        fill="none"
        filter="url(#auraEnvelopeGlow)"
      />
      <path
        d="M11 20L36 39L61 20"
        stroke="url(#auraEnvelopeGrad)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const STORAGE_PREFIX = 'aurameme_verify_cooldown_';

export default function PendingVerificationScreen({ email: initialEmail }) {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [email] = useState(() => {
    if (initialEmail && typeof initialEmail === 'string') return initialEmail.trim();
    if (typeof location !== 'undefined') {
      const params = new URLSearchParams(location.search);
      const queryEmail = (params.get('pending_verification') || params.get('email') || '').trim();
      if (queryEmail) {
        try {
          sessionStorage.setItem('aurameme_last_registered_email', queryEmail);
        } catch {}
        return queryEmail;
      }
    }
    try {
      return (sessionStorage.getItem('aurameme_last_registered_email') || '').trim();
    } catch {
      return '';
    }
  });

  const [cooldown, setCooldown] = useState(() => {
    if (typeof window === 'undefined' || !email) return 30;
    try {
      const stored = sessionStorage.getItem(STORAGE_PREFIX + email.toLowerCase());
      if (stored) {
        const remaining = Math.ceil((parseInt(stored, 10) - Date.now()) / 1000);
        if (remaining > 0 && remaining <= 600) return remaining;
        if (remaining <= 0) return 0;
      }
      const target = Date.now() + 30000;
      sessionStorage.setItem(STORAGE_PREFIX + email.toLowerCase(), target.toString());
      return 30;
    } catch {
      return 30;
    }
  });

  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const timerRef = useRef(null);

  useEffect(() => {
    if (cooldown <= 0) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    timerRef.current = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [cooldown]);

  async function handleResend() {
    if (cooldown > 0 || busy || !email) return;
    setBusy(true);
    setErrorMsg('');

    try {
      await auth.resendVerification(email);
      const target = Date.now() + 30000;
      try {
        sessionStorage.setItem(STORAGE_PREFIX + email.toLowerCase(), target.toString());
      } catch {}
      setCooldown(30);
    } catch (err) {
      if (err?.status === 429 && Number.isSafeInteger(err?.retryAfter) && err.retryAfter > 0) {
        const target = Date.now() + err.retryAfter * 1000;
        try {
          sessionStorage.setItem(STORAGE_PREFIX + email.toLowerCase(), target.toString());
        } catch {}
        setCooldown(err.retryAfter);
      }
      setErrorMsg(err?.serverMessage || authMessage(err, language));
    } finally {
      setBusy(false);
    }
  }

  const mins = Math.floor(cooldown / 60);
  const secs = cooldown % 60;
  const timeStr = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

  return (
    <main
      className="w-full flex-1 flex flex-col items-center justify-center min-h-[calc(100vh-160px)] px-4 py-8"
      role="status"
      aria-live="polite"
      style={{
        boxSizing: 'border-box',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          width: '100%',
          maxWidth: 520,
          margin: '0 auto',
          background: 'none',
          border: 'none',
          boxShadow: 'none',
        }}
      >
        {/* 1. Icon phong bì thư, kích thước khoảng 72px, outline, màu tím/cyan nhẹ */}
        <div style={{ marginBottom: 24 }}>
          <EnvelopeIcon size={72} />
        </div>

        {/* 2. "Chúng tôi đã gửi liên kết xác minh đến" */}
        <p
          style={{
            fontSize: '1rem',
            fontWeight: 500,
            color: 'var(--am-on-surface-variant, #cac4d0)',
            margin: '0 0 10px',
            lineHeight: 1.5,
          }}
        >
          {t('Chúng tôi đã gửi liên kết xác minh đến', 'We have sent a verification link to')}
        </p>

        {/* 3. Địa chỉ email thực tế của người dùng, nổi bật hơn các dòng chữ khác */}
        <div
          data-testid="verification-pending-email"
          style={{
            fontSize: '1.25rem',
            fontWeight: 800,
            color: 'var(--am-on-surface, #e3e1ed)',
            letterSpacing: '-0.01em',
            wordBreak: 'break-all',
            lineHeight: 1.4,
            margin: '0 0 10px',
          }}
        >
          {email || 'user@example.com'}
        </div>

        {/* 4. "Vui lòng xác minh để hoàn tất đăng ký tài khoản AuraMeme" */}
        <p
          style={{
            fontSize: '0.9375rem',
            fontWeight: 400,
            color: 'var(--am-on-surface-variant, #948f9a)',
            margin: '0 0 24px',
            lineHeight: 1.5,
          }}
        >
          {t(
            'Vui lòng xác minh để hoàn tất đăng ký tài khoản AuraMeme',
            'Please verify to complete your AuraMeme account registration'
          )}
        </p>

        {/* 5. "Gửi lại sau 00:30" với bộ đếm ngược thực tế từng giây / text link "Gửi lại email xác minh" */}
        <div style={{ minHeight: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {cooldown > 0 ? (
            <span
              style={{
                fontSize: '0.9375rem',
                color: 'var(--am-on-surface-variant, #948f9a)',
                fontVariantNumeric: 'tabular-nums',
                letterSpacing: '0.02em',
              }}
            >
              {t(`Gửi lại sau ${timeStr}`, `Resend in ${timeStr}`)}
            </span>
          ) : (
            <button
              type="button"
              onClick={handleResend}
              disabled={busy}
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                color: 'var(--am-secondary, #d0bcff)',
                fontSize: '0.9375rem',
                fontWeight: 600,
                cursor: busy ? 'wait' : 'pointer',
                textDecoration: 'underline',
                textUnderlineOffset: 4,
                transition: 'color 0.2s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--am-tertiary-container, #4cd7f6)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--am-secondary, #d0bcff)')}
            >
              {busy
                ? t('Đang gửi lại...', 'Resending...')
                : t('Gửi lại email xác minh', 'Resend verification email')}
            </button>
          )}
        </div>

        {/* Thông báo lỗi chỉ xuất hiện khi thực sự xảy ra lỗi */}
        {errorMsg ? (
          <p
            role="alert"
            style={{
              color: 'var(--am-error, #ea4335)',
              fontSize: '0.8125rem',
              marginTop: 16,
              marginBottom: 0,
              lineHeight: 1.4,
            }}
          >
            {errorMsg}
          </p>
        ) : null}
      </div>
    </main>
  );
}
