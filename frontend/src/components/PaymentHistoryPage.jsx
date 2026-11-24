import React, { useState, useEffect, useRef } from 'react';
import { auth } from '../auth.js';
import { readPreferences } from '../preferences.js';
import { downloadOwnReceipt } from '../receipt-pdf.js';
import '../payment-ring-081.css';

export default function PaymentHistoryPage() {
  const [orders, setOrders] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterMenuOpen, setFilterMenuOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [downloadSuccess, setDownloadSuccess] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const dialogRef = useRef(null);
  const filterDropdownRef = useRef(null);
  const reqIdRef = useRef(0);

  const prefs = readPreferences();
  const language = prefs.language || 'vi';
  const t = (vi, en) => (language === 'en' ? en : vi);

  const filterOptions = [
    { id: '', vi: 'Tất cả', en: 'All' },
    { id: 'success', vi: 'Thành công', en: 'Completed' },
    { id: 'pending', vi: 'Chờ thanh toán', en: 'Pending' },
    { id: 'processing', vi: 'Đang xác nhận', en: 'Confirming' },
    { id: 'failed', vi: 'Thất bại', en: 'Failed' },
    { id: 'cancelled', vi: 'Đã hủy', en: 'Cancelled' },
    { id: 'expired', vi: 'Hết hạn', en: 'Expired' },
  ];

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Click outside and Escape key to close filter dropdown
  useEffect(() => {
    if (!filterMenuOpen) return;
    const handleClickOutside = (e) => {
      if (filterDropdownRef.current && !filterDropdownRef.current.contains(e.target)) {
        setFilterMenuOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setFilterMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [filterMenuOpen]);

  const loadData = async () => {
    const curReqId = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams({
        page: String(page),
        limit: String(pageSize),
      });
      if (statusFilter && statusFilter !== 'all') {
        queryParams.set('status', statusFilter);
      }
      if (searchQuery) {
        queryParams.set('q', searchQuery);
      }

      const [ordersRes, statusRes] = await Promise.all([
        auth.read(`/premium/orders?${queryParams.toString()}`).catch(err => {
          console.error('Failed to fetch orders:', err);
          throw err;
        }),
        auth.read('/premium/status').catch(() => null),
      ]);

      // Ignore out-of-order responses
      if (curReqId !== reqIdRef.current) return;

      const items = Array.isArray(ordersRes) ? ordersRes : (ordersRes.items || []);
      const pagination = ordersRes.pagination || {
        page: page,
        page_size: pageSize,
        total: items.length,
        total_pages: Math.max(1, Math.ceil(items.length / pageSize)),
      };

      setOrders(items);
      setTotalPages(pagination.total_pages || 1);
      setTotalItems(pagination.total ?? items.length);

      if (statusRes && statusRes.subscription) {
        setSubscription(statusRes.subscription);
      }
    } catch (err) {
      if (curReqId !== reqIdRef.current) return;
      setError(err.message || t('Không thể tải lịch sử giao dịch.', 'Unable to load payment history.'));
    } finally {
      if (curReqId === reqIdRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadData();
  }, [page, statusFilter, searchQuery, language]);

  const handleSelectStatus = (filterId) => {
    setStatusFilter(filterId);
    setPage(1);
    setFilterMenuOpen(false);
  };

  const handleClearSearch = () => {
    setSearchInput('');
    setSearchQuery('');
    setPage(1);
  };

  const handleClearAll = () => {
    setSearchInput('');
    setSearchQuery('');
    setStatusFilter('');
    setPage(1);
  };

  const activeOption = filterOptions.find(opt => (statusFilter || '') === opt.id) || filterOptions[0];
  const isFilterActive = Boolean(statusFilter && statusFilter !== 'all');

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

  const handleDownloadPdf = async (order, e) => {
    if (e) e.stopPropagation();
    try {
      await downloadOwnReceipt(auth, order.order_code);
      setDownloadSuccess(order.order_code);
      setTimeout(() => setDownloadSuccess(null), 3000);
    } catch {
      handleCloseDetail();
      setError(t('Không thể tải biên lai và lịch sử đầy đủ. Vui lòng thử lại.', 'Unable to load receipt and payment history. Please retry.'));
    }
  };

  const canResume = order => order.status === 'pending' && Date.now() < new Date(order.created_at).getTime() + 3600000;
  const resumePayment = async order => {
    try {
      const current = await auth.read('/premium/orders/' + encodeURIComponent(order.order_code));
      if (canResume(current) && current.owner_username === auth.snapshot().user?.username) {
        location.assign('/premium/checkout?order=' + encodeURIComponent(current.order_code));
        return;
      }
      handleCloseDetail();
      await loadData();
      setError(t('Đơn không còn có thể thanh toán. Kiểm tra trạng thái hoặc chọn mua lại.', 'This order cannot be paid. Check its status or purchase again.'));
    } catch {
      handleCloseDetail();
      setError(t('Chưa thể xác minh đơn hàng. Vui lòng thử lại.', 'Unable to verify order. Please retry.'));
    }
  };
  const resumeButton = (order, iconOnly = true) => canResume(order) && (
    <button type="button" className={iconOnly ? 'history-action-btn' : 'u081-btn-confirm'}
      onClick={() => resumePayment(order)} title={t('Tiếp tục thanh toán', 'Continue payment')}
      aria-label={t('Tiếp tục thanh toán', 'Continue payment')}>
      <span className="material-symbols-outlined" aria-hidden="true">payment</span>
      {!iconOnly && t('Tiếp tục thanh toán', 'Continue payment')}
    </button>
  );

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

  const formatProvider = (orderOrProvider) => {
    const provider = typeof orderOrProvider === 'object' ? orderOrProvider?.provider : orderOrProvider;
    const txnId = typeof orderOrProvider === 'object' ? (orderOrProvider?.provider_txn_id || '') : '';

    if (!provider || provider === 'unselected') {
      return t('Chưa chọn', 'Not selected');
    }
    if (provider === 'sandbox_simulated' || provider === 'simulated' || txnId.startsWith('SIM-CARD-')) {
      return t('Thẻ', 'Card');
    }
    if (provider === 'paypal_sandbox') return 'PayPal';
    if (provider === 'vnpay_sandbox') {
      return 'VNPAY';
    }
    return provider ? String(provider) : t('Chưa xác định', 'Unknown');
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'success':
      case 'completed':
        return <span className="history-badge badge-status-success">{t('Thành công', 'Completed')}</span>;
      case 'processing':
        return <span className="history-badge badge-status-processing">{t('Đang xác nhận', 'Confirming')}</span>;
      case 'pending':
        return <span className="history-badge badge-status-pending">{t('Chờ thanh toán', 'Pending')}</span>;
      case 'failed':
        return <span className="history-badge badge-status-failed">{t('Thất bại', 'Failed')}</span>;
      case 'cancelled':
        return <span className="history-badge badge-status-cancelled">{t('Đã hủy', 'Cancelled')}</span>;
      case 'expired':
        return <span className="history-badge badge-status-expired">{t('Hết hạn', 'Expired')}</span>;
      default:
        return <span className="history-badge badge-status-cancelled">{status || '—'}</span>;
    }
  };

  const getStatusDetailText = (status) => {
    switch (status) {
      case 'pending':
        return t('Đang chờ bạn hoàn tất thanh toán.', 'Waiting for you to complete payment.');
      case 'processing':
        return t('Đang chờ PayPal xác nhận giao dịch.', 'Waiting for PayPal to confirm transaction.');
      case 'success':
      case 'completed':
        return t('Giao dịch đã hoàn tất và quyền lợi hội viên đã được kích hoạt.', 'Transaction completed and membership activated.');
      case 'failed':
        return t('Giao dịch không thành công hoặc bị cổng thanh toán từ chối.', 'Transaction failed or was declined.');
      case 'cancelled':
        return t('Đơn hàng đã được hủy bởi người dùng.', 'Order was cancelled by user.');
      case 'expired':
        return t('Đơn hàng đã quá hạn thanh toán.', 'Order has expired.');
      default:
        return '';
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

        {/* Search & Filter Toolbar */}
        <div className="history-toolbar">
          {/* Search Box */}
          <div className="history-search-wrap">
            <span className="material-symbols-outlined history-search-icon" aria-hidden="true">
              search
            </span>
            <input
              type="text"
              className="history-search-input"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t('Tìm mã đơn hàng...', 'Search order code...')}
              aria-label={t('Tìm kiếm theo mã đơn hàng', 'Search by order code')}
              maxLength={64}
            />
            {searchInput && (
              <button
                type="button"
                className="history-search-clear"
                onClick={handleClearSearch}
                title={t('Xóa tìm kiếm', 'Clear search')}
                aria-label={t('Xóa tìm kiếm', 'Clear search')}
              >
                <span className="material-symbols-outlined" aria-hidden="true">close</span>
              </button>
            )}
          </div>

          {/* Filter Popover Button & Menu */}
          <div className="history-filter-menu-wrap" ref={filterDropdownRef}>
            <button
              type="button"
              className={`history-filter-btn ${isFilterActive ? 'history-filter-btn--active' : ''}`}
              onClick={() => setFilterMenuOpen((prev) => !prev)}
              title={t('Lọc giao dịch', 'Filter transactions')}
              aria-label={t('Lọc giao dịch', 'Filter transactions')}
              aria-haspopup="listbox"
              aria-expanded={filterMenuOpen}
            >
              <span className="material-symbols-outlined" aria-hidden="true">filter_list</span>
              <span className="history-filter-btn-text">
                {language === 'en' ? activeOption.en : activeOption.vi}
              </span>
              {isFilterActive && <span className="history-filter-active-dot" aria-hidden="true" />}
              <span className="material-symbols-outlined history-filter-arrow" aria-hidden="true">
                {filterMenuOpen ? 'arrow_drop_up' : 'arrow_drop_down'}
              </span>
            </button>

            {filterMenuOpen && (
              <div
                className="history-filter-dropdown"
                role="listbox"
                aria-label={t('Lọc theo trạng thái', 'Filter by status')}
              >
                <div className="history-filter-dropdown-header">
                  <span>{t('Trạng thái đơn hàng', 'Order Status')}</span>
                </div>
                {filterOptions.map((opt) => {
                  const isSelected = (statusFilter || '') === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      className={`history-filter-item ${isSelected ? 'history-filter-item--selected' : ''}`}
                      onClick={() => handleSelectStatus(opt.id)}
                    >
                      <span className="history-filter-item-label">
                        {language === 'en' ? opt.en : opt.vi}
                      </span>
                      {isSelected && (
                        <span className="material-symbols-outlined history-filter-check" aria-hidden="true">
                          check
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

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
              <span className="material-symbols-outlined" aria-hidden="true">
                {searchQuery || isFilterActive ? 'search_off' : 'inbox'}
              </span>
            </div>
            <h3>
              {searchQuery || isFilterActive
                ? t('Không tìm thấy giao dịch phù hợp', 'No matching transactions found')
                : t('Chưa có giao dịch nào', 'No transactions found')}
            </h3>
            <p>
              {searchQuery || isFilterActive
                ? t(
                    'Không tìm thấy kết quả nào phù hợp với điều kiện tìm kiếm hoặc bộ lọc hiện tại.',
                    'No results found matching your current search query or status filter.'
                  )
                : t(
                    'Bạn chưa thực hiện giao dịch mua gói hội viên nào trên hệ thống thử nghiệm.',
                    'You have not completed any membership purchases on the sandbox system yet.'
                  )}
            </p>
            {searchQuery || isFilterActive ? (
              <button
                type="button"
                className="history-clear-all-btn"
                onClick={handleClearAll}
              >
                <span className="material-symbols-outlined" aria-hidden="true">clear_all</span>
                {t('Xóa tìm kiếm & bộ lọc', 'Clear search & filter')}
              </button>
            ) : (
              <a href="/premium" className="history-empty-cta">
                <span className="material-symbols-outlined" aria-hidden="true">workspace_premium</span>
                {t('Khám phá gói hội viên', 'Explore memberships')}
              </a>
            )}
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
                      <td className="history-td-provider">{formatProvider(o)}</td>
                      <td>{getStatusBadge(o.status)}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="history-actions-cell">
                          <button
                            type="button"
                            className="history-action-btn"
                            onClick={() => handleOpenDetail(o)}
                            title={t('Xem chi tiết', 'View details')}
                            aria-label={t('Xem chi tiết', 'View details')}
                          >
                            <span className="material-symbols-outlined" aria-hidden="true">visibility</span>
                          </button>
                          {resumeButton(o)}
                          {(o.status === 'success' || o.status === 'completed') && (
                            <button
                              type="button"
                              className="history-action-btn history-action-btn--download"
                              onClick={(e) => handleDownloadPdf(o, e)}
                              title={t('Tải biên lai', 'Download receipt')}
                              aria-label={t('Tải biên lai', 'Download receipt')}
                            >
                              <span className="material-symbols-outlined" aria-hidden="true">download</span>
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
                      <span>{formatProvider(o)}</span>
                    </div>
                  </div>

                  <div className="history-card-actions">
                    <button
                      type="button"
                      className="history-action-btn"
                      onClick={() => handleOpenDetail(o)}
                      title={t('Xem chi tiết', 'View details')}
                      aria-label={t('Xem chi tiết', 'View details')}
                    >
                      <span className="material-symbols-outlined" aria-hidden="true">visibility</span>
                    </button>
                    {resumeButton(o)}
                          {(o.status === 'success' || o.status === 'completed') && (
                      <button
                        type="button"
                        className="history-action-btn history-action-btn--download"
                        onClick={(e) => handleDownloadPdf(o, e)}
                        title={t('Tải biên lai', 'Download receipt')}
                        aria-label={t('Tải biên lai', 'Download receipt')}
                      >
                        <span className="material-symbols-outlined" aria-hidden="true">download</span>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination Controls */}
            <div className="history-pagination-bar">
              <div className="history-pagination-info">
                {t(
                  `Trang ${page} / ${totalPages} · Tổng cộng ${totalItems} giao dịch`,
                  `Page ${page} of ${totalPages} · Total ${totalItems} transactions`
                )}
              </div>
              <div className="history-pagination-controls">
                <button
                  type="button"
                  className="history-page-btn"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  aria-label={t('Trang trước', 'Previous page')}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '16px' }} aria-hidden="true">chevron_left</span>
                  {t('Trước', 'Prev')}
                </button>
                <span style={{ fontSize: '12px', fontFamily: "'JetBrains Mono', monospace", padding: '0 6px' }}>
                  {page} / {totalPages}
                </span>
                <button
                  type="button"
                  className="history-page-btn"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  aria-label={t('Trang sau', 'Next page')}
                >
                  {t('Sau', 'Next')}
                  <span className="material-symbols-outlined" style={{ fontSize: '16px' }} aria-hidden="true">chevron_right</span>
                </button>
              </div>
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
                <span className="u081-row-label">{t('Phương thức', 'Payment Method')}</span>
                <span className="u081-row-val">{formatProvider(selectedOrder)}</span>
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
              {getStatusDetailText(selectedOrder.status) && (
                <div
                  className="u081-summary-row history-detail-note"
                  style={{
                    background: 'rgba(255, 255, 255, 0.035)',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    gap: '4px',
                  }}
                >
                  <span className="u081-row-label" style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {t('Ghi chú trạng thái', 'Status Explanation')}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--am-on-surface-variant, #94a3b8)', lineHeight: '1.4' }}>
                    {getStatusDetailText(selectedOrder.status)}
                  </span>
                </div>
              )}
            </div>

            <div className="u081-actions" style={{ marginTop: '16px' }}>
              <button
                type="button"
                className="u081-btn-cancel"
                onClick={handleCloseDetail}
              >
                {t('Đóng', 'Close')}
              </button>
              {resumeButton(selectedOrder, false)}
              {(selectedOrder.status === 'success' || selectedOrder.status === 'completed') && (
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
