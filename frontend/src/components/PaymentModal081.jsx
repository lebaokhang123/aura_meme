// Lucian UX/UI Prompt #081 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#081
// Adapted for AuraMeme Cyberpunk Cultivation Platform with authoritative backend verification
import React, { useState, useEffect, useRef } from 'react';
import { auth } from '../auth.js';
import '../payment-ring-081.css';

export default function PaymentModal081({
  plan,
  isOpen,
  onClose,
  onSuccess,
  language = 'vi',
  vnpayConfigured = false,
}) {
  const t = (vi, en) => (language === 'en' ? en : vi);
  const dialogRef = useRef(null);

  // States: 'idle' | 'creating_order' | 'processing' | 'pending_confirmation' | 'confirmed' | 'failed'
  const [paymentState, setPaymentState] = useState('idle');
  const [statusText, setStatusText] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [receipt, setReceipt] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) {
      setPaymentState('idle');
      setStatusText('');
      setErrorMessage('');
      setReceipt(null);
      setBusy(false);
      if (!dialog.open) {
        dialog.showModal();
      }
    } else {
      if (dialog.open) {
        dialog.close();
      }
    }
  }, [isOpen]);

  function handleCancelClose(e) {
    if (busy) {
      e.preventDefault();
      return;
    }
    onClose();
  }

  async function handleSimulate(action) {
    if (busy) return;
    setBusy(true);
    setErrorMessage('');

    try {
      // Step 1: Creating order
      setPaymentState('creating_order');
      setStatusText(t('Đang khởi tạo đơn hàng...', 'Creating order...'));

      const orderRes = await auth.write('POST', '/premium/orders', {
        plan_tier: plan.id,
        provider: 'sandbox_simulated',
      });

      if (!orderRes?.order_code) {
        throw new Error(t('Không thể tạo đơn hàng thử nghiệm.', 'Could not create sandbox order.'));
      }

      // Step 2: Processing payment
      setPaymentState('processing');
      setStatusText(
        action === 'pay_success'
          ? t('Đang kết nối cổng mô phỏng...', 'Processing sandbox simulation...')
          : t('Đang gửi yêu cầu hủy / từ chối...', 'Sending cancel request...')
      );

      const simRes = await auth.write(
        'POST',
        `/premium/orders/${orderRes.order_code}/simulate`,
        { action }
      );

      // Step 3: Authoritative backend confirmation
      if (action === 'pay_success') {
        setPaymentState('pending_confirmation');
        setStatusText(t('Đang xác nhận với hệ thống...', 'Verifying with server...'));

        const [statusRes] = await Promise.all([
          auth.read('/premium/status').catch(() => null),
          onSuccess ? onSuccess() : Promise.resolve(),
        ]);

        if (statusRes?.subscription?.is_active) {
          // Genuine success confirmed by authoritative backend
          setReceipt({
            orderCode: orderRes.order_code,
            tierName: plan.name,
            amountVnd: plan.priceVndFormatted,
            amountUsd: plan.priceFormatted,
            durationDays: plan.days,
            activatedAt: new Date().toLocaleDateString(language === 'en' ? 'en-US' : 'vi-VN'),
          });
          setPaymentState('confirmed');
          setStatusText(
            t('Thanh toán thành công! Gói hội viên đã kích hoạt.', 'Payment confirmed! Membership active.')
          );
        } else {
          // Backend did not confirm subscription
          throw new Error(
            t('Đơn hàng chưa được hệ thống ghi nhận thành công.', 'Order was not confirmed by server.')
          );
        }
      } else {
        // Explicit simulation failure / cancellation
        setPaymentState('failed');
        setErrorMessage(
          t(
            'Mô phỏng thanh toán thất bại hoặc hủy đơn thành công.',
            'Simulated payment failure or cancellation successful.'
          )
        );
        setStatusText(t('Giao dịch đã bị từ chối / hủy.', 'Transaction rejected or cancelled.'));
      }
    } catch (err) {
      setPaymentState('failed');
      setErrorMessage(
        err.message || t('Đã xảy ra lỗi trong quá trình xử lý.', 'An error occurred during processing.')
      );
      setStatusText(t('Giao dịch không thành công.', 'Transaction failed.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleVnpayGateway() {
    if (busy || !vnpayConfigured) return;
    setBusy(true);
    setErrorMessage('');

    try {
      setPaymentState('creating_order');
      setStatusText(t('Đang kết nối cổng VNPAY Sandbox...', 'Connecting to VNPAY Sandbox...'));

      const orderRes = await auth.write('POST', '/premium/orders', {
        plan_tier: plan.id,
        provider: 'vnpay_sandbox',
      });

      if (orderRes?.payment_url) {
        setPaymentState('processing');
        setStatusText(t('Đang chuyển hướng sang VNPAY...', 'Redirecting to VNPAY...'));
        window.location.href = orderRes.payment_url;
      } else {
        throw new Error(t('Không nhận được đường dẫn thanh toán VNPAY.', 'No VNPAY payment URL received.'));
      }
    } catch (err) {
      setPaymentState('failed');
      setErrorMessage(err.message || t('Không thể khởi tạo cổng VNPAY.', 'Could not initialize VNPAY.'));
      setStatusText(t('Kết nối VNPAY thất bại.', 'VNPAY connection failed.'));
      setBusy(false);
    }
  }

  if (!isOpen) return null;

  const isSpinning = paymentState === 'creating_order' || paymentState === 'processing' || paymentState === 'pending_confirmation';
  const isConfirmed = paymentState === 'confirmed';
  const isFailed = paymentState === 'failed';

  return (
    <dialog
      ref={dialogRef}
      className="u081-dialog"
      aria-labelledby="u081-title"
      onCancel={handleCancelClose}
      onClose={handleCancelClose}
    >
      <div className="u081-container">
        {/* Header */}
        <div className="u081-header">
          <h2 id="u081-title">
            {t(`Xác nhận đơn hàng — Aura ${plan.name}`, `Order Confirmation — Aura ${plan.name}`)}
          </h2>
          <button
            type="button"
            className="u081-close-btn"
            aria-label={t('Đóng', 'Close')}
            disabled={busy}
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {/* Plan Summary */}
        <div className="u081-summary">
          <div className="u081-summary-row">
            <span>{t('Gói hội viên', 'Membership Plan')}:</span>
            <strong>Aura {plan.name}</strong>
          </div>
          <div className="u081-summary-row">
            <span>{t('Số tiền thanh toán thực tế (VNPAY)', 'Actual payment amount (VNPAY)')}:</span>
            <strong className="u081-price-primary">{plan.priceVndFormatted}</strong>
          </div>
          <div className="u081-summary-row">
            <span>{t('Giá niêm yết tham chiếu (USD)', 'Reference listed price (USD)')}:</span>
            <span>{plan.priceFormatted} USD</span>
          </div>
          <div className="u081-summary-row">
            <span>{t('Thời hạn sử dụng', 'Duration')}:</span>
            <span>{plan.days} {t('ngày', 'days')}</span>
          </div>
          <div className="u081-summary-row">
            <span>{t('Đặc quyền hệ số EXP', 'EXP Bonus multiplier')}:</span>
            <span className="u081-exp-badge">×{plan.boost} Level EXP</span>
          </div>
        </div>

        {/* Steps indicator */}
        <div className="u081-steps" aria-hidden="true">
          <div className={`u081-step ${paymentState === 'creating_order' ? 'active' : ['processing', 'pending_confirmation', 'confirmed'].includes(paymentState) ? 'done' : ''}`}>
            <span className="u081-step-dot" />
            <span>1. {t('Tạo đơn', 'Create')}</span>
          </div>
          <div className="u081-step-line" />
          <div className={`u081-step ${paymentState === 'processing' ? 'active' : ['pending_confirmation', 'confirmed'].includes(paymentState) ? 'done' : ''}`}>
            <span className="u081-step-dot" />
            <span>2. {t('Xử lý', 'Process')}</span>
          </div>
          <div className="u081-step-line" />
          <div className={`u081-step ${paymentState === 'pending_confirmation' ? 'active' : isConfirmed ? 'done' : ''}`}>
            <span className="u081-step-dot" />
            <span>3. {t('Xác nhận', 'Confirm')}</span>
          </div>
        </div>

        {/* Lucian #081 Payment Ring & Check Center Stage */}
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
                  <span className="material-symbols-outlined">
                    close
                  </span>
                )}
              </div>
            </div>
            {statusText && <div className="u081-stage-status">{statusText}</div>}
          </div>
        )}

        {/* Failure message */}
        {isFailed && errorMessage && (
          <div className="u081-error-banner" role="alert">
            <span className="material-symbols-outlined" aria-hidden="true">error</span>
            <span>{errorMessage}</span>
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
          </div>
        )}

        {/* Actions */}
        <div className="u081-actions">
          {paymentState === 'idle' && (
            <>
              <button
                type="button"
                className="u081-btn-simulate"
                disabled={busy}
                onClick={() => handleSimulate('pay_success')}
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  check_circle
                </span>
                <span>
                  {t(
                    'Thanh toán tức thì (Mô phỏng Sandbox)',
                    'Instant Payment (Simulate Success)'
                  )}
                </span>
              </button>

              <button
                type="button"
                className="u081-btn-fail"
                disabled={busy}
                onClick={() => handleSimulate('pay_fail')}
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  cancel
                </span>
                <span>
                  {t('Mô phỏng Thất bại / Hủy đơn', 'Simulate Failure / Cancel')}
                </span>
              </button>

              <button
                type="button"
                className="u081-btn-vnpay"
                disabled={busy || !vnpayConfigured}
                onClick={handleVnpayGateway}
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
                  <small className="u081-vnpay-badge">
                    ({t('Chờ duyệt giá VND', 'Pending VND Approval')})
                  </small>
                )}
              </button>
            </>
          )}

          {isConfirmed && (
            <button
              type="button"
              className="u081-btn-done"
              onClick={onClose}
            >
              <span className="material-symbols-outlined" aria-hidden="true">done_all</span>
              <span>{t('Hoàn tất & Đóng', 'Done & Close')}</span>
            </button>
          )}

          {isFailed && (
            <button
              type="button"
              className="u081-btn-retry"
              onClick={() => {
                setPaymentState('idle');
                setErrorMessage('');
                setStatusText('');
              }}
            >
              <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
              <span>{t('Thử lại', 'Try Again')}</span>
            </button>
          )}
        </div>
      </div>
    </dialog>
  );
}
