import React, { useEffect, useRef, useState } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';

export default function ResetPasswordPage() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const tokenRef = useRef('');
  const [hasToken, setHasToken] = useState(false);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const raw = (params.get('token') || '').trim();
    if (raw) {
      tokenRef.current = raw;
      setHasToken(true);
      // Remove token from URL bar/referrer immediately after capturing into memory.
      try {
        history.replaceState(null, '', '/reset-password');
      } catch {}
    }
  }, []);

  async function onSubmit(ev) {
    ev.preventDefault();
    if (busy) return;
    if (!tokenRef.current) {
      setError(t('Liên kết đặt lại mật khẩu không hợp lệ hoặc bị thiếu mã xác nhận.', 'Reset link is missing or invalid.'));
      return;
    }
    if (password.length < 12 || password.length > 128) {
      setError(t('Mật khẩu mới cần có từ 12 đến 128 ký tự.', 'New password must be between 12 and 128 characters.'));
      return;
    }
    if (password !== confirm) {
      setError(t('Mật khẩu xác nhận không khớp.', 'Confirmation password does not match.'));
      return;
    }
    setBusy(true);
    setError('');
    try {
      await auth.resetPassword(tokenRef.current, password);
      tokenRef.current = '';
      setDone(true);
    } catch (err) {
      setError(authMessage(err, language));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="account-page" style={{ maxWidth: 480 }}>
      <section className="account-panel" aria-labelledby="reset-title">
        <h1 id="reset-title" style={{ fontSize: 26, marginBottom: 8 }}>
          {t('Đặt lại mật khẩu mới', 'Set a new password')}
        </h1>

        {done ? (
          <div role="status" className="account-panel" style={{ padding: 16, marginBottom: 16 }}>
            <p className="account-success" style={{ margin: '0 0 12px', fontWeight: 600 }}>
              {t(
                'Đặt lại mật khẩu thành công. Các phiên đăng nhập cũ đã được đăng xuất để bảo vệ tài khoản.',
                'Password reset successful. Previous sessions have been signed out to protect your account.',
              )}
            </p>
            <a href="/login" className="account-button primary" style={{ width: '100%' }}>
              {t('Đăng nhập ngay', 'Sign in now')}
            </a>
          </div>
        ) : !hasToken ? (
          <div role="alert" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p className="account-error" style={{ margin: 0 }}>
              {t(
                'Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn. Vui lòng yêu cầu một liên kết mới.',
                'This password reset link is invalid or has expired. Please request a new link.',
              )}
            </p>
            <a href="/forgot-password" className="account-button primary">
              {t('Yêu cầu liên kết mới', 'Request a new link')}
            </a>
          </div>
        ) : (
          <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <p className="account-muted" style={{ marginTop: 0 }}>
              {t('Mật khẩu mới phải có từ 12 đến 128 ký tự.', 'Your new password must be 12 to 128 characters long.')}
            </p>
            <label htmlFor="reset-password">
              <span>{t('Mật khẩu mới', 'New password')}</span>
              <input
                id="reset-password"
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
              />
            </label>
            <label htmlFor="reset-confirm">
              <span>{t('Xác nhận mật khẩu mới', 'Confirm new password')}</span>
              <input
                id="reset-confirm"
                type="password"
                required
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={busy}
              />
            </label>
            {error && (
              <p role="alert" className="account-error" style={{ margin: 0 }}>
                {error}
              </p>
            )}
            <button type="submit" className="account-button primary" disabled={busy}>
              {busy ? t('Đang cập nhật...', 'Updating...') : t('Cập nhật mật khẩu', 'Update password')}
            </button>
          </form>
        )}

        <div style={{ marginTop: 18, textAlign: 'center' }}>
          <a href="/login">{t('← Quay lại đăng nhập', '← Back to sign in')}</a>
        </div>
      </section>
    </main>
  );
}
