// Lucian UX/UI Prompt #056 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#056
import React, { useId, useLayoutEffect, useRef, useState, useEffect, useSyncExternalStore } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { usePremium } from '../PremiumContext.jsx';
import { auth, MOCK_AUTH } from '../auth.js';
import PaymentModal081 from './PaymentModal081.jsx';
import '../workspace.css';

const defaultPlans = [
  {
    id: 'plus',
    name: 'Plus',
    days: 30,
    boost: 2,
    price: 5,
    priceFormatted: '$5',
    priceVndFormatted: '130.000 VNĐ',
    icon: 'workspace_premium',
  },
  {
    id: 'prime',
    name: 'Prime',
    days: 365,
    boost: 3,
    price: 50,
    priceFormatted: '$50',
    priceVndFormatted: '1.250.000 VNĐ',
    icon: 'diamond',
  },
];

function RollingDays({ days, label }) {
  return (
    <span className="u056-od" role="img" aria-label={label}>
      {String(days)
        .padStart(3, ' ')
        .split('')
        .map((digit, k) =>
          digit === ' ' ? (
            <span className="u056-blank" key={k} aria-hidden="true" />
          ) : (
            <span
              className="u056-col"
              key={k}
              aria-hidden="true"
              style={{ '--d': Number(digit), '--k': k }}
            >
              {Array.from({ length: 10 }, (_, n) => (
                <span key={n}>{n}</span>
              ))}
            </span>
          )
        )}
    </span>
  );
}

export default function PremiumPage() {
  const { language } = usePreferences(),
    t = (vi, en) => (language === 'en' ? en : vi);
  const { subscription, refresh: refreshPremium } = usePremium();
  const session = useSyncExternalStore(auth.subscribe, auth.snapshot);
  const isAuthenticated = !MOCK_AUTH && session.status === 'authenticated' && !!session.user;

  const [plans, setPlans] = useState(defaultPlans);
  const [pricingReliable, setPricingReliable] = useState(false);
  const activeTier = subscription?.is_active ? subscription.tier : null;
  const [selected, setSelected] = useState(() => (activeTier === 'prime' ? 1 : 0));
  const [wiggle, setWiggle] = useState(false);
  const root = useRef(null);
  const group = useId();
  const plan = plans[selected] || defaultPlans[selected] || defaultPlans[0];
  const displayedTier = plan?.id || 'plus';

  useEffect(() => {
    if (subscription?.is_active && subscription?.tier === 'prime') {
      setSelected(1);
    }
  }, [subscription?.is_active, subscription?.tier]);

  const [vnpayConfigured, setVnpayConfigured] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notice, setNotice] = useState(null);

  // Check gateway configuration and authoritative server plan prices
  useEffect(() => {
    let mounted = true;
    auth
      .read('/premium/status')
      .then((res) => {
        if (mounted && res) {
          setVnpayConfigured(!!res.vnpay_configured);
          if (res.plans && Array.isArray(res.plans) && res.plans.length > 0) {
            setPricingReliable(true);
            setPlans((prev) =>
              prev.map((p) => {
                const sp = res.plans.find((item) => item.tier === p.id);
                if (!sp) return p;
                const vndFormatted =
                  sp.amount_vnd
                    ? `${Number(sp.amount_vnd).toLocaleString('vi-VN')} VNĐ`
                    : (sp.amount_vnd_formatted?.replace(' đ', ' VNĐ') || p.priceVndFormatted);
                return {
                  ...p,
                  days: sp.duration_days ?? p.days,
                  boost: sp.boost_multiplier ?? p.boost,
                  priceFormatted: sp.amount_usd_formatted ?? p.priceFormatted,
                  priceVndFormatted: vndFormatted,
                };
              })
            );
          }
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, session.user?.id]);

  // Handle bfcache restoration & browser back navigation cleanly
  useEffect(() => {
    const handleRestore = () => {
      setDialogOpen(false);
      refreshPremium?.();
      auth
        .read('/premium/status')
        .then((res) => {
          if (res?.plans && Array.isArray(res.plans) && res.plans.length > 0) {
            setPricingReliable(true);
            setPlans((prev) =>
              prev.map((p) => {
                const sp = res.plans.find((item) => item.tier === p.id);
                if (!sp) return p;
                const vndFormatted =
                  sp.amount_vnd
                    ? `${Number(sp.amount_vnd).toLocaleString('vi-VN')} VNĐ`
                    : (sp.amount_vnd_formatted?.replace(' đ', ' VNĐ') || p.priceVndFormatted);
                return {
                  ...p,
                  days: sp.duration_days ?? p.days,
                  boost: sp.boost_multiplier ?? p.boost,
                  priceFormatted: sp.amount_usd_formatted ?? p.priceFormatted,
                  priceVndFormatted: vndFormatted,
                };
              })
            );
          }
        })
        .catch(() => {});
    };
    window.addEventListener('pageshow', handleRestore);
    return () => {
      window.removeEventListener('pageshow', handleRestore);
    };
  }, [refreshPremium]);

  // Handle return callback from VNPAY (HTTP redirect query parameters)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    if (params.has('vnp_status')) {
      const status = params.get('vnp_status');
      const orderCode = params.get('order_code');

      if (status === 'success' && orderCode) {
        // Authoritative verification: Check order status and subscription from backend
        setNotice({
          type: 'info',
          text: t(
            'Đang xác nhận thanh toán... Xin vui lòng đợi trong giây lát.',
            'Payment is being confirmed... Please wait a moment.'
          ),
        });

        const verify = async (attempt = 1) => {
          try {
            const [order, statusRes] = await Promise.all([
              auth.read('/premium/orders/' + orderCode).catch(() => null),
              auth.read('/premium/status').catch(() => null),
            ]);
            await refreshPremium();

            const isSubActive = !!statusRes?.subscription?.is_active;
            const isOrderSuccess = order?.status === 'success';

            if (isOrderSuccess && isSubActive) {
              setNotice({
                type: 'success',
                text: t(
                  'Thanh toán VNPAY thành công! Gói hội viên đã được kích hoạt.',
                  'VNPAY payment successful! Membership activated.'
                ),
              });
            } else if (attempt < 3) {
              // Retry in case IPN arrives slightly after browser return
              setTimeout(() => verify(attempt + 1), 2000);
            } else {
              setNotice({
                type: 'info',
                text: t(
                  'Đang xác nhận thanh toán với cổng VNPAY. Gói sẽ tự động kích hoạt khi có thông báo IPN từ ngân hàng.',
                  'Payment is being confirmed with VNPAY. Membership will be activated as soon as IPN confirmation arrives.'
                ),
              });
            }
          } catch {
            setNotice({
              type: 'info',
              text: t(
                'Đang xác nhận thanh toán... Xin vui lòng kiểm tra lại sau giây lát.',
                'Payment is being confirmed... Please check back in a moment.'
              ),
            });
          }
        };

        verify();
      } else if (status === 'cancelled') {
        setNotice({
          type: 'error',
          text: t('Giao dịch VNPAY đã bị hủy.', 'VNPAY transaction was cancelled.'),
        });
      } else {
        const msg = params.get('message') || params.get('code') || 'error';
        setNotice({
          type: 'error',
          text: t(
            'Thanh toán VNPAY không thành công (' + msg + ').',
            'VNPAY payment failed (' + msg + ').'
          ),
        });
      }
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (params.has('vnp_ResponseCode')) {
      // In case user arrived directly with gateway query parameters, forward to backend return handler
      window.location.replace('/api/v1/premium/vnpay-return' + window.location.search);
    }
  }, [refreshPremium, language]);

  useLayoutEffect(() => {
    const element = root.current;
    if (!element) return;
    const place = () => {
      const option = element.querySelectorAll('.u056-sw button')[selected],
        card = element.querySelectorAll('.u056-p')[selected];
      const knob = element.querySelector('.u056-knob'),
        ring = element.querySelector('.u056-ring');
      if (!option || !card || !knob || !ring) return;
      knob.style.setProperty('--x', option.offsetLeft - 4 + 'px');
      knob.style.setProperty('--w', option.offsetWidth + 'px');
      ring.style.setProperty('--y', card.offsetTop + 'px');
      ring.style.setProperty('--h', card.offsetHeight + 'px');
    };
    place();
    const observer = new ResizeObserver(place);
    for (const target of [element, ...element.querySelectorAll('.u056-sw button,.u056-p')]) {
      observer.observe(target);
    }
    return () => observer.disconnect();
  }, [selected, language]);

  function select(index, focus = false) {
    setSelected(index);
    setWiggle(index === 1);
    if (focus && root.current) {
      root.current.querySelectorAll('.u056-sw button')[index].focus();
    }
  }

  function openDialog() {
    if (!isAuthenticated) {
      window.location.href = '/login?next=%2Fpremium';
      return;
    }
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
  }

  function handleCtaClick() {
    if (!isAuthenticated) {
      window.location.href = '/login?next=%2Fpremium';
      return;
    }
    if (!pricingReliable || isCurrentPlanActive) return;
    openDialog();
  }

  const features = [
    t(`×${plan.boost} bonus EXP cho Level`, `×${plan.boost} bonus Level EXP`),
    t(`${plan.days} ngày quyền lợi hội viên`, `${plan.days} days of membership benefits`),
    t('Hết hạn vẫn giữ EXP đã nhận', 'Keep earned EXP after expiry'),
    t('Không tự động gia hạn', 'No automatic renewal'),
  ];

  const isCurrentPlanActive = subscription?.is_active && subscription?.tier === plan.id;

  return (
    <main className="workspace-page premium-page">
      <div className="workspace-content premium-layout">
        <div className="premium-intro">
          <div className="premium-aura">
            <img
              src="/assets/brand/symbol-dark-2048.png"
              alt="AuraMeme"
              width="128"
              height="128"
            />
          </div>
          <h1>Aura Memberships</h1>
          <a className="premium-home" href="/">
            {t('← Quay về Trang chủ', '← Back to Home')}
          </a>
        </div>

        <section
          className={`premium-selector-panel premium-selector-panel--${displayedTier}`}
          aria-labelledby="premium-selector-title"
        >
          {/* Ambient smoke aura elements */}
          <div className={`premium-smoke-glow premium-smoke-glow--top premium-smoke-glow--${displayedTier}`} aria-hidden="true" />
          <div className={`premium-smoke-glow premium-smoke-glow--bottom premium-smoke-glow--${displayedTier}`} aria-hidden="true" />
          <div className={`premium-smoke-glow premium-smoke-glow--center premium-smoke-glow--${displayedTier}`} aria-hidden="true" />

          <div className="premium-selector-heading">
            <span className="workspace-kicker">
              {t('CHỌN DẤU ẤN CỦA BẠN', 'FIND YOUR AURA')}
            </span>
            <h2 id="premium-selector-title">
              {t('Khám phá hai gói Aura', 'Explore Aura memberships')}
            </h2>
            <p>
              {t(
                'Nâng tầm trải nghiệm với đặc quyền nhân hệ số EXP và nhận diện độc quyền.',
                'Elevate your journey with bonus EXP multipliers and exclusive tier identities.'
              )}
            </p>

            {notice && (
              <div
                className={`premium-notice-banner ${notice.type}`}
                role="status"
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  {notice.type === 'success' ? 'check_circle' : 'error'}
                </span>
                <span>{notice.text}</span>
              </div>
            )}

            {subscription?.is_active && (
              <div className="premium-active-banner" role="status">
                <span className="material-symbols-outlined" aria-hidden="true">
                  verified
                </span>
                <div>
                  <strong>
                    {t(
                      `Gói đang kích hoạt: Aura ${subscription.tier.toUpperCase()}`,
                      `Active plan: Aura ${subscription.tier.toUpperCase()}`
                    )}
                  </strong>
                  <span className="premium-active-days">
                    {' · '}
                    {t(
                      `Còn ${subscription.days_remaining} ngày`,
                      `${subscription.days_remaining} days remaining`
                    )}
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="ux u056" ref={root}>
            <div
              className="u056-sw"
              role="radiogroup"
              aria-label={t('Thời hạn gói', 'Membership duration')}
            >
              <span className="u056-knob" aria-hidden="true" />
              {plans.map((item, i) => (
                <button
                  type="button"
                  key={item.name}
                  role="radio"
                  aria-checked={selected === i}
                  tabIndex={selected === i ? 0 : -1}
                  onClick={() => select(i)}
                  onKeyDown={(e) => {
                    if (
                      [
                        'ArrowRight',
                        'ArrowLeft',
                        'ArrowDown',
                        'ArrowUp',
                        'Home',
                        'End',
                      ].includes(e.key)
                    ) {
                      e.preventDefault();
                      select(
                        e.key === 'Home'
                          ? 0
                          : e.key === 'End'
                          ? 1
                          : 1 - selected,
                        true
                      );
                    }
                  }}
                >
                  {item.days} {t('ngày', 'days')}
                </button>
              ))}
            </div>

            <fieldset className="u056-plans">
              <legend className="workspace-sr">
                {t('Hai gói dự kiến', 'Planned memberships')}
              </legend>
              <span className="u056-ring" aria-hidden="true" />
              {plans.map((item, i) => (
                <label
                  className={
                    'u056-p premium-plan premium-' + item.name.toLowerCase()
                  }
                  key={item.name}
                >
                  <input
                    type="radio"
                    name={group}
                    aria-label={'Aura ' + item.name}
                    checked={selected === i}
                    onChange={() => select(i)}
                  />
                  <span className="u056-dot" aria-hidden="true" />
                  <span className="u056-nm">
                    <b>
                      Aura {item.name} · {language === 'en' ? item.priceFormatted : item.priceVndFormatted}
                      {i === 0 && (
                        <em className="u056-badge-exp u056-badge-exp--plus">
                          ×2 EXP
                        </em>
                      )}
                      {i === 1 && (
                        <em
                          className={`u056-badge-exp u056-badge-exp--prime ${wiggle ? 'wig' : ''}`}
                          onAnimationEnd={() => setWiggle(false)}
                        >
                          ×3 EXP
                        </em>
                      )}
                    </b>
                    <small>
                      {item.days} {t('ngày', 'days')} · ×{item.boost}{' '}
                      {t('bonus EXP cho Level', 'bonus Level EXP')}
                    </small>
                  </span>
                  <span
                    className="material-symbols-outlined u056-plan-icon"
                    aria-hidden="true"
                  >
                    {item.icon}
                  </span>
                </label>
              ))}
            </fieldset>

            <div className="u056-current">
              <div>
                <span className="u056-current-label">
                  {t('THỜI HẠN GÓI', 'MEMBERSHIP DURATION')}
                </span>
                <div className="u056-duration">
                  <RollingDays
                    days={plan.days}
                    label={plan.days + ' ' + t('ngày', 'days')}
                  />
                  <span>{t('ngày', 'days')}</span>
                </div>
              </div>
              <span className="u056-badge">
                {language === 'en' ? plan.priceFormatted : plan.priceVndFormatted}
              </span>
            </div>

            <ul className="u056-feat" aria-live="polite" aria-atomic="true">
              {features.map((feature, i) => (
                <li key={selected + '-' + i} style={{ '--i': i }}>
                  <svg viewBox="0 0 18 18" aria-hidden="true">
                    <path d="M4 9.4l3.2 3.2L14 5.6" />
                  </svg>
                  {feature}
                </li>
              ))}
            </ul>

            <button
              className={`u056-cta u056-cta--${plan.id}`}
              type="button"
              disabled={isAuthenticated && (!pricingReliable || isCurrentPlanActive)}
              onClick={handleCtaClick}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                {!isAuthenticated
                  ? 'login'
                  : isCurrentPlanActive
                  ? 'verified'
                  : 'shopping_cart'}
              </span>
              {!isAuthenticated
                ? t('Đăng nhập để mua gói', 'Sign in to purchase')
                : isCurrentPlanActive
                ? t(
                    `Gói đang kích hoạt (${subscription.days_remaining} ngày)`,
                    `Active Plan (${subscription.days_remaining} days left)`
                  )
                : !pricingReliable
                ? t('Đang tải bảng giá...', 'Loading pricing...')
                : plan.id === 'plus'
                ? t('Mua gói Plus', 'Buy Aura Plus')
                : t('Mua gói Prime', 'Buy Aura Prime')}
            </button>

            <p className="u056-price-note">
              {t('Không tự động gia hạn.', 'No automatic renewal.')}
            </p>

            <div style={{ textAlign: 'center', marginTop: '12px' }}>
              <a
                href="/premium/history"
                className="premium-history-link"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12.5px',
                  color: 'var(--ux-accent, #38bdf8)',
                  textDecoration: 'none',
                  fontWeight: 600,
                  padding: '6px 12px',
                  borderRadius: '8px',
                  transition: 'opacity 0.2s',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '16px' }} aria-hidden="true">
                  receipt_long
                </span>
                {t('Xem lịch sử thanh toán & biên lai', 'View payment history & receipts')}
              </a>
            </div>
          </div>
        </section>
      </div>

      {/* Lucian UX/UI Prompt #081 Order Confirmation Modal */}
      <PaymentModal081
        plan={plan}
        isOpen={dialogOpen}
        onClose={closeDialog}
        language={language}
      />
    </main>
  );
}
