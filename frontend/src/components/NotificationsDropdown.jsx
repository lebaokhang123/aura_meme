import React, { useEffect, useState, useCallback, useRef } from 'react';
import { getNotifications, markRead, markAllRead, deleteNotification } from '../notifications-api.js';
import { useLocalized } from '../localize.jsx';
import { usePreferences } from '../PreferencesContext.jsx';

const symbol = name => <span className="material-symbols-outlined" aria-hidden="true">{name}</span>;

function formatRelativeTime(dateString, t) {
  try {
    const diff = Math.max(0, Math.floor((Date.now() - Date.parse(dateString)) / 1000));
    if (diff < 60) return t('vừa xong', 'just now');
    if (diff < 3600) return `${Math.floor(diff / 60)} ${t('phút trước', 'm ago')}`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ${t('giờ trước', 'h ago')}`;
    return `${Math.floor(diff / 86400)} ${t('ngày trước', 'd ago')}`;
  } catch {
    return '';
  }
}

function formatFullDateTime(dateString, language) {
  try {
    return new Date(dateString).toLocaleString(language === 'en' ? 'en-US' : 'vi-VN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return dateString || '';
  }
}

export function NotificationsDropdown({ onClose, onUnreadChange }) {
  const render = useLocalized();
  const { language } = usePreferences();
  const t = (vi, en) => language === 'en' ? en : vi;

  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState('all'); // 'all' | 'unread'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [deletingIds, setDeletingIds] = useState(new Set());
  const [selectedNotif, setSelectedNotif] = useState(null);

  const modalRef = useRef(null);
  const lastActiveElementRef = useRef(null);

  const load = useCallback(async (isUnreadOnly = false) => {
    setLoading(true);
    setError(null);
    setPage(1);
    try {
      const data = await getNotifications({ page: 1, pageSize: 20, unreadOnly: isUnreadOnly });
      setItems(data.items || []);
      setTotalPages(data.pagination?.total_pages || 1);
      const count = typeof data.unread_count === 'number' ? data.unread_count : 0;
      setUnreadCount(count);
      onUnreadChange?.(count);
    } catch (err) {
      setError(err?.message || t('Lỗi khi tải thông báo', 'Failed to load notifications'));
    } finally {
      setLoading(false);
    }
  }, [onUnreadChange, t]);

  useEffect(() => {
    load(filter === 'unread');
  }, [filter, load]);

  const handleLoadMore = async () => {
    if (loadingMore || page >= totalPages) return;
    setLoadingMore(true);
    try {
      const nextPage = page + 1;
      const data = await getNotifications({ page: nextPage, pageSize: 20, unreadOnly: filter === 'unread' });
      setItems(prev => [...prev, ...(data.items || [])]);
      setPage(nextPage);
      setTotalPages(data.pagination?.total_pages || 1);
    } catch (err) {
      setError(err?.message || t('Lỗi khi tải thêm', 'Failed to load more'));
    } finally {
      setLoadingMore(false);
    }
  };

  const handleMarkOne = async (e, notif) => {
    e.stopPropagation();
    if (notif.is_read || busyAction) return;
    try {
      setBusyAction(true);
      await markRead(notif.id);
      setItems(prev => prev.map(item => item.id === notif.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item));
      setUnreadCount(prev => {
        const next = Math.max(0, prev - 1);
        onUnreadChange?.(next);
        return next;
      });
    } catch {}
    finally {
      setBusyAction(false);
    }
  };

  const handleMarkAll = async (e) => {
    e.preventDefault();
    if (busyAction || unreadCount === 0) return;
    try {
      setBusyAction(true);
      await markAllRead();
      setItems(prev => prev.map(item => ({ ...item, is_read: true, read_at: new Date().toISOString() })));
      setUnreadCount(0);
      onUnreadChange?.(0);
    } catch {}
    finally {
      setBusyAction(false);
    }
  };

  const handleDeleteOne = async (e, notif) => {
    e.stopPropagation();
    if (deletingIds.has(notif.id) || busyAction) return;
    setDeletingIds(prev => new Set(prev).add(notif.id));
    try {
      await deleteNotification(notif.id);
      setItems(prev => prev.filter(item => item.id !== notif.id));
      if (!notif.is_read) {
        setUnreadCount(prev => {
          const next = Math.max(0, prev - 1);
          onUnreadChange?.(next);
          return next;
        });
      }
      if (selectedNotif?.id === notif.id) {
        setSelectedNotif(null);
      }
    } catch (err) {
      setError(err?.message || t('Lỗi khi xóa thông báo', 'Error deleting notification'));
    } finally {
      setDeletingIds(prev => {
        const next = new Set(prev);
        next.delete(notif.id);
        return next;
      });
    }
  };

  const handleClickItem = (notif) => {
    lastActiveElementRef.current = document.activeElement;
    if (!notif.is_read) {
      markRead(notif.id).catch(() => {});
      setItems(prev => prev.map(item => item.id === notif.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item));
      setUnreadCount(prev => {
        const next = Math.max(0, prev - 1);
        onUnreadChange?.(next);
        return next;
      });
    }
    setSelectedNotif(notif);
  };

  const handleCloseModal = () => {
    setSelectedNotif(null);
    if (lastActiveElementRef.current && typeof lastActiveElementRef.current.focus === 'function') {
      lastActiveElementRef.current.focus();
    }
  };

  // Keyboard navigation and modal escape handling
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (selectedNotif) {
          e.stopPropagation();
          handleCloseModal();
        } else {
          onClose?.();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNotif, onClose]);

  // Trap focus inside modal when open
  useEffect(() => {
    if (selectedNotif && modalRef.current) {
      modalRef.current.focus();
    }
  }, [selectedNotif]);

  return render(
    <>
      <div
        className="notifications-dropdown"
        id="site-notifications-menu"
        role="dialog"
        aria-label={t('Hộp thông báo', 'Notifications Inbox')}
      >
        <div className="notifications-header">
          <div className="notifications-title-area">
            <h3>{t('Thông báo', 'Notifications')}</h3>
            {unreadCount > 0 && (
              <span className="notifications-unread-pill">
                {unreadCount} {t('mới', 'new')}
              </span>
            )}
          </div>
          <div className="notifications-header-actions">
            {unreadCount > 0 && (
              <button
                type="button"
                className="notifications-mark-all-btn"
                onClick={handleMarkAll}
                disabled={busyAction}
                title={t('Đánh dấu tất cả đã đọc', 'Mark all as read')}
              >
                {symbol('done_all')}
                <span>{t('Đọc tất cả', 'Mark all read')}</span>
              </button>
            )}
          </div>
        </div>

        <div className="notifications-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'all'}
            className={`notifications-tab${filter === 'all' ? ' active' : ''}`}
            onClick={() => setFilter('all')}
          >
            {t('Tất cả', 'All')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'unread'}
            className={`notifications-tab${filter === 'unread' ? ' active' : ''}`}
            onClick={() => setFilter('unread')}
          >
            {t('Chưa đọc', 'Unread')}
          </button>
        </div>

        <div className="notifications-list" role="feed">
          {loading ? (
            <div className="notifications-loading">
              <span className="notifications-spinner" aria-hidden="true"></span>
              <p>{t('Đang tải thông báo...', 'Loading notifications...')}</p>
            </div>
          ) : error ? (
            <div className="notifications-error">
              {symbol('error')}
              <p>{error}</p>
              <button type="button" onClick={() => load(filter === 'unread')}>
                {t('Thử lại', 'Retry')}
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="notifications-empty">
              {symbol('notifications_off')}
              <p>
                {filter === 'unread'
                  ? t('Không có thông báo chưa đọc.', 'No unread notifications.')
                  : t('Chưa có thông báo nào.', 'No notifications yet.')}
              </p>
            </div>
          ) : (
            <>
              {items.map(notif => {
                const actor = notif.actor;
                const title = notif.payload?.title;
                const body = notif.payload?.body;
                const reactionType = notif.payload?.reaction_type;
                const postTitle = notif.payload?.post_title;
                const reason = notif.payload?.reason;

                let message = '';
                let iconName = 'notifications';

                if (notif.type === 'reaction') {
                  iconName = reactionType === 'fire' ? 'local_fire_department' : 'favorite';
                  message = t(
                    `đã thả biểu cảm ${reactionType ? `(${reactionType})` : ''} vào bài viết của bạn`,
                    `reacted to your post`
                  );
                } else if (notif.type === 'comment') {
                  iconName = 'chat_bubble';
                  message = t('đã bình luận vào bài viết của bạn', 'commented on your post');
                } else if (notif.type === 'moderation') {
                  iconName = 'shield';
                  message = t('Nội dung của bạn đã được kiểm duyệt bởi Quản trị viên', 'Your content was moderated by an Administrator');
                } else if (notif.type === 'announcement') {
                  iconName = 'campaign';
                  message = title || t('Thông báo từ Hệ Thống AuraMeme', 'Announcement from AuraMeme System');
                }

                return (
                  <div
                    key={notif.id}
                    className={`notification-item${notif.is_read ? ' is-read' : ' is-unread'}`}
                    onClick={() => handleClickItem(notif)}
                    role="article"
                    tabIndex={0}
                    onKeyDown={e => {
                      if (e.key === 'Enter') handleClickItem(notif);
                    }}
                  >
                    <div className="notification-avatar-area">
                      {actor?.avatar_url ? (
                        <img
                          src={actor.avatar_url}
                          alt={actor.display_name}
                          className="notification-avatar"
                          width="36"
                          height="36"
                        />
                      ) : (
                        <div className="notification-icon-placeholder">
                          {symbol(iconName)}
                        </div>
                      )}
                      <span className={`notification-type-badge type-${notif.type}`}>
                        {symbol(iconName)}
                      </span>
                    </div>

                    <div className="notification-content">
                      <div className="notification-text">
                        {actor && (
                          <strong className="notification-actor">
                            {actor.display_name}{' '}
                          </strong>
                        )}
                        <span>{message}</span>
                      </div>

                      {postTitle && (
                        <p className="notification-preview-title">
                          "{postTitle}"
                        </p>
                      )}

                      {body && (
                        <p className="notification-preview-body">
                          {body}
                        </p>
                      )}

                      {reason && (
                        <p className="notification-reason">
                          <em>{t('Lý do:', 'Reason:')} {reason}</em>
                        </p>
                      )}

                      <span className="notification-time">
                        {formatRelativeTime(notif.created_at, t)}
                      </span>
                    </div>

                    <div className="notification-item-actions">
                      {!notif.is_read && (
                        <button
                          type="button"
                          className="notification-mark-read-btn"
                          onClick={e => handleMarkOne(e, notif)}
                          title={t('Đánh dấu đã đọc', 'Mark as read')}
                          aria-label={t('Đánh dấu đã đọc', 'Mark as read')}
                        >
                          <span className="notification-unread-dot" />
                        </button>
                      )}
                      <button
                        type="button"
                        className="notification-delete-btn"
                        onClick={e => handleDeleteOne(e, notif)}
                        disabled={deletingIds.has(notif.id)}
                        title={t('Xóa thông báo', 'Delete notification')}
                        aria-label={t('Xóa thông báo', 'Delete notification')}
                      >
                        {symbol('delete')}
                      </button>
                    </div>
                  </div>
                );
              })}

              {page < totalPages && (
                <button
                  type="button"
                  className="notifications-load-more"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? t('Đang tải...', 'Loading...') : t('Xem thêm', 'Load more')}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Task A4: Detail Modal */}
      {selectedNotif && (
        <div
          className="notification-modal-backdrop"
          onClick={handleCloseModal}
          role="presentation"
        >
          <div
            ref={modalRef}
            className="notification-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="notification-modal-title"
            tabIndex={-1}
            onClick={e => e.stopPropagation()}
          >
            <div className="notification-modal-header">
              <span className="notification-modal-type-tag">
                {symbol(
                  selectedNotif.type === 'reaction'
                    ? (selectedNotif.payload?.reaction_type === 'fire' ? 'local_fire_department' : 'favorite')
                    : selectedNotif.type === 'comment'
                    ? 'chat_bubble'
                    : selectedNotif.type === 'moderation'
                    ? 'shield'
                    : 'campaign'
                )}
                <span>
                  {selectedNotif.type === 'reaction'
                    ? t('Tương tác', 'Reaction')
                    : selectedNotif.type === 'comment'
                    ? t('Bình luận', 'Comment')
                    : selectedNotif.type === 'moderation'
                    ? t('Kiểm duyệt', 'Moderation')
                    : t('Thông báo hệ thống', 'System Announcement')}
                </span>
              </span>
              <button
                type="button"
                className="notification-modal-close-btn"
                onClick={handleCloseModal}
                aria-label={t('Đóng', 'Close')}
              >
                {symbol('close')}
              </button>
            </div>

            <div className="notification-modal-body">
              {selectedNotif.actor && (
                <div className="notification-modal-actor">
                  {selectedNotif.actor.avatar_url ? (
                    <img
                      src={selectedNotif.actor.avatar_url}
                      alt={selectedNotif.actor.display_name}
                      className="notification-avatar"
                      width="40"
                      height="40"
                    />
                  ) : (
                    <div className="notification-icon-placeholder">
                      {symbol('person')}
                    </div>
                  )}
                  <div className="notification-modal-actor-info">
                    <strong>{selectedNotif.actor.display_name}</strong>
                    <span>@{selectedNotif.actor.username}</span>
                  </div>
                </div>
              )}

              <time className="notification-modal-time">
                {formatFullDateTime(selectedNotif.created_at, language)}
              </time>

              {selectedNotif.payload?.title && (
                <h4 id="notification-modal-title" className="notification-modal-title">
                  {selectedNotif.payload.title}
                </h4>
              )}

              {selectedNotif.payload?.body && (
                <p className="notification-modal-content">
                  {selectedNotif.payload.body}
                </p>
              )}

              {selectedNotif.type === 'reaction' && (
                <p className="notification-modal-content">
                  {t(
                    `Đã thả biểu cảm ${selectedNotif.payload?.reaction_type ? `(${selectedNotif.payload.reaction_type})` : ''} vào bài viết của bạn.`,
                    `Reacted to your post.`
                  )}
                </p>
              )}

              {selectedNotif.type === 'comment' && (
                <p className="notification-modal-content">
                  {t(
                    `Đã để lại bình luận trên bài viết của bạn.`,
                    `Commented on your post.`
                  )}
                </p>
              )}

              {selectedNotif.payload?.reason && (
                <div className="notification-modal-reason">
                  <strong>{t('Lý do kiểm duyệt:', 'Moderation reason:')}</strong>
                  <span>{selectedNotif.payload.reason}</span>
                </div>
              )}

              {selectedNotif.payload?.post_title && (
                <div className="notification-modal-target">
                  <span className="text-xs text-outline font-medium">
                    {t('Bài viết liên quan:', 'Referenced post:')}
                  </span>
                  <p className="notification-modal-target-quote">
                    "{selectedNotif.payload.post_title}"
                  </p>
                </div>
              )}
            </div>

            <div className="notification-modal-footer">
              {(selectedNotif.target_type === 'post' && selectedNotif.target_id) ? (
                <button
                  type="button"
                  className="notification-modal-action-btn"
                  onClick={() => {
                    handleCloseModal();
                    onClose?.();
                    location.assign(`/#post-${selectedNotif.target_id}`);
                  }}
                >
                  {symbol('arrow_outward')}
                  <span>{t('Xem bài viết', 'View post')}</span>
                </button>
              ) : (selectedNotif.target_type === 'comment' && selectedNotif.payload?.post_id) ? (
                <button
                  type="button"
                  className="notification-modal-action-btn"
                  onClick={() => {
                    handleCloseModal();
                    onClose?.();
                    location.assign(`/#post-${selectedNotif.payload.post_id}`);
                  }}
                >
                  {symbol('arrow_outward')}
                  <span>{t('Xem bài viết', 'View post')}</span>
                </button>
              ) : null}

              <button
                type="button"
                className="notification-modal-dismiss-btn"
                onClick={handleCloseModal}
              >
                {t('Đóng', 'Close')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
