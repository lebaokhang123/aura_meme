/**
 * Lucian UX/UI Prompt #409 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#409
 * Ported for AuraMeme (Task 8 Polish).
 */
import React, { useEffect, useRef, useState } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { readCookieConsent, saveCookieConsent } from '../cookie-consent.js';

const DOUGH = 'M32 5C40 4.6 47.5 8 52.6 13.6C57.8 19.3 60 26 59.4 33.2C58.8 41 55.6 47.6 49.6 52.8C44 57.6 37.6 59.6 30.6 59.2C23 58.8 16.4 55.6 11.6 49.8C6.8 44 4.8 37.4 5.2 30.4C5.6 23.4 8.6 16.8 13.8 11.8C19 6.9 25.2 5.3 32 5Z';
const CHIPS = [
  'M19.5 19.8c1.6-1.4 4.4-1.2 5.6.5 1.1 1.6.6 4-1 5.1-1.7 1.1-4.3.8-5.3-.9-.9-1.5-.6-3.4.7-4.7z',
  'M37.6 15.4c1.2-.9 3.2-.8 4.1.4 1 1.3.5 3.2-.9 3.9-1.3.7-3.1.4-3.8-.8-.6-1.1-.4-2.6.6-3.5z',
  'M41.4 33.6c1.9-1.3 4.7-.7 5.5 1.3.8 1.9-.3 4.1-2.3 4.6-1.8.5-3.9-.4-4.4-2.1-.4-1.4.1-2.9 1.2-3.8z',
  'M24.2 37.9c1.4-1.5 4-1.6 5.3-.2 1.3 1.4 1 3.8-.6 4.8-1.6 1-4 .6-4.9-.9-.7-1.2-.6-2.7.2-3.7z',
  'M12.3 30.2c.9-.9 2.6-.9 3.4.1.8 1 .5 2.6-.6 3.2-1.1.6-2.6.3-3.1-.7-.4-.8-.3-1.9.3-2.6z',
  'M33 49.4c1-.8 2.7-.6 3.4.5.6 1-.1 2.5-1.2 2.9-1.1.4-2.5-.2-2.8-1.2-.2-.8.1-1.6.6-2.2z',
  'M49.2 24.1c.7-.6 1.9-.5 2.4.3.5.8.1 1.9-.8 2.2-.8.3-1.8-.1-2-.9-.1-.6.1-1.2.4-1.6z',
  'M31.2 26.6c.9-.7 2.3-.6 2.9.3.6.9.2 2.2-.8 2.6-.9.4-2.2.1-2.6-.8-.3-.7-.1-1.6.5-2.1z'
];
const BITE = [[55, 9, 10], [60.5, 21, 7.2], [45.5, 3, 7]];
const SPECKS = [
  [16, 18], [27, 13], [46, 22], [21, 47], [44, 46],
  [37, 39], [14, 40], [50, 40], [28, 32], [39, 9]
];
const CR = [
  [64, 13, 10, 18, 118, 230],
  [73, 23, 8, 34, 104, -180],
  [58, 6, 9, -10, 128, 260],
  [79, 31, 7, 42, 92, -140],
  [68, 10, 8, 6, 136, 200],
  [56, 19, 7, -22, 112, -230]
];

function CookieGraphic({ id }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <radialGradient id={`${id}d`} cx="38%" cy="32%" r="72%">
          <stop offset="0" stopColor="#F5CF8E" />
          <stop offset=".55" stopColor="#E2A95E" />
          <stop offset="1" stopColor="#BC7A3A" />
        </radialGradient>
        <radialGradient id={`${id}h`} cx="34%" cy="28%" r="40%">
          <stop offset="0" stopColor="#FFF6E0" stopOpacity=".55" />
          <stop offset="1" stopColor="#FFF6E0" stopOpacity="0" />
        </radialGradient>
        <mask id={`${id}m`} maskUnits="userSpaceOnUse" x="-10" y="-10" width="84" height="84">
          <rect x="-10" y="-10" width="84" height="84" fill="#fff" />
          <g className="bt">
            {BITE.map(([cx, cy, r], i) => (
              <circle key={i} cx={cx} cy={cy} r={r} fill="#000" />
            ))}
          </g>
        </mask>
        <clipPath id={`${id}c`}>
          <path d={DOUGH} />
        </clipPath>
      </defs>
      <g mask={`url(#${id}m)`}>
        <path d={DOUGH} fill={`url(#${id}d)`} />
        <g clipPath={`url(#${id}c)`}>
          <path d={DOUGH} fill="none" stroke="#9E5E26" strokeOpacity=".35" strokeWidth="3" />
          <path
            d="M16.5 27.6l2-.9 1.6.5 1.9-.8M35.6 21.4l1.5 1.2.4 1.7M28.4 46.4l1.8-.5 1.3.8 1.7-.4M47.6 30.4l-.5 1.8.6 1.6"
            fill="none"
            stroke="#A9682F"
            strokeOpacity=".45"
            strokeWidth=".8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {SPECKS.map(([cx, cy], k) => (
            <circle key={k} cx={cx} cy={cy} r={k % 3 ? 0.55 : 0.8} fill="#A8642C" opacity=".45" />
          ))}
          <ellipse cx="25" cy="20" rx="17" ry="13" fill={`url(#${id}h)`} />
          {CHIPS.map((d, i) => (
            <path key={`chip-${i}`} d={d} fill="#4A2817" />
          ))}
          {CHIPS.map((d, i) => {
            const m = d.match(/^M([\d.]+) ([\d.]+)/);
            if (!m) return null;
            return (
              <ellipse
                key={`hi-${i}`}
                cx={+m[1] + 1.6}
                cy={+m[2] - 0.1}
                rx="1.2"
                ry=".7"
                fill="#8A5634"
                opacity=".75"
              />
            );
          })}
          <g className="ed">
            {BITE.map(([cx, cy, r], i) => (
              <circle key={`ed-${i}`} cx={cx} cy={cy} r={r} fill="none" stroke="#F8DDA6" strokeWidth="2.4" />
            ))}
          </g>
        </g>
      </g>
    </svg>
  );
}

export default function CookieConsent() {
  const { language } = usePreferences();
  const isEn = language === 'en';
  const t = (vi, en) => (isEn ? en : vi);

  const [saved, setSaved] = useState(() => readCookieConsent());
  const [open, setOpen] = useState(() => readCookieConsent() === null);
  const [stateClass, setStateClass] = useState(''); // 'is-bite is-pill', 'is-tiny is-dot', etc.
  const [flyTuckClass, setFlyTuckClass] = useState(''); // 'is-fly', 'is-tuck'
  const [isIn, setIsIn] = useState(true);
  const [ckStyle, setCkStyle] = useState({});
  const [cardStyle, setCardStyle] = useState({});
  const [busy, setBusy] = useState(false);
  const crumbRefs = useRef([]);
  const cardRef = useRef(null);
  const pillSpanRef = useRef(null);

  const uid = useRef(`u409_${Math.random().toString(36).slice(2, 7)}`).current;

  function dropCrumbs() {
    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (rm) return;
    crumbRefs.current.forEach((el, k) => {
      if (!el || !el.animate) return;
      const p = CR[k];
      el.animate(
        [
          { opacity: 1, transform: 'translate(0,0) rotate(0deg)', easing: 'cubic-bezier(.2,.6,.4,1)' },
          {
            opacity: 1,
            transform: `translate(${p[3] * 0.25}px,-7px) rotate(${p[5] * 0.2}deg)`,
            offset: 0.18,
            easing: 'cubic-bezier(.45,0,.85,.55)',
          },
          { opacity: 1, offset: 0.86 },
          { opacity: 0, transform: `translate(${p[3]}px,${p[4]}px) rotate(${p[5]}deg)` },
        ],
        { duration: 1020 + k * 40, delay: 15 + k * 25, fill: 'both' }
      );
    });
  }

  function handleAllow() {
    if (busy) return;
    setBusy(true);
    setIsIn(false);
    setStateClass('is-bite');
    dropCrumbs();

    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Shrink into pill
    setTimeout(() => {
      const pillWidth = pillSpanRef.current ? Math.round(pillSpanRef.current.offsetWidth + 64) : 120;
      setStateClass('is-bite is-pill');
      setCardStyle({
        '--w': `${pillWidth}px`,
        height: '40px',
        padding: '0',
      });
      setCkStyle({
        '--tx': `${-pillWidth / 2 + 24}px`,
        '--ty': '20px',
        '--sc': '0.24',
        '--rt': '-10deg',
      });
    }, rm ? 100 : 900);

    // Float away
    setTimeout(() => {
      setFlyTuckClass('is-fly');
    }, rm ? 300 : 1900);

    // Commit & close
    setTimeout(() => {
      const rec = saveCookieConsent({ optional: false });
      setSaved(rec);
      setOpen(false);
      setBusy(false);
      setStateClass('');
      setFlyTuckClass('');
      setCardStyle({});
      setCkStyle({});
    }, rm ? 500 : 2550);
  }

  function handleEssential() {
    if (busy) return;
    setBusy(true);
    setIsIn(false);
    setStateClass('is-tiny');
    setCkStyle({
      '--tx': '0px',
      '--ty': '0px',
      '--sc': '0.2',
      '--rt': '-30deg',
    });

    const rm = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Shrink into dot
    setTimeout(() => {
      setStateClass('is-tiny is-dot');
      setCardStyle({
        '--w': '40px',
        height: '40px',
        padding: '0',
      });
      setCkStyle({
        '--tx': '0px',
        '--ty': '20px',
        '--sc': '0.2',
        '--rt': '-30deg',
      });
    }, rm ? 100 : 500);

    // Tuck down
    setTimeout(() => {
      setFlyTuckClass('is-tuck');
    }, rm ? 250 : 1100);

    // Commit & close
    setTimeout(() => {
      const rec = saveCookieConsent({ optional: false });
      setSaved(rec);
      setOpen(false);
      setBusy(false);
      setStateClass('');
      setFlyTuckClass('');
      setCardStyle({});
      setCkStyle({});
    }, rm ? 450 : 1700);
  }

  function handleReopen() {
    setStateClass('');
    setFlyTuckClass('');
    setCardStyle({});
    setCkStyle({});
    setIsIn(true);
    setOpen(true);
  }

  if (!open) {
    return (
      <button
        type="button"
        className="am-cookie-reopen"
        onClick={handleReopen}
        title={t('Cài đặt Cookie', 'Cookie settings')}
        aria-label={t('Mở tùy chọn Cookie', 'Open cookie options')}
        data-cookie-reopen="1"
      >
        <svg width="24" height="24" viewBox="0 0 64 64" fill="none" aria-hidden="true">
          <path d={DOUGH} fill="#E2A95E" />
          <circle cx="20" cy="20" r="3" fill="#4A2817" />
          <circle cx="38" cy="22" r="3" fill="#4A2817" />
          <circle cx="28" cy="38" r="3.2" fill="#4A2817" />
          <circle cx="42" cy="40" r="2.5" fill="#4A2817" />
        </svg>
      </button>
    );
  }

  return (
    <div className="am-cookie-root">
      <div className={`ux u409 ${stateClass}`} data-cookie-banner="1">
        <div className={`u409-wrap ${isIn ? 'is-in' : ''} ${flyTuckClass}`}>
          <section className="u409-card" ref={cardRef} style={cardStyle} aria-label="Cookie consent">
            <div className="u409-main" inert={busy || undefined}>
              <b className="u409-t">{t('Cho phép AuraMeme dùng Cookie?', 'Mind if we use cookies?')}</b>
              <span className="u409-s">
                {t(
                  'Chúng tôi chỉ dùng cookie cần thiết cho đăng nhập và bảo mật.',
                  'We use essential cookies for sign-in and security.'
                )}
                <a href="/privacy.html#cookies" className="u409-link">
                  {t('Chính sách bảo mật', 'Privacy policy')}
                </a>
              </span>
              <div className="u409-act">
                <button
                  type="button"
                  className="u409-ess"
                  onClick={handleEssential}
                  data-cookie-ess="1"
                  disabled={busy}
                >
                  {t('Chỉ thiết yếu', 'Essential only')}
                </button>
                <button
                  type="button"
                  className="u409-ok"
                  onClick={handleAllow}
                  data-cookie-ok="1"
                  disabled={busy}
                >
                  {t('Đã hiểu', 'Got it')}
                </button>
              </div>
            </div>
            <div className="u409-pill" aria-hidden="true">
              <span ref={pillSpanRef}>{t('Cảm ơn', 'Thanks')}</span>
            </div>
          </section>

          <span className="u409-ck" style={ckStyle} aria-hidden="true">
            <CookieGraphic id={uid} />
          </span>

          <span className="u409-crs" aria-hidden="true">
            {CR.map(([left, top, size], k) => (
              <i
                key={k}
                ref={(el) => {
                  crumbRefs.current[k] = el;
                }}
                className="u409-cr"
                style={{ left: `${left}px`, top: `${top}px`, '--s': `${size}px` }}
              >
                <svg viewBox="0 0 8 8">
                  <path d="M1 3.1 3.1.9l3 .7 1.1 2.9-2.4 2.6L1.3 6z" fill="#DFA45B" />
                  <path d="M4.8 7.1 7.2 4.5l-1.1-2.9-1.9 2.6z" fill="#B87436" opacity=".75" />
                  <path d="M2.6 2.4h1.6" stroke="#F8DDA6" strokeWidth=".7" strokeLinecap="round" />
                </svg>
              </i>
            ))}
          </span>
        </div>
        <p className="u409-live" aria-live="polite">
          {busy ? t('Đã ghi nhận tùy chọn', 'Preferences saved') : ''}
        </p>
      </div>
    </div>
  );
}
