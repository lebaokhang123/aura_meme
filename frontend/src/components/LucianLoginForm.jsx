/**
 * Lucian UX/UI Prompt #403 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#403
 * Ported for AuraMeme (Task 7 Polish).
 */
import React, { useState, useRef } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';
import { safeReturnUrl } from '../return-url.js';
import { showDemoMessage } from '../runtime.js';

export default function LucianLoginForm() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [focusedField, setFocusedField] = useState(null); // 'identifier' | 'password' | null
  const [errorField, setErrorField] = useState(null); // 'identifier' | 'password' | 'general' | null
  const [errorMsg, setErrorMsg] = useState('');
  const [isShake, setIsShake] = useState(null); // 'identifier' | 'password'
  const [isBusy, setIsBusy] = useState(false);
  const [isOk, setIsOk] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [onboarding, setOnboarding] = useState(null);
  const [chosenTag, setChosenTag] = useState('');
  const [tagError, setTagError] = useState('');
  const [onboardingBusy, setOnboardingBusy] = useState(false);


  const identifierRef = useRef(null);
  const passwordRef = useRef(null);

  function triggerShake(field) {
    setIsShake(field);
    setTimeout(() => setIsShake(null), 450);
  }

  async function handleSubmit(ev) {
    ev.preventDefault();
    if (isBusy || isOk) return;

    const trimmedId = identifier.trim();
    if (!trimmedId) {
      setErrorField('identifier');
      triggerShake('identifier');
      setErrorMsg(t('Vui lòng nhập email hoặc tên đăng nhập.', 'Please enter your email or username.'));
      identifierRef.current?.focus();
      return;
    }

    if (!password) {
      setErrorField('password');
      triggerShake('password');
      setErrorMsg(t('Vui lòng nhập mật khẩu.', 'Please enter your password.'));
      passwordRef.current?.focus();
      return;
    }

    setIsBusy(true);
    setErrorField(null);
    setErrorMsg('');

    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    try {
      await auth.login(trimmedId, password);
      setIsBusy(false);
      setIsOk(true);
      setTimeout(() => {
        const next = new URLSearchParams(location.search).get('next');
        location.assign(safeReturnUrl(next));
      }, rm ? 100 : 700);
    } catch (err) {
      setIsBusy(false);
      setIsOk(false);
      setErrorField('password');
      triggerShake('password');
      setErrorMsg(authMessage(err, language));
      passwordRef.current?.focus();
    }
  }

  async function handleGoogleLogin(ev) {
    ev.preventDefault();
    if (googleBusy) return;
    setGoogleBusy(true);
    try {
      const cfg = await auth.googleConfig();
      if (!cfg?.enabled || !cfg?.client_id) {
        showDemoMessage(
          isEn
            ? 'Google sign-in is not configured on this server yet.'
            : 'Đăng nhập Google chưa được cấu hình trên máy chủ.'
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
          try {
            const res = await auth.googleLogin(resp.credential, nonce);
            if (res?.status === 'needs_onboarding') {
              setOnboarding(res);
              setChosenTag(res.suggested_tag || '');
              setTagError('');
              return;
            }
            const next = new URLSearchParams(location.search).get('next');
            location.assign(safeReturnUrl(next));
          } catch (err) {
            showDemoMessage(authMessage(err, language));
          }
        },
      });
      window.google.accounts.id.prompt();
    } catch (err) {
      showDemoMessage(authMessage(err, language));
    } finally {
      setGoogleBusy(false);
    }
  }

  async function handleOnboardingSubmit(ev) {
    ev.preventDefault();
    if (!onboarding || onboardingBusy) return;
    const cleanTag = chosenTag.trim().toLowerCase().replace(/^@/, '');
    if (!cleanTag || !/^[a-z0-9_]{3,32}$/.test(cleanTag)) {
      setTagError(
        isEn
          ? 'Tag must be 3–32 characters (a-z, 0-9, _).'
          : 'Tag phải từ 3 đến 32 ký tự chữ thường, số hoặc gạch dưới (ví dụ: khang_dev).'
      );
      return;
    }
    setOnboardingBusy(true);
    setTagError('');
    try {
      await auth.googleOnboarding(onboarding.onboarding_token, cleanTag);
      const next = new URLSearchParams(location.search).get('next');
      location.assign(safeReturnUrl(next));
    } catch (err) {
      setTagError(authMessage(err, language));
    } finally {
      setOnboardingBusy(false);
    }
  }


  const idUp = focusedField === 'identifier' || Boolean(identifier);
  const pwUp = focusedField === 'password' || Boolean(password);

  return (
    <div className="ux u403-container">
      <form
        className="u403-form"
        id="loginForm"
        data-lucian-submit="1"
        onSubmit={handleSubmit}
        noValidate
      >
        {/* Identifier field */}
        <div
          className={`u403-f ${focusedField === 'identifier' ? 'is-f' : ''} ${idUp ? 'is-up' : ''} ${
            errorField === 'identifier' ? 'is-err' : ''
          } ${isShake === 'identifier' ? 'is-shake' : ''}`}
        >
          <input
            ref={identifierRef}
            id="identifier"
            name="identifier"
            className="u403-in"
            type="text"
            autoComplete="username"
            spellCheck="false"
            value={identifier}
            onChange={(e) => {
              setIdentifier(e.target.value);
              if (errorField === 'identifier') {
                setErrorField(null);
                setErrorMsg('');
              }
            }}
            onKeyDown={() => {
              if (errorField === 'identifier') {
                setErrorField(null);
                setErrorMsg('');
              }
            }}
            onFocus={() => setFocusedField('identifier')}
            onBlur={() => setFocusedField(null)}
            disabled={isBusy || isOk}
          />
          <label htmlFor="identifier">{t('Email hoặc tên đăng nhập', 'Email or username')}</label>
        </div>

        {/* Password field */}
        <div
          className={`u403-f u403-pw ${focusedField === 'password' ? 'is-f' : ''} ${pwUp ? 'is-up' : ''} ${
            errorField === 'password' ? 'is-err' : ''
          } ${isShake === 'password' ? 'is-shake' : ''}`}
        >
          <input
            ref={passwordRef}
            id="password"
            name="password"
            className="u403-in"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (errorField === 'password') {
                setErrorField(null);
                setErrorMsg('');
              }
            }}
            onKeyDown={() => {
              if (errorField === 'password') {
                setErrorField(null);
                setErrorMsg('');
              }
            }}
            onFocus={() => setFocusedField('password')}
            onBlur={() => setFocusedField(null)}
            disabled={isBusy || isOk}
          />
          <label htmlFor="password">{t('Mật khẩu', 'Password')}</label>
          <button
            type="button"
            className="u403-eye"
            aria-label={showPassword ? t('Ẩn mật khẩu', 'Hide password') : t('Hiện mật khẩu', 'Show password')}
            aria-pressed={showPassword}
            onClick={() => setShowPassword((v) => !v)}
            tabIndex={0}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <g className="lid">
                <path d="M2 10s3-5.2 8-5.2S18 10 18 10s-3 5.2-8 5.2S2 10 2 10z" />
                <circle cx="10" cy="10" r="2.4" />
              </g>
              <g className="lash">
                <path d="M3 10.4c2 2.4 4.4 3.4 7 3.4s5-1 7-3.4M6 13l-1 1.6M10 14v1.8M14 13l1 1.6" />
              </g>
            </svg>
          </button>
        </div>

        {/* Error message */}
        <p className={`u403-msg ${errorMsg ? 'is-on' : ''}`} role="alert" aria-live="polite">
          {errorMsg}
        </p>

        {/* Forgot password link */}
        <div className="flex justify-end pt-1 pb-2">
          <a
            href="/forgot-password"
            data-forgot-password-link="1"
            className="font-label-sm text-label-sm text-secondary hover:text-tertiary transition-colors underline-offset-4 hover:underline cursor-pointer"
          >
            {t('Quên mật khẩu?', 'Forgot password?')}
          </a>
        </div>

        {/* Submit button */}
        <button
          type="submit"
          id="submitBtn"
          className={`u403-go ${isBusy ? 'is-busy' : ''} ${isOk ? 'is-ok' : ''}`}
          disabled={isBusy || isOk}
          aria-busy={isBusy}
        >
          <span>{t('Đăng nhập', 'Sign in')}</span>
          <i aria-hidden="true" />
          <svg viewBox="0 0 22 22" aria-hidden="true">
            <path d="M5.5 11.5l4 4L17 7.5" />
          </svg>
        </button>

        {/* Divider */}
        <div className="relative flex items-center justify-center my-3.5">
          <div className="w-full h-[1px] bg-surface-variant" />
          <span className="absolute px-3 bg-surface-container u403-divider-text">
            {t('Hoặc tiếp tục với', 'Or continue with')}
          </span>
        </div>

        {/* Google button */}
        <button
          type="button"
          data-google-auth-button="1"
          onClick={handleGoogleLogin}
          disabled={googleBusy || isBusy || isOk}
          className="w-full h-12 px-4 rounded-xl bg-surface-container-low hover:bg-surface-container-high border border-outline-variant text-on-surface font-label-md text-label-md flex items-center justify-center gap-2.5 transition-colors shadow-[inset_0_1px_2px_rgba(0,0,0,0.4)] cursor-pointer"
        >
          <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              fill="#EA3545"
            />
          </svg>
          <span>{t('Tiếp tục với Google', 'Continue with Google')}</span>
        </button>

        {/* Link register */}
        <div className="text-center pt-3">
          <p className="font-body-md text-body-md text-on-surface-variant text-[13px]">
            {t('Chưa có tài khoản?', "Don't have an account?")}
            <a
              className="font-label-lg text-label-lg text-secondary hover:text-tertiary transition-colors underline underline-offset-4 decoration-secondary/40 hover:decoration-tertiary ml-1.5"
              href="/register"
            >
              {t('Đăng ký ngay', 'Register now')}
            </a>
          </p>
        </div>
      </form>

      {onboarding && (
        <div
          role="dialog"
          aria-modal="true"
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
                style={{
                  width: 52,
                  height: 52,
                  margin: '0 auto 12px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, rgba(84,36,175,0.35), rgba(76,215,246,0.35))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid rgba(208,188,255,0.4)',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 28, color: '#d0bcff' }}>
                  alternate_email
                </span>
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

            <form onSubmit={handleOnboardingSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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
                  <span style={{ display: 'block', color: '#ea4335', fontSize: 12, marginTop: 4 }}>
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
                  onClick={() => setOnboarding(null)}
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
        </div>
      )}

    </div>
  );
}
