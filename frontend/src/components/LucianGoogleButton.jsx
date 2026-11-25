/**
 * Lucian UX/UI Prompt #401 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#401
 * Ported for AuraMeme — Google Sign-In Button & Onboarding Modal.
 */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';
import { safeReturnUrl } from '../return-url.js';
import { showDemoMessage } from '../runtime.js';

export function GoogleMarkSvg({ className = '', size = 20 }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

export default function LucianGoogleButton({ disabled = false }) {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [state, setState] = useState('idle'); // 'idle' | 'busy' | 'ok'
  const [liveText, setLiveText] = useState('');
  const [onboarding, setOnboarding] = useState(null);
  const [chosenTag, setChosenTag] = useState('');
  const [tagError, setTagError] = useState('');
  const [onboardingBusy, setOnboardingBusy] = useState(false);

  const lbRef = useRef(null);
  const s0Ref = useRef(null);
  const s1Ref = useRef(null);
  const s2Ref = useRef(null);

  function fitLabel(index) {
    const lb = lbRef.current;
    const spans = [s0Ref.current, s1Ref.current, s2Ref.current];
    const target = spans[index];
    if (!lb || !target) return;
    const w = target.offsetWidth;
    lb.style.width = w ? `${w}px` : '';
  }

  useEffect(() => {
    if (state === 'idle' && lbRef.current) {
      lbRef.current.style.width = '';
    }
  }, [language, state]);

  useEffect(() => {
    const onOnboarding = (ev) => {
      const detail = ev.detail;
      if (detail && detail.status === 'needs_onboarding') {
        setState('idle');
        if (lbRef.current) lbRef.current.style.width = '';
        setOnboarding(detail);
        setChosenTag(detail.suggested_tag || '');
        setTagError('');
      }
    };
    window.addEventListener('aurameme-google-onboarding', onOnboarding);
    return () => window.removeEventListener('aurameme-google-onboarding', onOnboarding);
  }, []);

  function resetToIdle() {
    setState('idle');
    setLiveText('');
    fitLabel(0);
    setTimeout(() => {
      if (lbRef.current) lbRef.current.style.width = '';
    }, 550);
  }

  function finishSuccessAndRedirect() {
    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setState('ok');
    fitLabel(2);
    setLiveText(t('Đã đăng nhập bằng Google', 'Signed in with Google'));
    setTimeout(() => {
      const next = new URLSearchParams(location.search).get('next');
      location.assign(safeReturnUrl(next));
    }, rm ? 120 : 650);
  }

  async function handleClick(ev) {
    ev.preventDefault();
    if (disabled || state === 'busy' || state === 'ok') return;

    fitLabel(0);
    if (lbRef.current) void lbRef.current.offsetWidth;
    setState('busy');
    fitLabel(1);
    setLiveText(t('Đang kết nối với Google', 'Connecting to Google'));

    try {
      const cfg = await auth.googleConfig();
      if (!cfg?.enabled || !cfg?.client_id) {
        resetToIdle();
        showDemoMessage(
          t(
            'Đăng nhập Google chưa được cấu hình trên máy chủ.',
            'Google sign-in is not configured on this server yet.'
          )
        );
        return;
      }
      if (!window.google?.accounts?.id) {
        await new Promise((resolve, reject) => {
          const s = document.createElement('script');
          s.src = 'https://accounts.google.com/gsi/client';
          s.async = true;
          s.defer = true;
          s.onload = resolve;
          s.onerror = reject;
          document.head.appendChild(s);
        });
      }
      const nonce = crypto.randomUUID();
      window.google.accounts.id.initialize({
        client_id: cfg.client_id,
        nonce,
        callback: async (resp) => {
          if (!resp?.credential) {
            resetToIdle();
            return;
          }
          setState('busy');
          fitLabel(1);
          try {
            const res = await auth.googleLogin(resp.credential, nonce);
            if (res?.status === 'needs_onboarding') {
              resetToIdle();
              setOnboarding(res);
              setChosenTag(res.suggested_tag || '');
              setTagError('');
              return;
            }
            finishSuccessAndRedirect();
          } catch (err) {
            resetToIdle();
            showDemoMessage(authMessage(err, language));
          }
        },
      });
      window.google.accounts.id.prompt((notification) => {
        if (
          notification &&
          (notification.isNotDisplayed?.() || notification.isSkippedMoment?.() || notification.isDismissedMoment?.())
        ) {
          resetToIdle();
        }
      });
    } catch (err) {
      resetToIdle();
      showDemoMessage(authMessage(err, language));
    }
  }

  async function handleOnboardingSubmit(ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    if (!onboarding || onboardingBusy) return;
    const cleanTag = chosenTag.trim().toLowerCase().replace(/^@/, '');
    if (!cleanTag || !/^[a-z0-9_]{3,32}$/.test(cleanTag)) {
      setTagError(
        t(
          'Tag phải từ 3 đến 32 ký tự chữ thường, số hoặc gạch dưới (ví dụ: khang_dev).',
          'Tag must be 3–32 characters (a-z, 0-9, _).'
        )
      );
      return;
    }
    setOnboardingBusy(true);
    setTagError('');
    try {
      await auth.googleOnboarding(onboarding.onboarding_token, cleanTag);
      setOnboarding(null);
      finishSuccessAndRedirect();
    } catch (err) {
      setTagError(err?.serverMessage || authMessage(err, language));
    } finally {
      setOnboardingBusy(false);
    }
  }

  return (
    <>
      <div className="ux u401">
        <button
          type="button"
          data-google-auth-button="1"
          className={`u401-b ${state === 'busy' ? 'is-busy' : ''} ${state === 'ok' ? 'is-ok' : ''}`}
          aria-busy={state === 'busy' ? 'true' : undefined}
          disabled={disabled}
          onClick={handleClick}
        >
          <span className="u401-ic" aria-hidden="true">
            <GoogleMarkSvg className="u401-g" size={20} />
            <svg className="u401-arc" viewBox="0 0 20 20">
              <g>
                <circle cx="10" cy="10" r="8" stroke="#EA4335" strokeDashoffset="0" />
                <circle cx="10" cy="10" r="8" stroke="#4285F4" strokeDashoffset="-12.57" />
                <circle cx="10" cy="10" r="8" stroke="#34A853" strokeDashoffset="-25.13" />
                <circle cx="10" cy="10" r="8" stroke="#FBBC05" strokeDashoffset="-37.7" />
              </g>
            </svg>
            <svg className="u401-ck" viewBox="0 0 20 20">
              <path d="M4.8 10.4l3.4 3.4 7-7.4" />
            </svg>
          </span>
          <span className="u401-lb" ref={lbRef}>
            <span className="s0" ref={s0Ref}>
              {t('Tiếp tục với Google', 'Continue with Google')}
            </span>
            <span className="s1" ref={s1Ref} aria-hidden="true">
              {t('Đang kết nối…', 'Connecting…')}
            </span>
            <span className="s2" ref={s2Ref} aria-hidden="true">
              {t('Đã đăng nhập', 'Signed in')}
            </span>
          </span>
        </button>
        <p className="u401-live" role="status">
          {liveText}
        </p>
      </div>

      {onboarding && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-modal="true"
          data-testid="google-onboarding-modal"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.78)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 9999,
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 420,
              background: '#1a1b23',
              border: '1px solid rgba(208,188,255,0.3)',
              borderRadius: 16,
              padding: '26px 28px',
              boxShadow: '0 20px 50px rgba(0,0,0,0.85), 0 0 35px rgba(208,188,255,0.25)',
              position: 'relative',
            }}
          >
            <div style={{ textAlign: 'center', marginBottom: 18 }}>
              <div
                data-testid="google-onboarding-logo"
                style={{
                  width: 38,
                  height: 38,
                  margin: '0 auto 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <GoogleMarkSvg size={34} />
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: '#e3e1ed', margin: '0 0 6px' }}>
                {t('Hoàn tất đăng ký với Google', 'Complete Google Sign Up')}
              </h2>
              <p style={{ fontSize: 13, color: '#cac4d0', margin: 0 }}>
                {t('Chào mừng', 'Welcome')}{' '}
                <strong style={{ color: '#d0bcff' }}>{onboarding.display_name}</strong>!{' '}
                {t('Hãy chọn @tag người dùng duy nhất của bạn:', 'Choose your unique @tag:')}
              </p>
            </div>

            <form onSubmit={handleOnboardingSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label
                  htmlFor="onboarding-tag"
                  style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#cac4d0', marginBottom: 6 }}
                >
                  {t('@Tag người dùng', '@User tag')}
                </label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <span
                    style={{
                      position: 'absolute',
                      left: 12,
                      color: '#948f9a',
                      fontSize: 16,
                      fontWeight: 700,
                      pointerEvents: 'none',
                    }}
                  >
                    @
                  </span>
                  <input
                    id="onboarding-tag"
                    type="text"
                    value={chosenTag}
                    onChange={(e) => {
                      setChosenTag(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''));
                      setTagError('');
                    }}
                    placeholder="khang_dev"
                    maxLength={32}
                    style={{
                      width: '100%',
                      height: 44,
                      paddingLeft: 30,
                      paddingRight: 12,
                      background: '#12131b',
                      border: tagError ? '1px solid #ea4335' : '1px solid rgba(208,188,255,0.25)',
                      borderRadius: 10,
                      color: '#e3e1ed',
                      fontFamily: 'monospace',
                      fontSize: 14,
                      outline: 'none',
                    }}
                    autoFocus
                  />
                </div>
                {tagError ? (
                  <span role="alert" style={{ display: 'block', color: '#ea4335', fontSize: 12, marginTop: 4 }}>
                    {tagError}
                  </span>
                ) : (
                  <span style={{ display: 'block', color: '#948f9a', fontSize: 11, marginTop: 4 }}>
                    {t('3–32 ký tự chữ thường, số hoặc dấu gạch dưới', '3–32 lowercase letters, numbers or underscores')}
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setOnboarding(null);
                  }}
                  style={{
                    flex: 1,
                    height: 42,
                    borderRadius: 10,
                    background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    color: '#e3e1ed',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {t('Hủy', 'Cancel')}
                </button>
                <button
                  type="submit"
                  disabled={onboardingBusy}
                  style={{
                    flex: 2,
                    height: 42,
                    borderRadius: 10,
                    background: 'linear-gradient(135deg, #5424af 0%, #00d4ff 100%)',
                    border: 'none',
                    color: '#ffffff',
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: 'pointer',
                    boxShadow: '0 4px 14px rgba(84,36,175,0.4)',
                    opacity: onboardingBusy ? 0.7 : 1,
                  }}
                >
                  {onboardingBusy ? t('Đang xử lý...', 'Processing...') : t('Hoàn tất đăng ký', 'Finish Registration')}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
