// Lucian UX/UI Prompt #081 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#081
// Dedicated Simulated Checkout Page for AuraMeme Cyberpunk Cultivation Platform
import React, { useState, useEffect } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { usePremium } from '../PremiumContext.jsx';
import { auth } from '../auth.js';
import '../payment-ring-081.css';

export default function PremiumCheckoutPage() {
  const { language } = usePreferences();
  const t = (vi, en) => (language === 'en' ? en : vi);
  const { refresh: refreshPremium } = usePremium();

  const [orderCode, setOrderCode] = useState('');
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  // Form state - Form values exist strictly in memory for presentation and client formatting
  // NEVER transmitted to backend, logged, or saved to localStorage/database
  const [cardholderName, setCardholderName] = useState('NGUYEN VAN A');
  const [cardNumber, setCardNumber] = useState('4242 4242 4242 4242');
  const [expiryDate, setExpiryDate] = useState('12/28');
  const [cvv, setCvv] = useState('123');

  const [errors, setErrors] = useState({});
  // States: 'idle' | 'processing' | 'verifying' | 'success' | 'failed'
  const [checkoutState, setCheckoutState] = useState('idle');
  const [statusText, setStatusText] = useState('');
  const [checkoutError, setCheckoutError] = useState('');
  const [receipt, setReceipt] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('order');
    if (!code) {
      setLoadError(t('Không tìm thấy mã đơn hàng trong liên kết.', 'No order code found in URL.'));
      setLoading(false);
      return;
    }
    setOrderCode(code);

    let mounted = true;
    auth
      .read(`/premium/orders/${code}`)
      .then((data) => {
        if (!mounted) return;
        if (!data || !data.order_code) {
          throw new Error(t('Không tìm thấy thông tin đơn hàng.', 'Order not found.'));
        }
        setOrder(data);
        if (data.status === 'success') {
          // Order was already paid
          setCheckoutState('success');
          setReceipt({
            orderCode: data.order_code,
            tierName: data.tier === 'prime' ? 'Prime' : 'Plus',
            amountVnd: `${Number(data.amount_vnd).toLocaleString('vi-VN')} VNĐ`,
            amountUsd: data.amount_usd_formatted || (data.tier === 'prime' ? '$50' : '$5'),
            durationDays: data.duration_days,
            activatedAt: data.completed_at
              ? new Date(data.completed_at).toLocaleString(language === 'en' ? 'en-US' : 'vi-VN')
              : new Date().toLocaleString(language === 'en' ? 'en-US' : 'vi-VN'),
            status: 'ACTIVE',
          });
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setLoadError(
          err.message || t('Đơn hàng không tồn tại hoặc đã hết hiệu lực.', 'Order does not exist or has expired.')
        );
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [language]);

  function formatCardNumber(val) {
    const digits = val.replace(/\D/g, '').slice(0, 16);
    return digits.replace(/(\d{4})(?=\d)/g, '$1 ');
  }

  function formatExpiry(val) {
    const digits = val.replace(/\D/g, '').slice(0, 4);
    if (digits.length >= 3) {
      return `${digits.slice(0, 2)}/${digits.slice(2, 4)}`;
    }
    return digits;
  }

  function formatCvv(val) {
    return val.replace(/\D/g, '').slice(0, 3);
  }

  function fillSampleCard() {
    setCardholderName('NGUYEN VAN A');
    setCardNumber('4242 4242 4242 4242');
    setExpiryDate('12/28');
    setCvv('123');
    setErrors({});
  }

  function validateForm() {
    const errs = {};
    if (!cardholderName.trim()) {
      errs.cardholderName = t('Vui lòng nhập tên trên thẻ.', 'Cardholder name is required.');
    }
    const rawNumber = cardNumber.replace(/\s/g, '');
    if (!rawNumber || rawNumber.length !== 16) {
      errs.cardNumber = t('Số thẻ thử nghiệm cần đủ 16 chữ số.', 'Card number must be 16 digits.');
    }
    const expiryRegex = /^(0[1-9]|1[0-2])\/\d{2}$/;
    if (!expiryRegex.test(expiryDate)) {
      errs.expiryDate = t('Định dạng MM/YY không hợp lệ (ví dụ: 12/28).', 'Invalid MM/YY format (e.g. 12/28).');
    }
    if (!cvv || cvv.length !== 3) {
      errs.cvv = t('Mã CVV phải có 3 chữ số.', 'CVV must be 3 digits.');
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handlePaymentSubmit(e) {
    e.preventDefault();
    if (checkoutState === 'processing' || checkoutState === 'verifying') return;
    if (!validateForm()) return;

    setCheckoutState('processing');
    setCheckoutError('');
    setStatusText(t('Đang kết nối cổng mô phỏng...', 'Processing simulated payment...'));

    try {
      // Step 1: Simulated payment request
      // ZERO card details, CVVs, or cardholder names are ever transmitted to the server
      const simRes = await auth.write('POST', `/premium/orders/${order.order_code}/simulate`, {
        action: 'pay_success',
      });

      if (!simRes || simRes.status !== 'success') {
        throw new Error(t('Mô phỏng thanh toán không thành công.', 'Payment simulation failed.'));
      }

      // Step 2: Authoritative verification with backend status
      setCheckoutState('verifying');
      setStatusText(t('Đang xác thực giao dịch với máy chủ...', 'Verifying transaction with server...'));

      const [orderStatus, premiumStatus] = await Promise.all([
        auth.read(`/premium/orders/${order.order_code}`).catch(() => null),
        auth.read('/premium/status').catch(() => null),
        refreshPremium(),
      ]);

      if (premiumStatus?.subscription?.is_active && orderStatus?.status === 'success') {
        setCheckoutState('success');
        setReceipt({
          orderCode: order.order_code,
          tierName: order.tier === 'prime' ? 'Prime' : 'Plus',
          amountVnd: `${Number(order.amount_vnd).toLocaleString('vi-VN')} VNĐ`,
          amountUsd: order.amount_usd_formatted || (order.tier === 'prime' ? '$50' : '$5'),
          durationDays: order.duration_days,
          activatedAt: new Date().toLocaleString(language === 'en' ? 'en-US' : 'vi-VN'),
          status: 'ACTIVE',
        });
      } else {
        throw new Error(t('Máy chủ chưa thể xác nhận kích hoạt gói.', 'Server could not confirm activation.'));
      }
    } catch (err) {
      setCheckoutState('failed');
      setCheckoutError(err.message || t('Thanh toán mô phỏng thất bại.', 'Simulated payment failed.'));
    }
  }

  if (loading) {
    return (
      <main className="checkout-page">
        <div className="checkout-container">
          <div className="checkout-card" style={{ textAlign: 'center', padding: '48px 24px' }}>
            <span
              className="material-symbols-outlined u081-spin-icon"
              style={{ fontSize: '32px', color: 'var(--am-secondary)' }}
            >
              sync
            </span>
            <p style={{ marginTop: '16px', color: 'var(--am-on-surface-variant)' }}>
              {t('Đang tải thông tin đơn hàng...', 'Loading order details...')}
            </p>
          </div>
        </div>
      </main>
    );
  }

  if (loadError || !order) {
    return (
      <main className="checkout-page">
        <div className="checkout-container">
          <a className="checkout-back-link" href="/premium">
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
              arrow_back
            </span>
            <span>{t('Quay lại gói hội viên', 'Back to Membership Plans')}</span>
          </a>
          <div className="checkout-card" style={{ textAlign: 'center', padding: '40px 24px' }}>
            <span
              className="material-symbols-outlined"
              style={{ fontSize: '40px', color: '#ef4444' }}
            >
              error
            </span>
            <h2 style={{ margin: '16px 0 8px', color: 'var(--am-on-surface)' }}>
              {t('Không thể tiếp tục thanh toán', 'Unable to Proceed with Checkout')}
            </h2>
            <p style={{ color: 'var(--am-on-surface-variant)', marginBottom: '24px' }}>
              {loadError || t('Đơn hàng không tồn tại hoặc đã hết hạn.', 'Order not found or expired.')}
            </p>
            <a
              href="/premium"
              className="checkout-btn-home"
              style={{ display: 'inline-flex', width: 'auto', padding: '0 24px' }}
            >
              {t('Chọn lại gói', 'Choose Plan')}
            </a>
          </div>
        </div>
      </main>
    );
  }

  const isSpinning = checkoutState === 'processing' || checkoutState === 'verifying';
  const isConfirmed = checkoutState === 'success';
  const isFailed = checkoutState === 'failed';

  const tierTitle = order.tier === 'prime' ? 'Aura Prime' : 'Aura Plus';
  const formattedVnd = `${Number(order.amount_vnd).toLocaleString('vi-VN')} VNĐ`;

  return (
    <main className="checkout-page">
      <div className="checkout-container">
        {/* Navigation back */}
        <a className="checkout-back-link" href="/premium">
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
            arrow_back
          </span>
          <span>{t('Quay lại gói hội viên', 'Back to Membership Plans')}</span>
        </a>

        {/* Header */}
        <div className="checkout-header">
          <h1>{t('Thanh toán Hội viên Aura', 'Aura Membership Checkout')}</h1>
          <p>
            {t(
              'Xác nhận thông tin giao dịch và thực hiện thanh toán thử nghiệm.',
              'Confirm transaction details and complete simulated checkout.'
            )}
          </p>
        </div>

        {/* Main 2-column layout */}
        <div className="checkout-grid">
          {/* Column 1: Order Information */}
          <section className="checkout-card checkout-order-summary" aria-labelledby="order-summary-title">
            <div className="checkout-card-header">
              <span className="material-symbols-outlined checkout-card-icon" aria-hidden="true">
                receipt_long
              </span>
              <h2 id="order-summary-title">{t('Thông tin giao dịch', 'Transaction Summary')}</h2>
            </div>

            <div className="u081-summary">
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Mã đơn hàng', 'Order code')}</span>
                <strong className="u081-row-val u081-receipt-code">{order.order_code}</strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Gói hội viên', 'Membership Plan')}</span>
                <strong className="u081-row-val u081-tier-val">{tierTitle}</strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Giá thanh toán thực tế', 'Actual Payment')}</span>
                <strong className="u081-row-val u081-price-primary">{formattedVnd}</strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Giá niêm yết tham chiếu', 'Reference Price')}</span>
                <span className="u081-row-val">
                  {order.amount_usd_formatted || (order.tier === 'prime' ? '$50' : '$5')} USD
                </span>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Thời hạn sử dụng', 'Duration')}</span>
                <strong className="u081-row-val">{order.duration_days} {t('ngày', 'days')}</strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Đặc quyền EXP', 'EXP Bonus')}</span>
                <strong className="u081-row-val u081-exp-badge">
                  {order.tier === 'prime' ? '×3' : '×2'} Level EXP
                </strong>
              </div>
            </div>

            <div className="u081-note">
              <span className="material-symbols-outlined" aria-hidden="true">info</span>
              <span>{t('Hệ thống mô phỏng thanh toán', 'Simulated payment system')}</span>
            </div>
          </section>

          {/* Column 2: Simulated Card Form & Payment Ring Stage */}
          <section className="checkout-card checkout-payment-section" aria-labelledby="card-form-title">
            <div className="checkout-card-header">
              <span className="material-symbols-outlined checkout-card-icon" aria-hidden="true">
                credit_card
              </span>
              <h2 id="card-form-title">{t('Thông tin thẻ thử nghiệm', 'Simulated Card Information')}</h2>
            </div>

            {/* Stage indicator for Lucian #081 Ring and Checkmark */}
            {(isSpinning || isConfirmed || isFailed) && (
              <div className="u081-stage" role="status" aria-live="polite">
                <div className="u081-ring-wrapper">
                  <svg className="u081-svg-ring" viewBox="0 0 88 88" aria-hidden="true">
                    <circle className="u081-track" cx="44" cy="44" r="38" />
                    <circle
                      className={`u081-progress ${isSpinning ? 'spinning' : ''} ${isConfirmed ? 'confirmed' : ''} ${isFailed ? 'failed' : ''}`}
                      cx="44"
                      cy="44"
                      r="38"
                    />
                  </svg>
                  <div
                    className={`u081-center-icon ${isSpinning ? 'active' : ''} ${isConfirmed ? 'confirmed' : ''} ${isFailed ? 'failed' : ''}`}
                  >
                    {isSpinning && (
                      <span className="material-symbols-outlined" style={{ animation: 'u081-spin 2s linear infinite' }}>
                        sync
                      </span>
                    )}
                    {isConfirmed && (
                      <svg className="u081-check-svg" viewBox="0 0 24 24" aria-hidden="true">
                        <polyline className="u081-check-path" points="20 6 9 17 4 12" />
                      </svg>
                    )}
                    {isFailed && (
                      <span className="material-symbols-outlined" style={{ color: '#ffffff' }}>
                        close
                      </span>
                    )}
                  </div>
                </div>
                {statusText && <div className="u081-stage-status">{statusText}</div>}
              </div>
            )}

            {/* Error Banner */}
            {isFailed && checkoutError && (
              <div className="u081-error-banner" role="alert">
                <span className="material-symbols-outlined" aria-hidden="true">error</span>
                <span>{checkoutError}</span>
              </div>
            )}

            {/* Receipt slide-up when confirmed */}
            {isConfirmed && receipt && (
              <div className="u081-receipt" role="region" aria-label={t('Biên nhận thanh toán', 'Payment Receipt')}>
                <div className="u081-receipt-title">
                  <span className="material-symbols-outlined" aria-hidden="true">task_alt</span>
                  <span>{t('BIÊN NHẬN GIAO DỊCH HỘI VIÊN', 'MEMBERSHIP TRANSACTION RECEIPT')}</span>
                </div>
                <div className="u081-receipt-row">
                  <span>{t('Mã đơn hàng', 'Order code')}:</span>
                  <strong className="u081-receipt-code">{receipt.orderCode}</strong>
                </div>
                <div className="u081-receipt-row">
                  <span>{t('Gói đăng ký', 'Subscription Plan')}:</span>
                  <strong>Aura {receipt.tierName}</strong>
                </div>
                <div className="u081-receipt-row">
                  <span>{t('Số tiền giao dịch', 'Amount')}:</span>
                  <strong>{receipt.amountVnd} ({receipt.amountUsd})</strong>
                </div>
                <div className="u081-receipt-row">
                  <span>{t('Thời hạn sử dụng', 'Duration')}:</span>
                  <span>{receipt.durationDays} {t('ngày', 'days')}</span>
                </div>
                <div className="u081-receipt-row">
                  <span>{t('Ngày kích hoạt', 'Activation date')}:</span>
                  <span>{receipt.activatedAt}</span>
                </div>
                <div className="u081-receipt-row">
                  <span>{t('Trạng thái', 'Status')}:</span>
                  <span className="u081-receipt-badge">{t('ĐÃ KÍCH HOẠT (ACTIVE)', 'ACTIVE')}</span>
                </div>

                <a href="/" className="checkout-btn-home">
                  <span className="material-symbols-outlined" aria-hidden="true">
                    celebration
                  </span>
                  <span>{t('Trải nghiệm đặc quyền ngay', 'Experience Perks Now')}</span>
                </a>
              </div>
            )}

            {/* Card Input Form (Shown when idle or failed) */}
            {!isConfirmed && (
              <form className="checkout-form" onSubmit={handlePaymentSubmit} noValidate>
                {/* Test card autofill pill */}
                <div
                  className="checkout-demo-pill"
                  onClick={fillSampleCard}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fillSampleCard()}
                  title={t('Bấm để tự điền dữ liệu thẻ thử nghiệm', 'Click to autofill simulated test card')}
                >
                  <span className="checkout-demo-pill-title">
                    <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                      auto_fix_high
                    </span>
                    <span>{t('Dùng thẻ thử nghiệm mẫu', 'Use Sample Test Card')}</span>
                  </span>
                  <span className="checkout-demo-pill-val">4242 · 12/28 · 123</span>
                </div>

                <div className="checkout-form-group">
                  <label className="checkout-label" htmlFor="cardholder-name">
                    {t('Tên trên thẻ (Thử nghiệm)', 'Cardholder Name (Simulated)')}
                  </label>
                  <input
                    id="cardholder-name"
                    name="cardholderName"
                    type="text"
                    className={`checkout-input ${errors.cardholderName ? 'error' : ''}`}
                    placeholder="NGUYEN VAN A"
                    value={cardholderName}
                    disabled={isSpinning}
                    onChange={(e) => {
                      setCardholderName(e.target.value.toUpperCase());
                      if (errors.cardholderName) setErrors({ ...errors, cardholderName: null });
                    }}
                    autoComplete="off"
                  />
                  {errors.cardholderName && (
                    <span className="checkout-field-error" role="alert">
                      {errors.cardholderName}
                    </span>
                  )}
                </div>

                <div className="checkout-form-group">
                  <label className="checkout-label" htmlFor="card-number">
                    {t('Số thẻ thử nghiệm', 'Simulated Card Number')}
                  </label>
                  <input
                    id="card-number"
                    name="cardNumber"
                    type="text"
                    inputMode="numeric"
                    className={`checkout-input ${errors.cardNumber ? 'error' : ''}`}
                    placeholder="4242 4242 4242 4242"
                    value={cardNumber}
                    disabled={isSpinning}
                    onChange={(e) => {
                      setCardNumber(formatCardNumber(e.target.value));
                      if (errors.cardNumber) setErrors({ ...errors, cardNumber: null });
                    }}
                    autoComplete="off"
                  />
                  {errors.cardNumber && (
                    <span className="checkout-field-error" role="alert">
                      {errors.cardNumber}
                    </span>
                  )}
                </div>

                <div className="checkout-form-row">
                  <div className="checkout-form-group">
                    <label className="checkout-label" htmlFor="card-expiry">
                      {t('Hết hạn (MM/YY)', 'Expiry (MM/YY)')}
                    </label>
                    <input
                      id="card-expiry"
                      name="expiryDate"
                      type="text"
                      inputMode="numeric"
                      className={`checkout-input ${errors.expiryDate ? 'error' : ''}`}
                      placeholder="12/28"
                      value={expiryDate}
                      disabled={isSpinning}
                      onChange={(e) => {
                        setExpiryDate(formatExpiry(e.target.value));
                        if (errors.expiryDate) setErrors({ ...errors, expiryDate: null });
                      }}
                      autoComplete="off"
                    />
                    {errors.expiryDate && (
                      <span className="checkout-field-error" role="alert">
                        {errors.expiryDate}
                      </span>
                    )}
                  </div>

                  <div className="checkout-form-group">
                    <label className="checkout-label" htmlFor="card-cvv">
                      {t('Mã CVV (3 số)', 'CVV (3 digits)')}
                    </label>
                    <input
                      id="card-cvv"
                      name="cvv"
                      type="password"
                      inputMode="numeric"
                      className={`checkout-input ${errors.cvv ? 'error' : ''}`}
                      placeholder="123"
                      value={cvv}
                      disabled={isSpinning}
                      onChange={(e) => {
                        setCvv(formatCvv(e.target.value));
                        if (errors.cvv) setErrors({ ...errors, cvv: null });
                      }}
                      autoComplete="off"
                    />
                    {errors.cvv && (
                      <span className="checkout-field-error" role="alert">
                        {errors.cvv}
                      </span>
                    )}
                  </div>
                </div>

                {/* Primary Pay Action */}
                <button
                  type="submit"
                  className="checkout-btn-pay"
                  disabled={isSpinning}
                >
                  <span className="material-symbols-outlined" aria-hidden="true">
                    {isSpinning ? 'sync' : 'lock'}
                  </span>
                  <span>
                    {isSpinning
                      ? t('Đang xử lý...', 'Processing...')
                      : t('Thanh toán', 'Pay Now')}
                  </span>
                </button>

                {isFailed && (
                  <button
                    type="button"
                    className="checkout-btn-retry"
                    onClick={() => {
                      setCheckoutState('idle');
                      setCheckoutError('');
                      setStatusText('');
                    }}
                  >
                    <span className="material-symbols-outlined" aria-hidden="true">
                      refresh
                    </span>
                    <span>{t('Thử lại', 'Try Again')}</span>
                  </button>
                )}
              </form>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
