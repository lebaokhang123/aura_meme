// Lucian UX/UI Prompt #056 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#056
import React, { useId, useLayoutEffect, useRef, useState, useEffect, useSyncExternalStore } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { auth, MOCK_AUTH } from '../auth.js';
import '../workspace.css';

const plans = [
  {
    id: 'plus',
    name: 'Plus',
    days: 30,
    boost: 2,
    price: 5,
    priceFormatted: '$5',
    priceVndFormatted: '125.000 đ',
    icon: 'auto_awesome',
  },
  {
    id: 'prime',
    name: 'Prime',
    days: 365,
    boost: 3,
    price: 50,
    priceFormatted: '$50',
    priceVndFormatted: '1.250.000 đ',
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
  const session = useSyncExternalStore(auth.subscribe, auth.snapshot);
  const isAuthenticated = !MOCK_AUTH && session.status === 'authenticated' && !!session.user;

  const [selected, setSelected] = useState(0);
  const [wiggle, setWiggle] = useState(false);
  const root = useRef(null);
  const dialogRef = useRef(null);
  const group = useId();
  const plan = plans[selected];

  const [subscription, setSubscription] = useState(null);
  const [vnpayConfigured, setVnpayConfigured] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);
  const [notice, setNotice] = useState(null);

  // Fetch active subscription & gateway config
  useEffect(() => {
    let mounted = true;
    if (isAuthenticated) {
      auth
        .read('/premium/status')
        .then((res) => {
          if (mounted && res) {
            setSubscription(res.subscription || null);
            setVnpayConfigured(!!res.vnpay_configured);
          }
        })
        .catch(() => {
          // Gracefully fallback if network or mock
        });
    } else {
      setSubscription(null);
    }
    return () => {
      mounted = false;
    };
  }, [isAuthenticated, session.user?.id, refreshCount]);

  // Handle return callback from VNPAY if query parameters are present
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    if (params.has('vnp_ResponseCode') || params.has('vnp_SecureHash')) {
      const qs = window.location.search;
      auth
        .read('/premium/vnpay-return' + qs)
        .then((res) => {
          if (res?.status === 'paid') {
            if (res.subscription) setSubscription(res.subscription);
            setNotice({
              type: 'success',
              text: t(
                'Thanh toán VNPAY thành công! Gói hội viên đã được kích hoạt.',
                'VNPAY payment successful! Membership activated.'
              ),
            });
            setRefreshCount((c) => c + 1);
          } else {
            setNotice({
              type: 'error',
              text: t(
                'Thanh toán VNPAY không thành công (mã: ' +
                  (res?.response_code || 'error') +
                  ').',
                'VNPAY payment failed (code: ' +
                  (res?.response_code || 'error') +
                  ').'
              ),
            });
          }
          window.history.replaceState({}, document.title, window.location.pathname);
        })
        .catch(() => {
          setNotice({
            type: 'error',
            text: t(
              'Lỗi kiểm tra phản hồi từ cổng VNPAY.',
              'Error verifying response from VNPAY gateway.'
            ),
          });
          window.history.replaceState({}, document.title, window.location.pathname);
        });
    }
  }, []);

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
    setActionMessage(null);
    setDialogOpen(true);
    dialogRef.current?.showModal();
  }

  function closeDialog() {
    if (busy) return;
    dialogRef.current?.close();
    setDialogOpen(false);
    setActionMessage(null);
  }

  async function handleSimulatePayment(action) {
    setBusy(true);
    setActionMessage(null);
    try {
      const orderRes = await auth.write('POST', '/premium/orders', {
        plan_type: plan.id,
        provider: 'sandbox_simulated',
      });
      if (!orderRes?.order_code) {
        throw new Error(t('Không thể tạo đơn hàng thử nghiệm.', 'Could not create test order.'));
      }
      const simRes = await auth.write(
        'POST',
        `/premium/orders/${orderRes.order_code}/simulate`,
        { action }
      );
      if (action === 'pay_success') {
        if (simRes?.subscription) {
          setSubscription(simRes.subscription);
        }
        setActionMessage({
          type: 'success',
          text: t(
            `Kích hoạt thành công gói Aura ${plan.name}! Còn ${
              simRes?.subscription?.days_remaining || plan.days
            } ngày sử dụng.`,
            `Successfully activated Aura ${plan.name}! Duration: ${
              simRes?.subscription?.days_remaining || plan.days
            } days remaining.`
          ),
        });
        setRefreshCount((c) => c + 1);
      } else {
        setActionMessage({
          type: 'error',
          text: t(
            'Mô phỏng thanh toán thất bại / hủy đơn thành công.',
            'Simulated payment failure / order cancellation successfully.'
          ),
        });
      }
    } catch (err) {
      setActionMessage({
        type: 'error',
        text:
          err.message ||
          t(
            'Đã xảy ra lỗi trong quá trình thử nghiệm.',
            'An error occurred during sandbox test.'
          ),
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleVnpayCheckout() {
    if (!vnpayConfigured) return;
    setBusy(true);
    setActionMessage(null);
    try {
      const orderRes = await auth.write('POST', '/premium/orders', {
        plan_type: plan.id,
        provider: 'vnpay',
      });
      if (orderRes?.payment_url) {
        window.location.href = orderRes.payment_url;
      } else {
        throw new Error(
          t('Không nhận được đường dẫn thanh toán VNPAY.', 'No VNPAY payment URL received.')
        );
      }
    } catch (err) {
      setActionMessage({
        type: 'error',
        text:
          err.message ||
          t('Không thể khởi tạo cổng VNPAY.', 'Could not initialize VNPAY gateway.'),
      });
    } finally {
      setBusy(false);
    }
  }

  function handleCtaClick() {
    if (!isAuthenticated) {
      window.location.href = '/login?next=%2Fpremium';
      return;
    }
    openDialog();
  }

  const features = [
    t(`×${plan.boost} bonus XP cho Level`, `×${plan.boost} bonus XP for Level`),
    t(`${plan.days} ngày quyền lợi hội viên`, `${plan.days} days of membership benefits`),
    t('Hết hạn vẫn giữ XP đã nhận', 'Keep earned XP after expiry'),
    t('Không tự động gia hạn', 'No automatic renewal'),
  ];

  const isCurrentPlanActive = subscription?.active && subscription?.tier === plan.id;

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
          className="premium-selector-panel"
          aria-labelledby="premium-selector-title"
        >
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

            {subscription?.active && (
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
                      Aura {item.name} · {language === 'en' ? item.priceFormatted : `${item.priceVndFormatted} (${item.priceFormatted})`}
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
                      {t('bonus XP cho Level', 'bonus Level XP')}
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
              <span className="u056-badge">{language === 'en' ? plan.priceFormatted : `${plan.priceVndFormatted} (${plan.priceFormatted})`}</span>
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
              className="u056-cta"
              type="button"
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
                : t(
                    `Mua gói ${plan.name} (${plan.priceFormatted})`,
                    `Buy Aura ${plan.name} (${plan.priceFormatted})`
                  )}
            </button>

            <p className="u056-price-note">
              {t(
                'Giá niêm yết: $5/30 ngày và $50/365 ngày. Không tự động gia hạn.',
                'Listed prices: $5/30 days and $50/365 days. No recurring charges.'
              )}
            </p>
          </div>
        </section>
      </div>

      <dialog
        ref={dialogRef}
        className="workspace-dialog premium-sandbox-dialog"
        aria-labelledby="sandbox-dialog-title"
        onCancel={closeDialog}
        onClose={closeDialog}
      >
        {dialogOpen && (
          <div className="sandbox-dialog-content">
            <div className="workspace-panel-heading">
              <h2 id="sandbox-dialog-title">
                {t(
                  `Xác nhận đơn hàng — Gói Aura ${plan.name}`,
                  `Order Confirmation — Aura ${plan.name}`
                )}
              </h2>
              <button
                type="button"
                aria-label={t('Đóng', 'Close')}
                disabled={busy}
                onClick={closeDialog}
              >
                ×
              </button>
            </div>

            <div className="sandbox-summary-card">
              <div className="sandbox-summary-row">
                <span>{t('Gói hội viên', 'Membership Plan')}:</span>
                <strong>Aura {plan.name}</strong>
              </div>
              <div className="sandbox-summary-row">
                <span>{t('Giá niêm yết (USD)', 'Listed Price (USD)')}:</span>
                <strong className="sandbox-price-usd">
                  {plan.priceFormatted} USD
                </strong>
              </div>
              <div className="sandbox-summary-row">
                <span>{t('Giá quy đổi VNPAY (VND)', 'VNPAY Equivalent (VND)')}:</span>
                <span>{plan.priceVndFormatted}</span>
              </div>
              <div className="sandbox-summary-row">
                <span>{t('Thời hạn sử dụng', 'Duration')}:</span>
                <span>
                  {plan.days} {t('ngày', 'days')}
                </span>
              </div>
              <div className="sandbox-summary-row">
                <span>{t('Quyền lợi bonus', 'Bonus benefit')}:</span>
                <span className="sandbox-bonus-tag">×{plan.boost} Level XP</span>
              </div>
            </div>

            <div className="sandbox-note-box">
              <span className="material-symbols-outlined" aria-hidden="true">
                info
              </span>
              <div>
                <strong>
                  {t(
                    'Môi trường thử nghiệm — Không phát sinh thanh toán thật.',
                    'Sandbox Environment — No real charges applied.'
                  )}
                </strong>
                <p>
                  {t(
                    'Hệ thống thử nghiệm phục vụ đồ án & portfolio. Không yêu cầu thông tin thẻ tín dụng.',
                    'Portfolio demo sandbox. No credit card required.'
                  )}
                </p>
              </div>
            </div>

            {actionMessage && (
              <div
                className={
                  'sandbox-result-box ' +
                  (actionMessage.type === 'error' ? 'error' : 'success')
                }
                role="alert"
              >
                {actionMessage.text}
              </div>
            )}

            <div className="sandbox-actions">
              <button
                type="button"
                className="sandbox-btn-success"
                disabled={busy}
                onClick={() => handleSimulatePayment('pay_success')}
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  check_circle
                </span>
                {busy
                  ? t('Đang xử lý...', 'Processing...')
                  : t(
                      'Thanh toán tức thì (Mô phỏng thành công)',
                      'Instant Payment (Simulate Success)'
                    )}
              </button>

              <button
                type="button"
                className="sandbox-btn-fail"
                disabled={busy}
                onClick={() => handleSimulatePayment('pay_fail')}
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  cancel
                </span>
                {t('Mô phỏng Thất bại / Hủy đơn', 'Simulate Failure / Cancel')}
              </button>

              <button
                type="button"
                className="sandbox-btn-vnpay"
                disabled={busy || !vnpayConfigured}
                onClick={handleVnpayCheckout}
                title={
                  !vnpayConfigured
                    ? t(
                        'Chờ Owner phê duyệt giá VND trước khi mở checkout VNPAY',
                        'Pending Owner approval for VND pricing before enabling VNPAY checkout'
                      )
                    : ''
                }
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  payments
                </span>
                <span>{t('Cổng VNPAY Sandbox', 'VNPAY Sandbox Gateway')}</span>
                {!vnpayConfigured && (
                  <small className="sandbox-vnpay-badge">
                    ({t('Chờ duyệt giá VND', 'Pending VND Approval')})
                  </small>
                )}
              </button>
            </div>

            <div className="workspace-dialog-actions">
              <button type="button" disabled={busy} onClick={closeDialog}>
                {t('Đóng', 'Close')}
              </button>
            </div>
          </div>
        )}
      </dialog>
    </main>
  );
}
