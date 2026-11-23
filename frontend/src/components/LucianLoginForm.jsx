/**
 * Lucian UX/UI Prompt #403 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#403
 * Ported for AuraMeme (Task 7 Polish + Lucian #401 Google Button).
 */
import React, { useState, useRef } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';
import { safeReturnUrl } from '../return-url.js';
import LucianGoogleButton from './LucianGoogleButton.jsx';

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
        <p className={`u403-msg ${errorMsg ? 'is-on' : ''}`} role={errorMsg ? 'alert' : undefined} aria-live="polite">
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

        {/* Lucian #401 Google Sign-In Button */}
        <LucianGoogleButton disabled={isBusy || isOk} />

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
    </div>
  );
}
