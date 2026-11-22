// Lucian UX/UI Prompt #081 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#081
// Dedicated Simulated Checkout Page for AuraMeme Cyberpunk Cultivation Platform
import React, { useState, useEffect, useRef } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { usePremium } from '../PremiumContext.jsx';
import { auth } from '../auth.js';
import { readDemoUser } from '../demo.js';
import { downloadReceiptPdf } from '../receipt-pdf.js';
import '../payment-ring-081.css';

const COUNTRIES = [
  { code: 'VN', nameVi: 'Việt Nam', nameEn: 'Vietnam', dialCode: '+84' },
  { code: 'US', nameVi: 'Hoa Kỳ (United States)', nameEn: 'United States', dialCode: '+1' },
  { code: 'JP', nameVi: 'Nhật Bản (Japan)', nameEn: 'Japan', dialCode: '+81' },
  { code: 'KR', nameVi: 'Hàn Quốc (South Korea)', nameEn: 'South Korea', dialCode: '+82' },
  { code: 'SG', nameVi: 'Singapore', nameEn: 'Singapore', dialCode: '+65' },
  { code: 'AU', nameVi: 'Úc (Australia)', nameEn: 'Australia', dialCode: '+61' },
  { code: 'GB', nameVi: 'Vương quốc Anh (United Kingdom)', nameEn: 'United Kingdom', dialCode: '+44' },
  { code: 'OTHER', nameVi: 'Khác (Other)', nameEn: 'Other', dialCode: '' },
];

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
  // Group 1: Card details
  const [cardNumber, setCardNumber] = useState('4242 4242 4242 4242');
  const [expiryDate, setExpiryDate] = useState('12/28');
  const [cvv, setCvv] = useState('123');

  // Group 2: Billing information
  const [cardholderName, setCardholderName] = useState('NGUYEN VAN A');
  const [country, setCountry] = useState('VN');
  const [address1, setAddress1] = useState('123 Đường Cyber');
  const [address2, setAddress2] = useState('Tòa nhà Aura, Tầng 5');
  const [city, setCity] = useState('TP. Hồ Chí Minh');
  const [postalCode, setPostalCode] = useState('700000');
  const [phone, setPhone] = useState('0901234567');

  const selectedCountryObj = COUNTRIES.find((c) => c.code === country) || COUNTRIES[0];
  const dialCode = selectedCountryObj.dialCode;

  const [errors, setErrors] = useState({});
  // Payment method selector: 'paypal' | 'card'
  const [paymentMethod, setPaymentMethod] = useState('paypal');
  // States: 'idle' | 'processing' | 'verifying' | 'success' | 'failed'
  const [checkoutState, setCheckoutState] = useState('idle');
  const [statusText, setStatusText] = useState('');
  const [checkoutError, setCheckoutError] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [instantConfirmStep, setInstantConfirmStep] = useState(0);
  const instantTimerRef = useRef(null);

  const handleInstantCaptureClick = () => {
    if (instantConfirmStep === 0) {
      setInstantConfirmStep(1);
      if (instantTimerRef.current) clearTimeout(instantTimerRef.current);
      instantTimerRef.current = setTimeout(() => {
        setInstantConfirmStep(0);
      }, 4000);
    } else {
      if (instantTimerRef.current) clearTimeout(instantTimerRef.current);
      setInstantConfirmStep(0);
      executeCapture();
    }
  };

  useEffect(() => {
    return () => {
      if (instantTimerRef.current) clearTimeout(instantTimerRef.current);
    };
  }, []);

  // Handle bfcache restoration & reset any stuck transient state
  useEffect(() => {
    const handlePageShow = () => {
      if (checkoutState === 'processing' || checkoutState === 'verifying') {
        setCheckoutState('idle');
        setStatusText('');
      }
    };
    window.addEventListener('pageshow', handlePageShow);
    return () => {
      window.removeEventListener('pageshow', handlePageShow);
    };
  }, [checkoutState]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    let code = params.get('order');
    if (!code) {
      code = sessionStorage.getItem('am_checkout_order');
    }
    if (!code) {
      setLoadError(t('Không tìm thấy mã đơn hàng trong liên kết.', 'No order code found in URL.'));
      setLoading(false);
      return;
    }
    if (typeof code !== 'string' || code.length > 64 || !/^AM-[A-Za-z0-9\-_]{6,60}$/.test(code)) {
      setLoadError(t('Mã đơn hàng không đúng định dạng.', 'Invalid order code format.'));
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
        if (data.provider === 'sandbox_simulated') {
          setPaymentMethod('card');
        } else {
          setPaymentMethod('paypal');
        }
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
            provider: data.provider,
            provider_txn_id: data.provider_txn_id,
            isExistingSuccess: true,
          });
        } else if (data.status === 'cancelled' || data.status === 'failed') {
          setCheckoutState('failed');
          setCheckoutError(
            data.status === 'cancelled'
              ? t('Đơn hàng này đã bị hủy.', 'This order was cancelled.')
              : t('Đơn hàng thanh toán không thành công.', 'Payment was not successful for this order.')
          );
        } else {
          setCheckoutState('idle');
          setCheckoutError('');
        }
        setLoading(false);

        // If returned from PayPal approval with token, automatically capture
        const token = params.get('token');
        if (token && data.status === 'pending') {
          executeCapture(token, data);
        }
      })
      .catch((err) => {
        if (!mounted) return;
        console.error('[PremiumCheckoutPage] Load order failed:', err);
        setLoadError(
          t('Đơn hàng không tồn tại hoặc đã hết hiệu lực.', 'Order does not exist or has expired.')
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
    setCardNumber('4242 4242 4242 4242');
    setExpiryDate('12/28');
    setCvv('123');
    setCardholderName('NGUYEN VAN A');
    setCountry('VN');
    setAddress1('123 Đường Cyber');
    setAddress2('Tòa nhà Aura, Tầng 5');
    setCity('TP. Hồ Chí Minh');
    setPostalCode('700000');
    setPhone('0901234567');
    setErrors({});
  }

  function validateForm() {
    const errs = {};
    const rawNumber = cardNumber.replace(/\s/g, '');
    if (!rawNumber || rawNumber.length !== 16) {
      errs.cardNumber = t('Số thẻ thử nghiệm cần đủ 16 chữ số.', 'Card number must be 16 digits.');
    }
    const expiryRegex = /^(0[1-9]|1[0-2])\/\d{2}$/;
    if (!expiryRegex.test(expiryDate)) {
      errs.expiryDate = t('Định dạng MM/YY không hợp lệ (ví dụ: 12/28).', 'Invalid MM/YY format (e.g. 12/28).');
    }
    if (!cvv || (cvv.length !== 3 && cvv.length !== 4)) {
      errs.cvv = t('Mã CVV phải có 3 hoặc 4 chữ số.', 'CVV must be 3 or 4 digits.');
    }
    if (!cardholderName.trim()) {
      errs.cardholderName = t('Vui lòng nhập tên trên thẻ.', 'Cardholder name is required.');
    }
    if (!address1.trim()) {
      errs.address1 = t('Vui lòng nhập địa chỉ dòng 1.', 'Address line 1 is required.');
    }
    if (!city.trim()) {
      errs.city = t('Vui lòng nhập thành phố.', 'City is required.');
    }
    if (!postalCode.trim()) {
      errs.postalCode = t('Vui lòng nhập mã bưu chính.', 'Postal code is required.');
    }
    if (!phone.trim()) {
      errs.phone = t('Vui lòng nhập số điện thoại.', 'Phone number is required.');
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function executeCapture(paypalToken = null, targetOrder = null) {
    const currentOrder = targetOrder || order;
    if (!currentOrder) return;
    if (checkoutState === 'processing' || checkoutState === 'verifying') return;

    setCheckoutState('processing');
    setCheckoutError('');
    setStatusText(
      paymentMethod === 'card'
        ? t('Đang xử lý thanh toán bằng Thẻ...', 'Processing Card payment...')
        : t('Đang xử lý thanh toán PayPal...', 'Processing PayPal payment...')
    );

    try {
      let captureRes;
      if (paymentMethod === 'card') {
        captureRes = await auth.write('POST', `/premium/orders/${currentOrder.order_code}/simulate`, {
          action: 'pay_success',
        });
      } else {
        captureRes = await auth.write('POST', `/premium/orders/${currentOrder.order_code}/capture`, {
          paypal_order_id: paypalToken || currentOrder.provider_txn_id || 'MOCK_SANDBOX_TOKEN',
        });
      }

      if (!captureRes || captureRes.status !== 'success') {
        throw new Error(t('Xác thực thanh toán không thành công.', 'Payment capture verification failed.'));
      }

      setCheckoutState('verifying');
      setStatusText(t('Đang kích hoạt đặc quyền hội viên...', 'Activating membership perks...'));

      const [orderStatus, premiumStatus] = await Promise.all([
        auth.read(`/premium/orders/${currentOrder.order_code}`).catch(() => null),
        auth.read('/premium/status').catch(() => null),
        refreshPremium(),
      ]);

      if (premiumStatus?.subscription?.is_active && orderStatus?.status === 'success') {
        setCheckoutState('success');
        setReceipt({
          orderCode: currentOrder.order_code,
          tierName: currentOrder.tier === 'prime' ? 'Prime' : 'Plus',
          amountVnd: `${Number(currentOrder.amount_vnd).toLocaleString('vi-VN')} VNĐ`,
          amountUsd: currentOrder.amount_usd_formatted || (currentOrder.tier === 'prime' ? '$50' : '$5'),
          durationDays: currentOrder.duration_days,
          activatedAt: new Date().toLocaleString(language === 'en' ? 'en-US' : 'vi-VN'),
          status: 'ACTIVE',
          provider: orderStatus?.provider || (paymentMethod === 'card' ? 'sandbox_simulated' : 'paypal_sandbox'),
          provider_txn_id: orderStatus?.provider_txn_id || captureRes?.provider_txn_id,
        });
      } else {
        throw new Error(t('Máy chủ chưa thể xác nhận kích hoạt gói.', 'Server could not confirm activation.'));
      }
    } catch (err) {
      console.error('[PremiumCheckoutPage] Capture failed:', err);
      setCheckoutState('failed');
      setCheckoutError(t('Thanh toán thất bại. Vui lòng thử lại.', 'Payment failed. Please try again.'));
    }
  }

  async function handlePaymentSubmit(e) {
    e.preventDefault();
    if (checkoutState === 'processing' || checkoutState === 'verifying') return;
    if (!validateForm()) return;
    await executeCapture();
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
            <p className="checkout-load-error" style={{ color: 'var(--am-on-surface-variant)', marginBottom: '24px' }}>
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
                <strong className="u081-row-val u081-price-primary">
                  {language === 'en'
                    ? `${order.amount_usd_formatted || (order.tier === 'prime' ? '$50' : '$5')} USD`
                    : formattedVnd}
                </strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Giá quy đổi tham chiếu', 'Reference Price')}</span>
                <span className="u081-row-val">
                  {language === 'en'
                    ? formattedVnd
                    : `${order.amount_usd_formatted || (order.tier === 'prime' ? '$50' : '$5')} USD`}
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
              <span>{t('Hệ thống thanh toán thử nghiệm', 'Sandbox Payment System')}</span>
            </div>
          </section>

          {/* Column 2: PayPal Sandbox & Payment Ring Stage */}
          <section className="checkout-card checkout-payment-section" aria-labelledby="card-form-title">
            <div className="checkout-card-header">
              <span className="material-symbols-outlined checkout-card-icon" aria-hidden="true">
                payments
              </span>
              <h2 id="card-form-title">{t('Phương thức thanh toán', 'Payment Method')}</h2>
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

                <div
                  className="checkout-success-alert"
                  role="status"
                  style={{
                    padding: '10px 14px',
                    background: 'rgba(34, 197, 94, 0.12)',
                    border: '1px solid rgba(34, 197, 94, 0.35)',
                    borderRadius: '8px',
                    color: '#4ade80',
                    fontSize: '13px',
                    marginBottom: '16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontWeight: 500,
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '18px' }} aria-hidden="true">
                    check_circle
                  </span>
                  <span>
                    {t(
                      `Đơn hàng này đã được thanh toán thành công vào ${receipt.activatedAt}.`,
                      `This order was successfully paid on ${receipt.activatedAt}.`
                    )}
                  </span>
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
                <div className="u081-receipt-row u081-receipt-download-row">
                  <span>{t('Biên lai:', 'Receipt:')}</span>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="checkout-btn-download-receipt"
                      onClick={async () => {
                        const activeUser = auth.snapshot()?.user || readDemoUser?.();
                        let historyList = null;
                        try {
                          historyList = await auth.read('/premium/orders/successful');
                        } catch {}
                        downloadReceiptPdf(receipt || order, activeUser, historyList);
                      }}
                      title={t('Tải về biên lai PDF', 'Download PDF Receipt')}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
                        download
                      </span>
                      <span>{t('Tải PDF', 'Download PDF')}</span>
                    </button>
                  </div>
                </div>

                <div
                  className="checkout-receipt-actions"
                  style={{ display: 'flex', gap: '10px', marginTop: '18px' }}
                >
                  <a
                    href="/premium"
                    className="checkout-btn-home"
                    style={{
                      flex: 1,
                      background: 'rgba(255, 255, 255, 0.08)',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      color: 'var(--am-on-surface)',
                    }}
                  >
                    <span className="material-symbols-outlined" aria-hidden="true">
                      arrow_back
                    </span>
                    <span>{t('Về trang hội viên', 'Back to Plans')}</span>
                  </a>
                  <a href="/" className="checkout-btn-home" style={{ flex: 1.2 }}>
                    <span className="material-symbols-outlined" aria-hidden="true">
                      celebration
                    </span>
                    <span>{t('Trải nghiệm ngay', 'Experience Now')}</span>
                  </a>
                </div>
              </div>
            )}

            {/* Payment Method Selector & Actions (Shown when not confirmed) */}
            {!isConfirmed && (
              <>
                <div
                  className="checkout-method-selector"
                  role="radiogroup"
                  aria-label={t('Phương thức thanh toán', 'Payment method')}
                >
                  <div
                    className={`checkout-method-card ${paymentMethod === 'paypal' ? 'active' : ''}`}
                    role="radio"
                    aria-checked={paymentMethod === 'paypal'}
                    tabIndex={0}
                    data-method="paypal"
                    onClick={() => setPaymentMethod('paypal')}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setPaymentMethod('paypal')}
                  >
                    <div className="checkout-method-info">
                      <img
                        src="/assets/payment/paypal.png"
                        alt="PayPal"
                        className="checkout-method-img"
                        width="28"
                        height="28"
                      />
                      <div className="checkout-method-text">
                        <h3>
                          PayPal
                          <span className="checkout-method-badge">{t('Cổng chính', 'Primary')}</span>
                        </h3>
                        <p>{t('Thanh toán an toàn qua cổng PayPal v2', 'Secure payment via PayPal v2')}</p>
                      </div>
                    </div>
                    <div className="checkout-method-radio">
                      <div className="checkout-method-radio-dot" />
                    </div>
                  </div>

                  <div
                    className={`checkout-method-card ${paymentMethod === 'card' ? 'active' : ''}`}
                    role="radio"
                    aria-checked={paymentMethod === 'card'}
                    tabIndex={0}
                    data-method="card"
                    onClick={() => setPaymentMethod('card')}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setPaymentMethod('card')}
                  >
                    <div className="checkout-method-info">
                      <img
                        src="/assets/payment/credit_card.png"
                        alt="Credit Card"
                        className="checkout-method-img"
                        width="28"
                        height="28"
                      />
                      <div className="checkout-method-text">
                        <h3>{t('Nhập thẻ', 'Card Payment')}</h3>
                        <p>{t('Mô phỏng tức thì trên trình duyệt', 'Instant browser simulation')}</p>
                      </div>
                    </div>
                    <div className="checkout-method-radio">
                      <div className="checkout-method-radio-dot" />
                    </div>
                  </div>
                </div>

                {/* Option 1: PayPal Action Box with 4:1 row layout */}
                {paymentMethod === 'paypal' && (
                  <div className="checkout-paypal-action-box paypal-action-card">
                    <div className="checkout-paypal-btn-row">
                      <button
                        type="button"
                        className="checkout-btn-paypal"
                        disabled={isSpinning}
                        onClick={async () => {
                          try {
                            let current = order;
                            if (!current.payment_url || current.provider !== 'paypal_sandbox') {
                              const initRes = await auth.write('POST', `/premium/orders/${current.order_code}/init-paypal`);
                              if (initRes) {
                                current = initRes;
                                setOrder(initRes);
                              }
                            }
                            if (current.payment_url && !current.payment_url.includes('token=MOCK-')) {
                              sessionStorage.setItem('am_checkout_order', current.order_code);
                              window.location.assign(current.payment_url);
                            } else {
                              executeCapture(null, current);
                            }
                          } catch (err) {
                            console.error('[PremiumCheckoutPage] PayPal init failed:', err);
                            executeCapture();
                          }
                        }}
                      >
                        <img
                          src="/assets/payment/paypal.png"
                          alt=""
                          aria-hidden="true"
                          className="checkout-btn-paypal-icon"
                          width="20"
                          height="20"
                        />
                        <span>{t('Thanh toán ngay', 'Pay Now')}</span>
                      </button>

                      <div className="checkout-instant-wrapper">
                        <button
                          type="button"
                          className={`checkout-btn-instant checkout-btn-secondary ${instantConfirmStep === 1 ? 'confirming' : ''}`}
                          disabled={isSpinning}
                          onClick={handleInstantCaptureClick}
                          aria-label={
                            instantConfirmStep === 1
                              ? t('Bấm lại lần nữa để xác nhận', 'Click again to confirm')
                              : t('Duyệt thanh toán thử nghiệm PayPal tức thì', 'Instant sandbox approval')
                          }
                          title={
                            instantConfirmStep === 1
                              ? t('Bấm lại lần nữa để xác nhận', 'Click again to confirm')
                              : t('Duyệt thanh toán thử nghiệm PayPal tức thì', 'Instant sandbox approval')
                          }
                        >
                          <span className="material-symbols-outlined checkout-instant-bolt">
                            bolt
                          </span>
                        </button>
                        <span className="checkout-instant-tooltip" role="tooltip">
                          {instantConfirmStep === 1
                            ? t('Bấm lại lần nữa để xác nhận', 'Click again to confirm')
                            : t('Duyệt thanh toán thử nghiệm PayPal tức thì', 'Instant sandbox approval')}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Card Input Form (Shown only when paymentMethod is 'card') */}
            {!isConfirmed && paymentMethod === 'card' && (
              <div className="checkout-card-form-expand">
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

                  {/* Thẻ thanh toán (Card Details) */}
                  <div className="checkout-form-section">
                    <div className="checkout-form-section-title">
                      <span className="material-symbols-outlined" aria-hidden="true">credit_card</span>
                      <span>{t('Thẻ thanh toán', 'Card Details')}</span>
                    </div>

                    <div className="checkout-form-group">
                      <label className="checkout-label" htmlFor="card-number">
                        {t('Số thẻ', 'Card Number')}
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
                          {t('Ngày hết hạn (MM/YY)', 'Expiry (MM/YY)')}
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
                          {t('Mã CVV', 'CVV')}
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
                  </div>

                  {/* Thông tin thanh toán (Billing Information) */}
                  <div className="checkout-form-section">
                    <div className="checkout-form-section-title">
                      <span className="material-symbols-outlined" aria-hidden="true">badge</span>
                      <span>{t('Thông tin thanh toán', 'Billing Information')}</span>
                    </div>

                    <div className="checkout-form-group">
                      <label className="checkout-label" htmlFor="cardholder-name">
                        {t('Tên trên thẻ', 'Cardholder Name')}
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
                      <label className="checkout-label" htmlFor="billing-country">
                        {t('Quốc gia / Vùng lãnh thổ', 'Country / Region')}
                      </label>
                      <select
                        id="billing-country"
                        name="country"
                        className="checkout-select"
                        value={country}
                        disabled={isSpinning}
                        onChange={(e) => setCountry(e.target.value)}
                      >
                        {COUNTRIES.map((c) => (
                          <option key={c.code} value={c.code}>
                            {language === 'en' ? c.nameEn : c.nameVi}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="checkout-form-group">
                      <label className="checkout-label" htmlFor="billing-address-1">
                        {t('Địa chỉ dòng 1', 'Address Line 1')}
                      </label>
                      <input
                        id="billing-address-1"
                        name="address1"
                        type="text"
                        className={`checkout-input ${errors.address1 ? 'error' : ''}`}
                        placeholder={t('Số nhà, tên đường', 'Street address')}
                        value={address1}
                        disabled={isSpinning}
                        onChange={(e) => {
                          setAddress1(e.target.value);
                          if (errors.address1) setErrors({ ...errors, address1: null });
                        }}
                        autoComplete="off"
                      />
                      {errors.address1 && (
                        <span className="checkout-field-error" role="alert">
                          {errors.address1}
                        </span>
                      )}
                    </div>

                    <div className="checkout-form-group">
                      <label className="checkout-label" htmlFor="billing-address-2">
                        {t('Địa chỉ dòng 2 (Không bắt buộc)', 'Address Line 2 (Optional)')}
                      </label>
                      <input
                        id="billing-address-2"
                        name="address2"
                        type="text"
                        className="checkout-input"
                        placeholder={t('Căn hộ, tầng, tòa nhà...', 'Apartment, suite, unit...')}
                        value={address2}
                        disabled={isSpinning}
                        onChange={(e) => setAddress2(e.target.value)}
                        autoComplete="off"
                      />
                    </div>

                    <div className="checkout-form-row">
                      <div className="checkout-form-group">
                        <label className="checkout-label" htmlFor="billing-city">
                          {t('Thành phố', 'City')}
                        </label>
                        <input
                          id="billing-city"
                          name="city"
                          type="text"
                          className={`checkout-input ${errors.city ? 'error' : ''}`}
                          placeholder={t('Ví dụ: Hà Nội, TP.HCM', 'e.g. San Francisco')}
                          value={city}
                          disabled={isSpinning}
                          onChange={(e) => {
                            setCity(e.target.value);
                            if (errors.city) setErrors({ ...errors, city: null });
                          }}
                          autoComplete="off"
                        />
                        {errors.city && (
                          <span className="checkout-field-error" role="alert">
                            {errors.city}
                          </span>
                        )}
                      </div>

                      <div className="checkout-form-group">
                        <label className="checkout-label" htmlFor="billing-postal">
                          {t('Mã bưu chính', 'Postal Code')}
                        </label>
                        <input
                          id="billing-postal"
                          name="postalCode"
                          type="text"
                          className={`checkout-input ${errors.postalCode ? 'error' : ''}`}
                          placeholder={t('Ví dụ: 700000', 'e.g. 94103')}
                          value={postalCode}
                          disabled={isSpinning}
                          onChange={(e) => {
                            setPostalCode(e.target.value);
                            if (errors.postalCode) setErrors({ ...errors, postalCode: null });
                          }}
                          autoComplete="off"
                        />
                        {errors.postalCode && (
                          <span className="checkout-field-error" role="alert">
                            {errors.postalCode}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="checkout-form-group">
                      <label className="checkout-label" htmlFor="billing-phone">
                        {t('Số điện thoại', 'Phone Number')}
                      </label>
                      <div className="checkout-phone-input-wrap">
                        {dialCode && <span className="checkout-phone-prefix">{dialCode}</span>}
                        <input
                          id="billing-phone"
                          name="phone"
                          type="tel"
                          className={`checkout-input ${errors.phone ? 'error' : ''}`}
                          placeholder={t('Ví dụ: 0901234567', 'e.g. 555-0199')}
                          value={phone}
                          disabled={isSpinning}
                          onChange={(e) => {
                            setPhone(e.target.value);
                            if (errors.phone) setErrors({ ...errors, phone: null });
                          }}
                          autoComplete="off"
                        />
                      </div>
                      {errors.phone && (
                        <span className="checkout-field-error" role="alert">
                          {errors.phone}
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
                </form>
              </div>
            )}

            {!isConfirmed && isFailed && (
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
          </section>
        </div>
      </div>
    </main>
  );
}
