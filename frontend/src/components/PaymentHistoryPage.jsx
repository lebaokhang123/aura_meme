import React, { useState, useEffect, useRef } from 'react';
import { auth } from '../auth.js';
import { readPreferences } from '../preferences.js';
import { downloadReceiptPdf } from '../receipt-pdf.js';
import '../payment-ring-081.css';

export default function PaymentHistoryPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [downloadSuccess, setDownloadSuccess] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const dialogRef = useRef(null);

  const prefs = readPreferences();
  const language = prefs.language || 'vi';
  const t = (vi, en) => (language === 'en' ? en : vi);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ordersRes, statusRes] = await Promise.all([
        auth.read('/premium/orders').catch(err => {
          console.error('Failed to fetch orders:', err);
          throw err;
        }),
        auth.read('/premium/status').catch(() => null),
      ]);
      setOrders(Array.isArray(ordersRes) ? ordersRes : []);
      if (statusRes && statusRes.subscription) {
        setSubscription(statusRes.subscription);
      }
    } catch (err) {
      setError(err.message || t('Không thể tải lịch sử giao dịch.', 'Unable to load payment history.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [language]);

  const handleOpenDetail = (order) => {
    setSelectedOrder(order);
    if (dialogRef.current) {
      if (typeof dialogRef.current.showModal === 'function') {
        dialogRef.current.showModal();
      } else {
        dialogRef.current.setAttribute('open', '');
      }
    }
  };

  const handleCloseDetail = () => {
    setSelectedOrder(null);
    if (dialogRef.current) {
      if (typeof dialogRef.current.close === 'function') {
        dialogRef.current.close();
      } else {
        dialogRef.current.removeAttribute('open');
      }
    }
  };

  const handleDownloadPdf = (order, e) => {
    if (e) e.stopPropagation();
    const success = downloadReceiptPdf(order, auth.user);
    if (success) {
      setDownloadSuccess(order.order_code);
      setTimeout(() => setDownloadSuccess(null), 3000);
    }
  };

  const formatDate = (val) => {
    if (!val) return '—';
    try {
      const d = new Date(val);
      if (isNaN(d.getTime())) return String(val);
      const pad = (n) => String(n).padStart(2, '0');
      return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
      return String(val);
    }
  };

  const formatAmount = (order) => {
    const isPrime = order.tier === 'prime';
    const usd = order.amount_usd_formatted || (isPrime ? '$50' : '$5');
    const vnd = order.amount_vnd_formatted || (isPrime ? '1.250.000 VNĐ' : '130.000 VNĐ');
    return language === 'en' ? `${usd} (~${vnd})` : `${vnd} (~${usd})`;
  };

  const formatProvider = (provider) => {
    if (provider === 'paypal_sandbox') return 'PayPal Sandbox';
    if (provider === 'vnpay_sandbox') return 'VNPAY Sandbox';
    if (provider === 'sandbox_simulated' || provider === 'simulated') return t('Thẻ thử nghiệm', 'Simulated Card');
    return provider || t('Thanh toán thử nghiệm', 'Sandbox Payment');
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return <span className="history-badge badge-status-success">{t('Thành công', 'Completed')}</span>;
      case 'pending':
        return <span className="history-badge badge-status-pending">{t('Đang xử lý', 'Pending')}</span>;
      case 'failed':
        return <span className="history-badge badge-status-failed">{t('Thất bại', 'Failed')}</span>;
      case 'cancelled':
        return <span className="history-badge badge-status-cancelled">{t('Đã hủy', 'Cancelled')}</span>;
      default:
        return <span className="history-badge badge-status-cancelled">{status || '—'}</span>;
    }
  };

  const getTierBadge = (tier) => {
    const isPrime = tier === 'prime';
    return (
      <span className={`history-badge ${isPrime ? 'badge-tier-prime' : 'badge-tier-plus'}`}>
        <span className="material-symbols-outlined" style={{ fontSize: '13px', marginRight: '3px' }} aria-hidden="true">
          {isPrime ? 'diamond' : 'workspace_premium'}
        </span>
        {isPrime ? 'Aura Prime' : 'Aura Plus'}
      </span>
    );
  };

  return (
    <main className="payment-history-page" style={{ minHeight: 'calc(100vh - 120px)' }}>
      <div className="history-container">
        {/* Navigation Bar */}
        <div className="history-nav">
          <a href="/premium" className="history-back-btn">
            <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
            {t('Quay lại gói hội viên', 'Back to memberships')}
          </a>
        </div>

        {/* Page Title & Intro */}
        <div className="history-header">
          <div className="history-title-group">
            <div className="history-icon-badge">
              <span className="material-symbols-outlined" aria-hidden="true">receipt_long</span>
            </div>
            <div>
              <h1 className="history-title">{t('Lịch sử thanh toán & biên lai', 'Payment History & Receipts')}</h1>
              <p className="history-subtitle">
                {t(
                  'Xem chi tiết tất cả giao dịch nâng cấp hội viên và tải lại biên lai PDF chính thức.',
                  'View all membership upgrade transactions and re-download official PDF receipts.'
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Current Active Plan Banner */}
        {subscription && subscription.is_active && (
          <div className={`history-active-banner history-active-banner--${subscription.tier}`}>
            <span className="material-symbols-outlined" aria-hidden="true">
              {subscription.tier === 'prime' ? 'diamond' : 'workspace_premium'}
            </span>
            <div className="history-active-info">
              <strong>
                {t('Gói hội viên đang hoạt động:', 'Active Membership:')}{' '}
                {subscription.tier === 'prime' ? 'Aura Prime' : 'Aura Plus'}
              </strong>
              <span>
                {t(`Còn lại ${subscription.days_remaining} ngày`, `${subscription.days_remaining} days remaining`)}
                {subscription.expires_at ? ` · ${t('Hết hạn:', 'Expires:')} ${formatDate(subscription.expires_at)}` : ''}
              </span>
            </div>
          </div>
        )}

        {/* Download Success Toast Notice */}
        {downloadSuccess && (
          <div className="history-toast" role="status" aria-live="polite">
            <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
            <span>{t(`Đã tải biên lai cho đơn hàng ${downloadSuccess}`, `Receipt downloaded for order ${downloadSuccess}`)}</span>
          </div>
        )}

        {/* Content States */}
        {loading ? (
          <div className="history-loading">
            <span className="history-spinner" aria-hidden="true" />
            <p>{t('Đang tải lịch sử giao dịch...', 'Loading transaction history...')}</p>
          </div>
        ) : error ? (
          <div className="history-error" role="alert">
            <span className="material-symbols-outlined" aria-hidden="true">error</span>
            <p>{error}</p>
            <button type="button" onClick={loadData} className="history-retry-btn">
              {t('Thử lại', 'Retry')}
            </button>
          </div>
        ) : orders.length === 0 ? (
          <div className="history-empty">
            <div className="history-empty-icon">
              <span className="material-symbols-outlined" aria-hidden="true">inbox</span>
            </div>
            <h3>{t('Chưa có giao dịch nào', 'No transactions found')}</h3>
            <p>
              {t(
                'Bạn chưa thực hiện giao dịch mua gói hội viên nào trên hệ thống thử nghiệm.',
                'You have not completed any membership purchases on the sandbox system yet.'
              )}
            </p>
            <a href="/premium" className="history-empty-cta">
              <span className="material-symbols-outlined" aria-hidden="true">workspace_premium</span>
              {t('Khám phá gói hội viên', 'Explore memberships')}
            </a>
          </div>
        ) : (
          <div className="history-content">
            {/* Desktop Table View */}
            <div className="history-table-wrapper">
              <table className="history-table" aria-label={t('Bảng lịch sử thanh toán', 'Payment history table')}>
                <thead>
                  <tr>
                    <th>{t('MÃ ĐƠN HÀNG', 'ORDER CODE')}</th>
                    <th>{t('NGÀY GIAO DỊCH', 'DATE')}</th>
                    <th>{t('GÓI HỘI VIÊN', 'TIER')}</th>
                    <th>{t('SỐ TIỀN', 'AMOUNT')}</th>
                    <th>{t('PHƯƠNG THỨC', 'METHOD')}</th>
                    <th>{t('TRẠNG THÁI', 'STATUS')}</th>
                    <th style={{ textAlign: 'right' }}>{t('THAO TÁC', 'ACTIONS')}</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.order_code || o.id} className="history-row">
                      <td className="history-td-code">
                        <code>{o.order_code}</code>
                      </td>
                      <td className="history-td-date">{formatDate(o.completed_at || o.created_at)}</td>
                      <td>{getTierBadge(o.tier)}</td>
                      <td className="history-td-amount">
                        <strong>{formatAmount(o)}</strong>
                      </td>
                      <td className="history-td-provider">{formatProvider(o.provider)}</td>
                      <td>{getStatusBadge(o.status)}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="history-actions-cell">
                          <button
                            type="button"
                            className="history-action-btn"
                            onClick={() => handleOpenDetail(o)}
                            title={t('Xem chi tiết đơn hàng', 'View order details')}
                          >
                            <span className="material-symbols-outlined" aria-hidden="true">visibility</span>
                            {t('Chi tiết', 'Details')}
                          </button>
                          {o.status === 'success' && (
                            <button
                              type="button"
                              className="history-action-btn history-action-btn--download"
                              onClick={(e) => handleDownloadPdf(o, e)}
                              title={t('Tải biên lai PDF chính thức', 'Download official PDF receipt')}
                            >
                              <span className="material-symbols-outlined" aria-hidden="true">download</span>
                              {t('Tải biên lai', 'Receipt')}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards View */}
            <div className="history-cards-list">
              {orders.map((o) => (
                <div key={o.order_code || o.id} className="history-card">
                  <div className="history-card-header">
                    <div>
                      <span className="history-card-code">{o.order_code}</span>
                      <div className="history-card-date">{formatDate(o.completed_at || o.created_at)}</div>
                    </div>
                    <div>{getStatusBadge(o.status)}</div>
                  </div>

                  <div className="history-card-body">
                    <div className="history-card-field">
                      <span>{t('Gói:', 'Tier:')}</span>
                      {getTierBadge(o.tier)}
                    </div>
                    <div className="history-card-field">
                      <span>{t('Số tiền:', 'Amount:')}</span>
                      <strong>{formatAmount(o)}</strong>
                    </div>
                    <div className="history-card-field">
                      <span>{t('Phương thức:', 'Method:')}</span>
                      <span>{formatProvider(o.provider)}</span>
                    </div>
                  </div>

                  <div className="history-card-actions">
                    <button
                      type="button"
                      className="history-action-btn"
                      onClick={() => handleOpenDetail(o)}
                    >
                      <span className="material-symbols-outlined" aria-hidden="true">visibility</span>
                      {t('Xem chi tiết', 'Details')}
                    </button>
                    {o.status === 'success' && (
                      <button
                        type="button"
                        className="history-action-btn history-action-btn--download"
                        onClick={(e) => handleDownloadPdf(o, e)}
                      >
                        <span className="material-symbols-outlined" aria-hidden="true">download</span>
                        {t('Tải biên lai PDF', 'PDF Receipt')}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Order Details Modal */}
      <dialog
        ref={dialogRef}
        className="u081-dialog history-detail-modal"
        aria-labelledby="history-detail-title"
        onClose={handleCloseDetail}
      >
        {selectedOrder && (
          <div className="u081-container">
            <div className="u081-header">
              <div className="u081-header-title-wrap">
                <span className="material-symbols-outlined u081-header-icon" aria-hidden="true">
                  receipt
                </span>
                <h2 id="history-detail-title">{t('Chi tiết giao dịch', 'Transaction Details')}</h2>
              </div>
              <button
                type="button"
                className="u081-close-btn"
                onClick={handleCloseDetail}
                aria-label={t('Đóng', 'Close')}
              >
                ×
              </button>
            </div>

            <div className="u081-summary" style={{ gap: '10px' }}>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Mã đơn hàng', 'Order Code')}</span>
                <span className="history-detail-value"><code>{selectedOrder.order_code}</code></span>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Gói hội viên', 'Membership Tier')}</span>
                <span className="u081-row-val">{getTierBadge(selectedOrder.tier)}</span>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Thời hạn', 'Duration')}</span>
                <strong className="u081-row-val">
                  {selectedOrder.duration_days || (selectedOrder.tier === 'prime' ? 365 : 30)} {t('ngày', 'days')}
                </strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Số tiền thanh toán', 'Total Amount')}</span>
                <strong className="u081-row-val u081-price-primary">
                  {formatAmount(selectedOrder)}
                </strong>
              </div>
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Cổng thanh toán', 'Provider')}</span>
                <span className="u081-row-val">{formatProvider(selectedOrder.provider)}</span>
              </div>
              {selectedOrder.provider_txn_id && (
                <div className="u081-summary-row">
                  <span className="u081-row-label">{t('Mã giao dịch / Ref', 'Txn Reference')}</span>
                  <span className="history-detail-value"><code>{selectedOrder.provider_txn_id}</code></span>
                </div>
              )}
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Thời gian tạo', 'Created At')}</span>
                <span className="u081-row-val">{formatDate(selectedOrder.created_at)}</span>
              </div>
              {selectedOrder.completed_at && (
                <div className="u081-summary-row">
                  <span className="u081-row-label">{t('Thời gian hoàn tất', 'Completed At')}</span>
                  <span className="u081-row-val">{formatDate(selectedOrder.completed_at)}</span>
                </div>
              )}
              <div className="u081-summary-row">
                <span className="u081-row-label">{t('Trạng thái', 'Status')}</span>
                <span className="u081-row-val">{getStatusBadge(selectedOrder.status)}</span>
              </div>
            </div>

            <div className="u081-actions" style={{ marginTop: '16px' }}>
              <button
                type="button"
                className="u081-btn-cancel"
                onClick={handleCloseDetail}
              >
                {t('Đóng', 'Close')}
              </button>
              {selectedOrder.status === 'success' && (
                <button
                  type="button"
                  className="u081-btn-confirm"
                  onClick={(e) => handleDownloadPdf(selectedOrder, e)}
                  style={{ gap: '8px' }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '18px' }} aria-hidden="true">download</span>
                  {t('Tải biên lai PDF', 'Download PDF Receipt')}
                </button>
              )}
            </div>
          </div>
        )}
      </dialog>
    </main>
  );
}
