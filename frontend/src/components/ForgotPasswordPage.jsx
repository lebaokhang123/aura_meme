/**
 * Lucian UX/UI Prompt #405 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#405
 * Ported for AuraMeme (Task 7 Polish).
 */
import React, { useEffect, useRef, useState } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';

const COOL_SECONDS = (typeof window !== 'undefined' && window.__FORGOT_COOL_SECONDS) || 30;

export default function ForgotPasswordPage() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [email, setEmail] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [shake, setShake] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [isSent, setIsSent] = useState(false);
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const [resendStatus, setResendStatus] = useState(null);

  const boxRef = useRef(null);
  const sendBtnRef = useRef(null);
  const planeRef = useRef(null);
  const reBtnRef = useRef(null);
  const timerRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  function fly(from) {
    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (rm || !planeRef.current || !from || !boxRef.current) return;
    const box = boxRef.current;
    const r = from.getBoundingClientRect();
    const bb = box.getBoundingClientRect();
    const k = box.offsetWidth / (bb.width || 1);
    const x = (r.left + r.width / 2 - bb.left - bb.width / 2) * k;
    const y = (r.top + r.height / 2 - bb.top - bb.height / 2) * k;
    planeRef.current.animate(
      [
        { opacity: 0, transform: `translate(${x}px,${y}px) rotate(10deg) scale(.6)` },
        { opacity: 1, transform: `translate(${x + 10}px,${y - 18}px) rotate(-6deg) scale(1.1)`, offset: 0.2 },
        { opacity: 1, transform: `translate(${x + 70}px,${y - 70}px) rotate(-18deg) scale(1)`, offset: 0.6 },
        { opacity: 0, transform: `translate(${x + 150}px,${y - 150}px) rotate(-30deg) scale(.55)` },
      ],
      { duration: 1000, easing: 'cubic-bezier(.3,.1,.4,1)' }
    );
  }

  function startCooldown() {
    if (timerRef.current) clearInterval(timerRef.current);
    setCooldownLeft(COOL_SECONDS);
    let left = COOL_SECONDS;
    timerRef.current = setInterval(() => {
      left -= 1;
      setCooldownLeft(Math.max(0, left));
      if (left <= 0) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 1000);
  }

  async function handleSubmit(ev) {
    ev.preventDefault();
    if (busy) return;
    const trimmed = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(trimmed)) {
      setHasError(true);
      setShake(true);
      setTimeout(() => setShake(false), 500);
      setErrorMsg(t('Vui lòng nhập địa chỉ email hợp lệ.', 'Please enter a valid email address.'));
      inputRef.current?.focus();
      return;
    }

    setBusy(true);
    setHasError(false);
    setErrorMsg('');
    setResendStatus(null);
    fly(sendBtnRef.current);

    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    try {
      await auth.forgotPassword(trimmed);
      setTimeout(() => {
        setIsSent(true);
        startCooldown();
        setBusy(false);
      }, rm ? 0 : 420);
    } catch (err) {
      setBusy(false);
      setHasError(true);
      setShake(true);
      setTimeout(() => setShake(false), 500);
      setErrorMsg(authMessage(err, language));
    }
  }

  async function handleResend() {
    if (cooldownLeft > 0 || busy) return;
    setBusy(true);
    setResendStatus(null);
    fly(reBtnRef.current);
    try {
      await auth.forgotPassword(email.trim());
      startCooldown();
      setResendStatus({
        type: 'success',
        text: t('Đã gửi lại liên kết qua email.', 'A new link has been sent to your email.'),
      });
    } catch (err) {
      if (err?.status === 429 || err?.code === 'RATE_LIMITED') {
        setResendStatus({
          type: 'error',
          text: t('Bạn thao tác quá nhanh. Vui lòng đợi trước khi gửi lại.', 'Too many attempts. Please wait before retrying.'),
        });
      } else {
        setResendStatus({
          type: 'error',
          text: t('Không thể gửi lại. Vui lòng thử lại sau.', 'Could not resend. Please try again later.'),
        });
      }
    } finally {
      setBusy(false);
    }
  }

  function handleChangeEmail() {
    if (timerRef.current) clearInterval(timerRef.current);
    setIsSent(false);
    setHasError(false);
    setErrorMsg('');
    setResendStatus(null);
    setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.select();
    }, 50);
  }

  const isUp = isFocused || Boolean(email);

  return (
    <main className="account-page" style={{ maxWidth: 440, minHeight: 'calc(100vh - 140px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className={`ux u405 ${isSent ? 'is-sent' : ''}`}>
        <div className="u405-box" ref={boxRef}>
          {/* STATE A: Nhập email */}
          <form className="u405-a" onSubmit={handleSubmit} noValidate inert={isSent ? '' : undefined}>
            <h1 className="u405-title">{t('Quên mật khẩu?', 'Forgot password?')}</h1>
            <p className="u405-sub">{t('Nhập email để nhận liên kết đặt lại mật khẩu.', 'Enter your email to receive a password reset link.')}</p>

            <div className={`u405-f ${isFocused ? 'is-f' : ''} ${isUp ? 'is-up' : ''} ${hasError ? 'is-err' : ''} ${shake ? 'is-shake' : ''}`}>
              <input
                ref={inputRef}
                id="forgot-email"
                className="u405-in"
                type="email"
                autoComplete="email"
                spellCheck="false"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (hasError) {
                    setHasError(false);
                    setErrorMsg('');
                  }
                }}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                disabled={busy}
              />
              <label htmlFor="forgot-email">Email</label>
            </div>

            {errorMsg && (
              <p className="u405-msg" role="alert">
                {errorMsg}
              </p>
            )}

            <button type="submit" className="u405-send" ref={sendBtnRef} disabled={busy}>
              {busy ? t('Đang gửi...', 'Sending...') : t('Gửi liên kết', 'Send reset link')}
            </button>

            <div className="u405-back">
              <a href="/login">{t('← Quay lại đăng nhập', '← Back to sign in')}</a>
            </div>
          </form>

          {/* STATE B: Kiểm tra email */}
          <div className="u405-b" role="status" aria-live="polite" inert={!isSent ? '' : undefined}>
            <svg className="u405-env" viewBox="0 0 72 60" aria-hidden="true">
              <rect className="bk" x="6" y="16" width="60" height="40" rx="6" />
              <g className="letter">
                <rect className="lt" x="14" y="6" width="44" height="34" rx="4" />
                <path className="ln" d="M21 15h22M21 21h30M21 27h18" />
              </g>
              <path className="fr" d="M6 22v28a6 6 0 0 0 6 6h48a6 6 0 0 0 6-6V22L38.6 40.6a4.5 4.5 0 0 1-5.2 0z" />
              <path className="fl" d="M8 17.5c-1.2-.9-.6-1.5.9-1.5h54.2c1.5 0 2.1.6.9 1.5L38.4 37a4 4 0 0 1-4.8 0z" />
            </svg>

            <b>{t('Kiểm tra email của bạn', 'Check your email')}</b>

            <span className="u405-to">
              <span className="u405-em">{email}</span>
              <button type="button" className="u405-chg" onClick={handleChangeEmail} aria-label={t('Đổi địa chỉ email', 'Change email address')}>
                {t('Đổi', 'Change')}
              </button>
            </span>

            <p className="u405-spam-note">{t('Vui lòng kiểm tra hộp thư đến hoặc thư rác.', 'Please check your inbox or spam folder.')}</p>

            {resendStatus && (
              <p
                className={`u405-resend-feedback ${resendStatus.type === 'error' ? 'is-error' : 'is-success'}`}
                role={resendStatus.type === 'error' ? 'alert' : 'status'}
              >
                {resendStatus.text}
              </p>
            )}

            <button
              type="button"
              className={`u405-re ${cooldownLeft <= 0 ? 'is-ready' : ''}`}
              ref={reBtnRef}
              disabled={cooldownLeft > 0 || busy}
              onClick={handleResend}
            >
              <span className="u405-ring" aria-hidden="true">
                <svg viewBox="0 0 26 26">
                  <circle className="tr" cx="13" cy="13" r="10" />
                  <circle
                    className="pr"
                    cx="13"
                    cy="13"
                    r="10"
                    style={{ strokeDashoffset: `${(62.8 * (1 - cooldownLeft / COOL_SECONDS)).toFixed(1)}px` }}
                  />
                </svg>
                <em>{cooldownLeft > 0 ? cooldownLeft : ''}</em>
                <i />
              </span>
              <span className="u405-rl">
                {cooldownLeft > 0
                  ? isEn
                    ? `Resend in ${cooldownLeft}s`
                    : `Gửi lại sau ${cooldownLeft}s`
                  : isEn
                  ? 'Resend'
                  : 'Gửi lại'}
              </span>
            </button>

            <div className="u405-back">
              <a href="/login">{t('← Quay lại đăng nhập', '← Back to sign in')}</a>
            </div>
          </div>

          {/* Paper plane */}
          <span className="u405-plane" ref={planeRef} aria-hidden="true">
            <svg viewBox="0 0 30 30">
              <path className="p1" d="M3 14.2 27 4l-7.6 21.6-5.4-6.2z" />
              <path className="p2" d="M14 19.4 27 4 11.2 17.6l1.6 6.4z" />
            </svg>
          </span>
        </div>
      </div>
    </main>
  );
}
