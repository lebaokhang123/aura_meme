// Lucian UX/UI Prompt #081 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#081
// Order Confirmation Modal adapted for AuraMeme Cyberpunk Cultivation Platform
import React, { useState, useEffect, useRef } from 'react';
import { auth } from '../auth.js';
import '../payment-ring-081.css';

export default function PaymentModal081({
  plan,
  isOpen,
  onClose,
  language = 'vi',
}) {
  const t = (vi, en) => (language === 'en' ? en : vi);
  const dialogRef = useRef(null);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) {
      setBusy(false);
      setError('');
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

  async function handleConfirmOrder() {
    if (busy || !plan) return;
    setBusy(true);
    setError('');

    try {
      const orderRes = await auth.write('POST', '/premium/orders', {
        plan_tier: plan.id,
        provider: 'sandbox_simulated',
      });

      if (!orderRes?.order_code) {
        throw new Error(t('Không thể tạo đơn hàng từ hệ thống.', 'Could not create order.'));
      }

      // Navigate to dedicated checkout page with order code
      window.location.assign(`/premium/checkout?order=${encodeURIComponent(orderRes.order_code)}`);
    } catch (err) {
      setError(err.message || t('Khởi tạo đơn hàng không thành công.', 'Failed to initialize order.'));
      setBusy(false);
    }
  }

  if (!isOpen || !plan) return null;

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
          <div className="u081-header-title-wrap">
            <span className="material-symbols-outlined u081-header-icon" aria-hidden="true">
              receipt_long
            </span>
            <h2 id="u081-title">
              {t(`Xác nhận đơn hàng — Aura ${plan.name}`, `Order Confirmation — Aura ${plan.name}`)}
            </h2>
          </div>
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

        {/* Plan Summary - Two-column aligned table */}
        <div className="u081-summary">
          <div className="u081-summary-row">
            <span className="u081-row-label">{t('Gói hội viên', 'Membership Plan')}</span>
            <strong className="u081-row-val u081-tier-val">Aura {plan.name}</strong>
          </div>
          <div className="u081-summary-row">
            <span className="u081-row-label">{t('Số tiền thanh toán', 'Payment Amount')}</span>
            <strong className="u081-row-val u081-price-primary">
              {language === 'en' ? `${plan.priceFormatted} USD` : plan.priceVndFormatted}
            </strong>
          </div>
          <div className="u081-summary-row">
            <span className="u081-row-label">{t('Thời hạn sử dụng', 'Duration')}</span>
            <strong className="u081-row-val">{plan.days} {t('ngày', 'days')}</strong>
          </div>
          <div className="u081-summary-row">
            <span className="u081-row-label">{t('Đặc quyền hệ số EXP', 'EXP Multiplier')}</span>
            <strong className="u081-row-val u081-exp-badge">×{plan.boost} Level EXP</strong>
          </div>
        </div>

        {/* Error notice if creation failed */}
        {error && (
          <div className="u081-error-banner" role="alert">
            <span className="material-symbols-outlined" aria-hidden="true">error</span>
            <span>{error}</span>
          </div>
        )}

        {/* Discreet note */}
        <div className="u081-note">
          <span className="material-symbols-outlined" aria-hidden="true">info</span>
          <span>{t('Hệ thống mô phỏng thanh toán', 'Simulated payment system')}</span>
        </div>

        {/* Single Primary Action Button */}
        <div className="u081-actions">
          <button
            type="button"
            className="u081-btn-confirm"
            disabled={busy}
            onClick={handleConfirmOrder}
          >
            {busy ? (
              <>
                <span className="material-symbols-outlined u081-spin-icon" aria-hidden="true">
                  sync
                </span>
                <span>{t('Đang chuyển sang thanh toán...', 'Redirecting to checkout...')}</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined" aria-hidden="true">
                  arrow_forward
                </span>
                <span>{t('Xác nhận thanh toán', 'Confirm Payment')}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </dialog>
  );
}
