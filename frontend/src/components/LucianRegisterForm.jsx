/**
 * Lucian UX/UI Prompt #244 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#244
 * Ported for AuraMeme — Register Form Validation + Privacy Policy Checkbox + Lucian #401 Google Sign-In.
 */
import React, { useState, useRef } from 'react';
import { auth, MOCK_AUTH } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { USER_KEY, identifyDemoUser } from '../demo.js';
import { usePreferences } from '../PreferencesContext.jsx';
import { showDemoMessage } from '../runtime.js';
import LucianGoogleButton from './LucianGoogleButton.jsx';

export default function LucianRegisterForm() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [displayName, setDisplayName] = useState('');
  const [username, setUsername] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [terms, setTerms] = useState(false); // Unchecked by default per Checkpoint B3

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [tried, setTried] = useState(false);
  const [summaryKeys, setSummaryKeys] = useState([]);
  const [shakeKeys, setShakeKeys] = useState({});
  const [serverErrors, setServerErrors] = useState({});
  const [isBusy, setIsBusy] = useState(false);
  const [isDone, setIsDone] = useState(false);

  const fieldRefs = {
    displayName: useRef(null),
    username: useRef(null),
    identifier: useRef(null),
    password: useRef(null),
    confirmPassword: useRef(null),
    terms: useRef(null),
  };
  const inputRefs = {
    displayName: useRef(null),
    username: useRef(null),
    identifier: useRef(null),
    password: useRef(null),
    confirmPassword: useRef(null),
    terms: useRef(null),
  };

  const cleanTag = username.trim().replace(/^@/, '').trim().toLowerCase();
  const cleanEmail = identifier.trim().toLowerCase();
  const effectiveDisplayName = displayName.trim() || username.trim().replace(/^@/, '').trim();

  const fieldMeta = [
    {
      key: 'displayName',
      label: t('Tên hiển thị', 'Display name'),
      value: effectiveDisplayName,
      valid: effectiveDisplayName.length >= 1 && effectiveDisplayName.length <= 80 && !serverErrors.displayName,
      error:
        serverErrors.displayName ||
        t('Vui lòng nhập tên hiển thị (1–80 ký tự).', 'Please enter your display name (1–80 characters).'),
    },
    {
      key: 'username',
      label: t('@Tag người dùng', '@User tag'),
      value: username,
      valid: /^[a-z0-9_]{3,32}$/.test(cleanTag) && !serverErrors.username,
      error:
        serverErrors.username ||
        t(
          'Tag phải từ 3 đến 32 ký tự chữ thường, số hoặc gạch dưới (ví dụ: khang_dev).',
          'Tag must be 3–32 characters (a-z, 0-9, _).'
        ),
    },
    {
      key: 'identifier',
      label: 'Email',
      value: identifier,
      valid: /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(cleanEmail) && !serverErrors.identifier,
      error:
        serverErrors.identifier ||
        t('Email không hợp lệ (ví dụ: name@example.com).', 'That doesn’t look like an email (e.g. name@example.com).'),
    },
    {
      key: 'password',
      label: t('Mật khẩu', 'Password'),
      value: password,
      valid: password.length >= 12 && password.length <= 128 && !serverErrors.password,
      error:
        serverErrors.password ||
        t('Mật khẩu phải từ 12 đến 128 ký tự.', 'Use a password between 12 and 128 characters.'),
    },
    {
      key: 'confirmPassword',
      label: t('Xác nhận mật khẩu', 'Confirm password'),
      value: confirmPassword,
      valid: confirmPassword.length >= 12 && confirmPassword === password && !serverErrors.confirmPassword,
      error:
        serverErrors.confirmPassword ||
        t('Mật khẩu xác nhận không khớp.', 'Confirmation password does not match.'),
    },
    {
      key: 'terms',
      label: t('Chính sách bảo mật', 'Privacy Policy'),
      value: terms ? '1' : '',
      valid: terms === true && !serverErrors.terms,
      error:
        serverErrors.terms ||
        t(
          'Vui lòng đồng ý với Chính sách bảo mật của AuraMeme.',
          'Please agree to AuraMeme’s Privacy Policy.'
        ),
    },
  ];

  const metaByKey = Object.fromEntries(fieldMeta.map((m) => [m.key, m]));
  const invalidKeys = fieldMeta.filter((m) => !m.valid).map((m) => m.key);
  const showSummary = tried && invalidKeys.length > 0;

  function triggerShake(keys) {
    const next = {};
    for (const k of keys) next[k] = true;
    setShakeKeys(next);
    setTimeout(() => setShakeKeys({}), 420);
  }

  function scrollToAndFocus(key) {
    const el = fieldRefs[key]?.current;
    const inp = inputRefs[key]?.current;
    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (el && typeof el.scrollIntoView === 'function') {
      try {
        el.scrollIntoView({ behavior: rm ? 'auto' : 'smooth', block: 'center' });
      } catch {
        el.scrollIntoView();
      }
    }
    setTimeout(() => {
      inp?.focus({ preventScroll: true });
    }, rm ? 0 : 180);
  }

  async function handleSubmit(ev) {
    ev.preventDefault();
    if (isBusy || isDone) return;

    setTried(true);
    setServerErrors({});

    const currentBad = fieldMeta
      .filter((m) => {
        if (m.key === 'displayName') return !(effectiveDisplayName.length >= 1 && effectiveDisplayName.length <= 80);
        if (m.key === 'username') return !/^[a-z0-9_]{3,32}$/.test(cleanTag);
        if (m.key === 'identifier') return !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(cleanEmail);
        if (m.key === 'password') return !(password.length >= 12 && password.length <= 128);
        if (m.key === 'confirmPassword') return !(confirmPassword.length >= 12 && confirmPassword === password);
        if (m.key === 'terms') return !terms;
        return false;
      })
      .map((m) => m.key);

    if (currentBad.length > 0) {
      setSummaryKeys(currentBad);
      triggerShake(currentBad);
      scrollToAndFocus(currentBad[0]);
      if (MOCK_AUTH && currentBad.includes('confirmPassword') && confirmPassword !== password) {
        showDemoMessage('Mật khẩu xác nhận không khớp.');
      }
      return;
    }

    if (MOCK_AUTH) {
      const demo = identifyDemoUser(cleanEmail);
      try {
        localStorage.setItem(USER_KEY, JSON.stringify({ displayName: demo.displayName, username: demo.username }));
      } catch {
        showDemoMessage('Không lưu được phiên demo. Vui lòng cho phép lưu trữ trình duyệt.');
        return;
      }
      setIsDone(true);
      setTimeout(() => location.assign('/'), 160);
      return;
    }

    setIsBusy(true);
    try {
      const regRes = await auth.register({
        email: cleanEmail,
        password,
        username: cleanTag,
        display_name: effectiveDisplayName,
      });
      setIsDone(true);
      if (regRes?.status === 'pending_verification') {
        try {
          sessionStorage.setItem('aurameme_last_registered_email', cleanEmail);
          const target = Date.now() + 30000;
          sessionStorage.setItem('aurameme_verify_cooldown_' + cleanEmail.toLowerCase(), target.toString());
        } catch {}
        location.assign('/login?pending_verification=' + encodeURIComponent(cleanEmail));
      } else {
        location.assign('/login?registered=1');
      }
    } catch (error) {
      const msg = authMessage(error, language);
      let targetKey = 'identifier';
      if (error.code === 'USERNAME_EXISTS' || /tag|username/i.test(error.message || '')) {
        targetKey = 'username';
      } else if (error.code === 'EMAIL_EXISTS' || /email/i.test(error.message || '')) {
        targetKey = 'identifier';
      } else if (/password/i.test(error.message || '')) {
        targetKey = 'password';
      }
      setServerErrors({ [targetKey]: msg });
      setSummaryKeys([targetKey]);
      triggerShake([targetKey]);
      scrollToAndFocus(targetKey);
    } finally {
      setIsBusy(false);
    }
  }

  function renderFieldStateClass(key) {
    const meta = metaByKey[key];
    const isBad = tried && !meta.valid;
    const isGood = tried && meta.valid && Boolean(meta.value);
    const isShake = Boolean(shakeKeys[key]);
    return `u244-fd ${isBad ? 'is-bad' : ''} ${isGood ? 'is-good' : ''} ${isShake ? 'is-shake' : ''}`;
  }

  return (
    <div className={`ux u244-register ${showSummary ? 'is-err' : ''}`}>
      <form
        className="u244-form"
        id="loginForm"
        data-lucian-submit="1"
        onSubmit={handleSubmit}
        noValidate
        aria-label={t('Biểu mẫu đăng ký', 'Sign-up form')}
      >
        {/* Error summary box (#244) */}
        <div className="u244-sm" role={showSummary ? 'alert' : undefined} aria-live="polite">
          <div>
            <div className="u244-sb">
              <b>
                <i aria-hidden="true">!</i>
                <span className="u244-ct">
                  {t(
                    `Có ${invalidKeys.length} trường cần kiểm tra`,
                    `${invalidKeys.length} ${invalidKeys.length === 1 ? 'field needs' : 'fields need'} attention`
                  )}
                </span>
              </b>
              <ul>
                {summaryKeys.map((key) => {
                  const meta = metaByKey[key];
                  if (!meta) return null;
                  const fixed = meta.valid;
                  return (
                    <li key={key} data-field={key} className={fixed ? 'is-fixed' : ''}>
                      <a
                        href={`#${key === 'terms' ? 'terms' : key}`}
                        onClick={(ev) => {
                          ev.preventDefault();
                          scrollToAndFocus(key);
                        }}
                      >
                        {meta.label}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>

        {/* 1. Display Name */}
        <div className={renderFieldStateClass('displayName')} ref={fieldRefs.displayName}>
          <label htmlFor="displayName">{t('Tên hiển thị', 'Display name')}</label>
          <div className="u244-bx">
            <span className="material-symbols-outlined u244-lead-ic" aria-hidden="true">
              badge
            </span>
            <input
              ref={inputRefs.displayName}
              id="displayName"
              name="displayName"
              type="text"
              className="u244-in"
              placeholder={t('Ví dụ: Khang Dev, Kien Dev', 'e.g. Khang Dev, Kien Dev')}
              maxLength={80}
              value={displayName}
              aria-invalid={tried && !metaByKey.displayName.valid}
              aria-describedby="err-displayName"
              onChange={(e) => {
                setDisplayName(e.target.value);
                if (serverErrors.displayName) setServerErrors((s) => ({ ...s, displayName: undefined }));
              }}
              disabled={isBusy || isDone}
            />
            <span className="u244-ok" aria-hidden="true" />
          </div>
          <div className="u244-ms">
            <div>
              <span id="err-displayName" className="error-hint">
                {tried && !metaByKey.displayName.valid ? metaByKey.displayName.error : ''}
              </span>
            </div>
          </div>
        </div>

        {/* 2. @Tag (username) */}
        <div className={renderFieldStateClass('username')} ref={fieldRefs.username}>
          <div className="u244-lb-row">
            <label htmlFor="username">{t('@Tag người dùng (duy nhất)', '@User tag (unique)')}</label>
            <span className="u244-hint-inline">{t('3–32 ký tự a-z, 0-9, _', '3–32 chars a-z, 0-9, _')}</span>
          </div>
          <div className="u244-bx">
            <span className="material-symbols-outlined u244-lead-ic" aria-hidden="true">
              alternate_email
            </span>
            <input
              ref={inputRefs.username}
              id="username"
              name="username"
              type="text"
              className="u244-in font-mono"
              placeholder="khang_dev"
              maxLength={32}
              value={username}
              aria-invalid={tried && !metaByKey.username.valid}
              aria-describedby="err-username"
              onChange={(e) => {
                setUsername(e.target.value);
                if (serverErrors.username) setServerErrors((s) => ({ ...s, username: undefined }));
              }}
              disabled={isBusy || isDone}
            />
            <span className="u244-ok" aria-hidden="true" />
          </div>
          <div className="u244-ms">
            <div>
              <span id="err-username" className="error-hint">
                {tried && !metaByKey.username.valid ? metaByKey.username.error : ''}
              </span>
            </div>
          </div>
        </div>

        {/* 3. Email (identifier) */}
        <div className={renderFieldStateClass('identifier')} ref={fieldRefs.identifier}>
          <label htmlFor="identifier">Email</label>
          <div className="u244-bx">
            <span className="material-symbols-outlined u244-lead-ic" aria-hidden="true">
              mail
            </span>
            <input
              ref={inputRefs.identifier}
              id="identifier"
              name="identifier"
              type="email"
              className="u244-in"
              placeholder="name@example.com"
              value={identifier}
              aria-invalid={tried && !metaByKey.identifier.valid}
              aria-describedby="err-identifier"
              onChange={(e) => {
                setIdentifier(e.target.value);
                if (serverErrors.identifier) setServerErrors((s) => ({ ...s, identifier: undefined }));
              }}
              disabled={isBusy || isDone}
            />
            <span className="u244-ok" aria-hidden="true" />
          </div>
          <div className="u244-ms">
            <div>
              <span id="err-identifier" className="error-hint">
                {tried && !metaByKey.identifier.valid ? metaByKey.identifier.error : ''}
              </span>
            </div>
          </div>
        </div>

        {/* 4. Password */}
        <div className={renderFieldStateClass('password')} ref={fieldRefs.password}>
          <div className="u244-lb-row">
            <label htmlFor="password">{t('Mật khẩu', 'Password')}</label>
            <span className="u244-hint-inline">{t('12–128 ký tự', '12–128 characters')}</span>
          </div>
          <div className="u244-bx u244-bx-pw">
            <span className="material-symbols-outlined u244-lead-ic" aria-hidden="true">
              lock
            </span>
            <input
              ref={inputRefs.password}
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              className="u244-in u244-in-pw"
              placeholder={t('12–128 ký tự', '12–128 characters')}
              minLength={12}
              maxLength={128}
              value={password}
              aria-invalid={tried && !metaByKey.password.valid}
              aria-describedby="err-password"
              onChange={(e) => {
                setPassword(e.target.value);
                if (serverErrors.password) setServerErrors((s) => ({ ...s, password: undefined }));
              }}
              disabled={isBusy || isDone}
            />
            <button
              type="button"
              id="togglePassword"
              className="u244-pw-toggle"
              aria-label={showPassword ? t('Ẩn mật khẩu', 'Hide password') : t('Hiện mật khẩu', 'Show password')}
              onClick={() => setShowPassword((v) => !v)}
            >
              <span className="material-symbols-outlined text-[19px]" id="eyeIcon">
                {showPassword ? 'visibility_off' : 'visibility'}
              </span>
            </button>
            <span className="u244-ok u244-ok-pw" aria-hidden="true" />
          </div>
          <div className="u244-ms">
            <div>
              <span id="err-password" className="error-hint">
                {tried && !metaByKey.password.valid ? metaByKey.password.error : ''}
              </span>
            </div>
          </div>
        </div>

        {/* 5. Confirm Password */}
        <div className={renderFieldStateClass('confirmPassword')} ref={fieldRefs.confirmPassword}>
          <label htmlFor="confirmPassword">{t('Xác nhận mật khẩu', 'Confirm password')}</label>
          <div className="u244-bx u244-bx-pw">
            <span className="material-symbols-outlined u244-lead-ic" aria-hidden="true">
              lock_reset
            </span>
            <input
              ref={inputRefs.confirmPassword}
              id="confirmPassword"
              name="confirmPassword"
              type={showConfirm ? 'text' : 'password'}
              className="u244-in u244-in-pw"
              placeholder={t('Nhập lại mật khẩu chính xác', 'Re-enter your password')}
              minLength={12}
              maxLength={128}
              value={confirmPassword}
              aria-invalid={tried && !metaByKey.confirmPassword.valid}
              aria-describedby="err-confirmPassword"
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (serverErrors.confirmPassword) setServerErrors((s) => ({ ...s, confirmPassword: undefined }));
              }}
              disabled={isBusy || isDone}
            />
            <button
              type="button"
              id="toggleConfirmPassword"
              className="u244-pw-toggle"
              aria-label={
                showConfirm
                  ? t('Ẩn mật khẩu xác nhận', 'Hide confirm password')
                  : t('Hiện mật khẩu xác nhận', 'Show confirm password')
              }
              onClick={() => setShowConfirm((v) => !v)}
            >
              <span className="material-symbols-outlined text-[19px]" id="eyeIconConfirm">
                {showConfirm ? 'visibility_off' : 'visibility'}
              </span>
            </button>
            <span className="u244-ok u244-ok-pw" aria-hidden="true" />
          </div>
          <div className="u244-ms">
            <div>
              <span id="err-confirmPassword" className="error-hint">
                {tried && !metaByKey.confirmPassword.valid ? metaByKey.confirmPassword.error : ''}
              </span>
            </div>
          </div>
        </div>

        {/* 6. Privacy Policy Checkbox (Unchecked by default, links only /privacy.html) */}
        <div
          ref={fieldRefs.terms}
          className={`u244-ag-wrap ${tried && !metaByKey.terms.valid ? 'is-bad' : ''} ${
            shakeKeys.terms ? 'is-shake' : ''
          }`}
        >
          <label className="u244-ag" htmlFor="terms">
            <input
              ref={inputRefs.terms}
              id="terms"
              name="terms"
              type="checkbox"
              checked={terms}
              aria-invalid={tried && !metaByKey.terms.valid}
              aria-describedby="err-terms"
              onChange={(e) => {
                setTerms(e.target.checked);
                if (serverErrors.terms) setServerErrors((s) => ({ ...s, terms: undefined }));
              }}
              disabled={isBusy || isDone}
            />
            <i aria-hidden="true" />
            <span>
              {isEn ? (
                <>
                  I agree to AuraMeme&apos;s{' '}
                  <a
                    href="/privacy.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Privacy Policy
                  </a>
                </>
              ) : (
                <>
                  Tôi đồng ý với{' '}
                  <a
                    href="/privacy.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Chính sách bảo mật
                  </a>{' '}
                  của AuraMeme
                </>
              )}
            </span>
          </label>
          <div className="u244-ms">
            <div>
              <span id="err-terms" className="error-hint">
                {tried && !metaByKey.terms.valid ? metaByKey.terms.error : ''}
              </span>
            </div>
          </div>
        </div>

        {/* Submit button */}
        <button
          type="submit"
          id="submitBtn"
          className={`u244-go ${isDone ? 'is-done' : ''}`}
          disabled={isBusy || isDone}
          aria-busy={isBusy}
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
            {isDone ? 'check_circle' : 'person_add'}
          </span>
          <span>
            {isDone
              ? t('Hoàn tất! Đang chuyển hướng…', 'You’re in! Redirecting…')
              : isBusy
                ? t('Đang xử lý…', 'Creating account…')
                : t('Đăng ký tài khoản', 'Create account')}
          </span>
        </button>

        {/* Divider */}
        <div className="relative flex items-center justify-center my-3.5">
          <div className="w-full h-[1px] bg-surface-variant" />
          <span className="absolute px-3 bg-surface-container u403-divider-text">
            {t('Hoặc tiếp tục với', 'Or continue with')}
          </span>
        </div>

        {/* Lucian #401 Google Sign-In Button */}
        <LucianGoogleButton disabled={isBusy || isDone} />

        {/* Link to login */}
        <div className="text-center pt-3">
          <p className="font-body-md text-body-md text-on-surface-variant text-[13px]">
            {t('Đã có tài khoản?', 'Already have an account?')}
            <a
              className="font-label-lg text-label-lg text-secondary hover:text-tertiary transition-colors underline underline-offset-4 decoration-secondary/40 hover:decoration-tertiary ml-1.5"
              data-path="dang-nhap"
              href="/login"
            >
              {t('Đăng nhập ngay', 'Sign in now')}
            </a>
          </p>
        </div>
      </form>
    </div>
  );
}
