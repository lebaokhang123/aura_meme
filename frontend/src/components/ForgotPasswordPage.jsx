import React, { useState } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';

export default function ForgotPasswordPage() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function onSubmit(ev) {
    ev.preventDefault();
    if (busy) return;
    const trimmed = email.trim();
    if (!trimmed) {
      setError(t('Vui lòng nhập địa chỉ email.', 'Please enter your email address.'));
      return;
    }
    setBusy(true);
    setError('');
    try {
      await auth.forgotPassword(trimmed);
      setDone(true);
    } catch (err) {
      setError(authMessage(err, language));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="account-page" style={{ maxWidth: 480 }}>
      <section className="account-panel" aria-labelledby="forgot-title">
        <h1 id="forgot-title" style={{ fontSize: 26, marginBottom: 8 }}>
          {t('Quên mật khẩu', 'Forgot password')}
        </h1>
        <p className="account-muted" style={{ marginTop: 0, marginBottom: 20 }}>
          {t(
            'Nhập email đã đăng ký tài khoản AuraMeme. Nếu hợp lệ, chúng tôi sẽ gửi liên kết đặt lại mật khẩu có hiệu lực trong 30 phút.',
            'Enter the email linked to your AuraMeme account. If eligible, we will send a 30-minute one-time password reset link.',
          )}
        </p>

        {done ? (
          <div role="status" className="account-panel" style={{ padding: 16, marginBottom: 16 }}>
            <p className="account-success" style={{ margin: 0, fontWeight: 600 }}>
              {t(
                'Nếu địa chỉ email tồn tại và đủ điều kiện khôi phục, chúng tôi đã gửi liên kết đặt lại mật khẩu. Vui lòng kiểm tra hộp thư đến hoặc thư mục Spam.',
                'If the email address exists and is eligible for recovery, we have sent a password reset link. Please check your inbox or spam folder.',
              )}
            </p>
          </div>
        ) : (
          <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label htmlFor="forgot-email">
              <span>{t('Địa chỉ Email', 'Email address')}</span>
              <input
                id="forgot-email"
                name="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={busy}
              />
            </label>
            {error && (
              <p role="alert" className="account-error" style={{ margin: 0 }}>
                {error}
              </p>
            )}
            <button type="submit" className="account-button primary" disabled={busy}>
              {busy
                ? t('Đang gửi yêu cầu...', 'Sending request...')
                : t('Gửi liên kết đặt lại mật khẩu', 'Send reset link')}
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
