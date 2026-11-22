/**
 * AuraMeme Cookie Consent — Adapted from Lucian UX/UI Prompt #225 ("Cookie consent with a bite")
 * Source: https://lucianlabs.dev/uxui-prompt/#225
 * License: MIT
 */
import React, { useEffect, useState } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { readCookieConsent, saveCookieConsent } from '../cookie-consent.js';

function CookieIcon({ bitten }) {
  return (
    <div className={`am-cookie-art${bitten ? ' am-cookie-art--bitten' : ''}`} aria-hidden="true">
      <svg className="am-cookie-svg" viewBox="0 0 40 40" fill="none">
        {bitten ? (
          <path
            d="M20 4C11.16 4 4 11.16 4 20s7.16 16 16 16 16-7.16 16-16c0-1.2-.13-2.36-.38-3.48a4.8 4.8 0 0 1-5.8-4.72 4.8 4.8 0 0 1-5.4-5.4A16.1 16.1 0 0 0 20 4Z"
            fill="#d99b4e"
            stroke="#f5c982"
            strokeWidth="1.5"
          />
        ) : (
          <circle cx="20" cy="20" r="16" fill="#d99b4e" stroke="#f5c982" strokeWidth="1.5" />
        )}
        <circle cx="14" cy="14" r="2.2" fill="#4e2e14" />
        <circle cx="23" cy="22" r="2.4" fill="#4e2e14" />
        <circle cx="15" cy="25" r="2" fill="#4e2e14" />
        <circle cx="27" cy="28" r="1.7" fill="#4e2e14" />
        {!bitten && <circle cx="26" cy="13" r="1.9" fill="#4e2e14" />}
      </svg>
      <span className="am-cookie-crumb am-cookie-crumb--1" />
      <span className="am-cookie-crumb am-cookie-crumb--2" />
      <span className="am-cookie-crumb am-cookie-crumb--3" />
    </div>
  );
}

export default function CookieConsent() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [saved, setSaved] = useState(() => readCookieConsent());
  const [open, setOpen] = useState(() => readCookieConsent() === null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [optionalPref, setOptionalPref] = useState(() => Boolean(readCookieConsent()?.optional));
  const [bitten, setBitten] = useState(false);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (ev) => {
      if (ev.key === 'Escape' && saved) {
        setOpen(false);
        setSettingsOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, saved]);

  function commitChoice(optionalValue) {
    const next = saveCookieConsent({ optional: optionalValue });
    setSaved(next);
    setOptionalPref(next.optional);
    setBitten(true);
    const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setOpen(false);
      setSettingsOpen(false);
      setBitten(false);
      return;
    }
    setTimeout(() => setExiting(true), 240);
    setTimeout(() => {
      setOpen(false);
      setExiting(false);
      setSettingsOpen(false);
      setBitten(false);
    }, 520);
  }

  if (!open) {
    return (
      <button
        type="button"
        className="am-cookie-reopen"
        onClick={() => {
          setOptionalPref(Boolean(saved?.optional));
          setOpen(true);
        }}
        title={t('Cài đặt Cookie', 'Cookie settings')}
        aria-label={t('Mở cài đặt Cookie', 'Open cookie settings')}
        data-cookie-reopen="1"
      >
        <svg width="22" height="22" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <path
            d="M20 4C11.16 4 4 11.16 4 20s7.16 16 16 16 16-7.16 16-16c0-1.2-.13-2.36-.38-3.48a4.8 4.8 0 0 1-5.8-4.72 4.8 4.8 0 0 1-5.4-5.4A16.1 16.1 0 0 0 20 4Z"
            fill="#d99b4e"
            stroke="#f5c982"
            strokeWidth="1.5"
          />
          <circle cx="14" cy="14" r="2.2" fill="#4e2e14" />
          <circle cx="23" cy="22" r="2.4" fill="#4e2e14" />
          <circle cx="15" cy="25" r="2" fill="#4e2e14" />
        </svg>
      </button>
    );
  }

  return (
    <aside
      className={`am-cookie-banner${exiting ? ' am-cookie-banner--exiting' : ''}`}
      role="region"
      aria-label={t('Tùy chọn Cookie', 'Cookie preferences')}
      data-cookie-banner="1"
    >
      <div className="am-cookie-header">
        <CookieIcon bitten={bitten} />
        <div className="am-cookie-copy">
          <h2 className="am-cookie-title">{t('Cookie & quyền riêng tư', 'Cookies & privacy')}</h2>
          <p className="am-cookie-desc">
            {t(
              'AuraMeme sử dụng cookie thiết yếu cho phiên đăng nhập và bảo mật CSRF. Hiện tại website không kích hoạt tracker quảng cáo bên thứ ba. ',
              'AuraMeme uses essential cookies for sign-in sessions and CSRF security. No third-party ad trackers are currently active. ',
            )}
            <a className="am-cookie-link" href="/privacy.html#cookies">
              {t('Chính sách bảo mật', 'Privacy policy')}
            </a>
          </p>
        </div>
      </div>

      <div className="am-cookie-settings" hidden={!settingsOpen} data-cookie-settings="1">
        <div className="am-cookie-row">
          <div className="am-cookie-row-info">
            <div className="am-cookie-row-title">{t('Cookie thiết yếu (Luôn bật)', 'Essential cookies (Always on)')}</div>
            <div className="am-cookie-row-note">
              {t(
                'Duy trì phiên đăng nhập HttpOnly, bảo vệ CSRF và lưu giao diện Sáng/Tối, ngôn ngữ VI/EN.',
                'Keeps HttpOnly sign-in sessions, CSRF protection, and Light/Dark + VI/EN preferences.',
              )}
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked="true"
            disabled
            className="am-cookie-switch"
            aria-label={t('Cookie thiết yếu luôn bật', 'Essential cookies always enabled')}
          >
            <span className="am-cookie-switch-thumb" />
          </button>
        </div>

        <div className="am-cookie-row">
          <div className="am-cookie-row-info">
            <div className="am-cookie-row-title">{t('Phân tích & tiếp thị (Không sử dụng)', 'Analytics & marketing (Not in use)')}</div>
            <div className="am-cookie-row-note">
              {t(
                'AuraMeme hiện chưa tích hợp Google Analytics hay pixel quảng cáo. Lựa chọn của bạn được lưu để bảo vệ quyền riêng tư về sau.',
                'AuraMeme does not load analytics or ad pixels. Your choice is saved for future optional features.',
              )}
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={optionalPref}
            className="am-cookie-switch"
            onClick={() => setOptionalPref((v) => !v)}
            aria-label={t('Bật/tắt cookie tùy chọn', 'Toggle optional cookies')}
            data-cookie-optional-switch="1"
          >
            <span className="am-cookie-switch-thumb" />
          </button>
        </div>
      </div>

      <div className="am-cookie-actions">
        <button
          type="button"
          className="am-cookie-btn am-cookie-btn--ghost"
          aria-expanded={settingsOpen}
          onClick={() => setSettingsOpen((v) => !v)}
          data-cookie-toggle-settings="1"
        >
          {t('Cài đặt', 'Settings')}
        </button>
        <button
          type="button"
          className="am-cookie-btn"
          onClick={() => commitChoice(false)}
          data-cookie-reject="1"
        >
          {t('Từ chối', 'Reject')}
        </button>
        {settingsOpen ? (
          <button
            type="button"
            className="am-cookie-btn am-cookie-btn--primary"
            onClick={() => commitChoice(optionalPref)}
            data-cookie-save="1"
          >
            {t('Lưu lựa chọn', 'Save choices')}
          </button>
        ) : (
          <button
            type="button"
            className="am-cookie-btn am-cookie-btn--primary"
            onClick={() => commitChoice(true)}
            data-cookie-accept="1"
          >
            {t('Chấp nhận', 'Accept')}
          </button>
        )}
      </div>
    </aside>
  );
}
