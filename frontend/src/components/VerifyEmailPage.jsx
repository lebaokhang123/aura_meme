import React, { useEffect, useRef, useState } from 'react';
import { auth } from '../auth.js';
import { authMessage } from '../auth-client.js';
import { usePreferences } from '../PreferencesContext.jsx';

export default function VerifyEmailPage() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [status, setStatus] = useState('checking'); // 'checking' | 'success' | 'error'
  const [message, setMessage] = useState('');
  const executedRef = useRef(false);

  useEffect(() => {
    if (executedRef.current) return;
    executedRef.current = true;

    const params = new URLSearchParams(location.search);
    const token = (params.get('token') || '').trim();

    if (!token) {
      setStatus('error');
      setMessage(
        t(
          'Không tìm thấy mã xác minh trong liên kết. Vui lòng kiểm tra lại email của bạn.',
          'No verification token found in link. Please check your email again.'
        )
      );
      return;
    }

    auth
      .verifyEmail(token)
      .then((res) => {
        setStatus('success');
        setMessage(
          res?.message ||
            t(
              'Tài khoản của bạn đã được kích hoạt thành công! Hãy đăng nhập để bắt đầu hành trình tu chân.',
              'Your account has been activated successfully! Please sign in to begin your cultivation journey.'
            )
        );
        try {
          history.replaceState(null, '', '/verify-email');
        } catch {}
      })
      .catch((err) => {
        setStatus('error');
        setMessage(authMessage(err, language));
      });
  }, [language]);

  return (
    <main className="account-page" style={{ maxWidth: 480, margin: '60px auto', padding: '0 16px' }}>
      <section
        className="account-panel"
        aria-labelledby="verify-title"
        style={{
          background: 'rgba(26, 27, 35, 0.95)',
          border: '1px solid rgba(208, 188, 255, 0.15)',
          borderRadius: 16,
          padding: 28,
          boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(16px)',
          textAlign: 'center',
        }}
      >
        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              width: 64,
              height: 64,
              margin: '0 auto 16px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background:
                status === 'success'
                  ? 'linear-gradient(135deg, rgba(52, 168, 83, 0.2), rgba(76, 215, 246, 0.2))'
                  : status === 'error'
                  ? 'linear-gradient(135deg, rgba(234, 67, 53, 0.2), rgba(251, 188, 5, 0.2))'
                  : 'linear-gradient(135deg, rgba(84, 36, 175, 0.2), rgba(76, 215, 246, 0.2))',
              border:
                status === 'success'
                  ? '1px solid rgba(52, 168, 83, 0.4)'
                  : status === 'error'
                  ? '1px solid rgba(234, 67, 53, 0.4)'
                  : '1px solid rgba(208, 188, 255, 0.3)',
            }}
          >
            {status === 'checking' && (
              <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#d0bcff' }}>
                sync
              </span>
            )}
            {status === 'success' && (
              <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#34A853' }}>
                verified
              </span>
            )}
            {status === 'error' && (
              <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#EA4335' }}>
                error
              </span>
            )}
          </div>
          <h1
            id="verify-title"
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: '#e3e1ed',
              letterSpacing: '-0.02em',
              margin: '0 0 8px',
            }}
          >
            {status === 'checking' && t('Đang xác minh tài khoản...', 'Verifying account...')}
            {status === 'success' && t('Kích hoạt tài khoản thành công!', 'Account Activated Successfully!')}
            {status === 'error' && t('Xác minh không thành công', 'Verification Failed')}
          </h1>
          <p style={{ fontSize: 14, color: '#cac4d0', lineHeight: 1.6, margin: 0 }}>
            {message}
          </p>
        </div>

        {status === 'success' && (
          <a
            href="/login?verified=1"
            className="account-button primary"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              height: 44,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #5424af 0%, #00d4ff 100%)',
              color: '#ffffff',
              fontWeight: 700,
              textDecoration: 'none',
              boxShadow: '0 4px 14px rgba(84,36,175,0.4)',
              transition: 'all 0.2s',
            }}
          >
            {t('Đăng nhập ngay', 'Sign in now')}
          </a>
        )}

        {status === 'error' && (
          <div style={{ display: 'flex', gap: 12 }}>
            <a
              href="/register"
              style={{
                flex: 1,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: 42,
                borderRadius: 10,
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: '#e3e1ed',
                fontSize: 13,
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              {t('Đăng ký lại', 'Register again')}
            </a>
            <a
              href="/login"
              style={{
                flex: 1,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: 42,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #5424af 0%, #00d4ff 100%)',
                color: '#ffffff',
                fontSize: 13,
                fontWeight: 700,
                textDecoration: 'none',
              }}
            >
              {t('Đăng nhập', 'Sign in')}
            </a>
          </div>
        )}
      </section>
    </main>
  );
}
