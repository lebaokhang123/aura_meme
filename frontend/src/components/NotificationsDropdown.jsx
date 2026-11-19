import React, { useEffect, useState, useCallback } from 'react';
import { getNotifications, markRead, markAllRead } from '../notifications-api.js';
import { useLocalized } from '../localize.jsx';

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

export function NotificationsDropdown({ onClose, onUnreadChange }) {
  const render = useLocalized();
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState('all'); // 'all' | 'unread'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState(false);

  const load = useCallback(async (isUnreadOnly = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getNotifications({ page: 1, pageSize: 30, unreadOnly: isUnreadOnly });
      setItems(data.items || []);
      const count = typeof data.unread_count === 'number' ? data.unread_count : 0;
      setUnreadCount(count);
      onUnreadChange?.(count);
    } catch (err) {
      setError(err?.message || 'Lỗi khi tải thông báo');
    } finally {
      setLoading(false);
    }
  }, [onUnreadChange]);

  useEffect(() => {
    load(filter === 'unread');
  }, [filter, load]);

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

  const handleClickItem = (notif) => {
    if (!notif.is_read) {
      markRead(notif.id).catch(() => {});
      setItems(prev => prev.map(item => item.id === notif.id ? { ...item, is_read: true } : item));
      onUnreadChange?.(Math.max(0, unreadCount - 1));
    }
    onClose?.();

    if (notif.target_type === 'post' && notif.target_id) {
      location.assign(`/#post-${notif.target_id}`);
    } else if (notif.target_type === 'comment' && notif.payload?.post_id) {
      location.assign(`/#post-${notif.payload.post_id}`);
    }
  };

  const renderContent = (t) => {
    return (
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
            items.map(notif => {
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
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    );
  };

  return render(renderContent);
}
