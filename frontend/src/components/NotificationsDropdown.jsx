import React, { useEffect, useState, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getNotifications, markRead, markAllRead, deleteNotification } from '../notifications-api.js';
import { useLocalized } from '../localize.jsx';
import { usePreferences } from '../PreferencesContext.jsx';

const symbol = name => <span className="material-symbols-outlined" aria-hidden="true">{name}</span>;

function describeNotification(notif, t) {
  const actor = notif.actor;
  const title = notif.payload?.title;
  const body = notif.payload?.body;
  const reactionType = notif.payload?.reaction_type;
  const postTitle = notif.payload?.post_title;
  const commentText = notif.payload?.comment_body || notif.payload?.comment_text || notif.payload?.content || '';
  const reason = notif.payload?.reason;

  let iconName = 'notifications';
  let actorName = '';
  let notifTitle = '';
  let notifSnippet = '';
  let reasonLabel = t('Lý do kiểm duyệt:', 'Moderation reason:');

  if (notif.type === 'reaction') {
    iconName = reactionType === 'fire' ? 'local_fire_department' : 'favorite';
    actorName = actor?.display_name || actor?.username || t('Thành viên AuraMeme', 'AuraMeme Member');
    if (notif.target_type === 'comment') {
      notifTitle = t('Đã thả biểu cảm vào bình luận của bạn', 'Reacted to your comment');
      notifSnippet = commentText || body || (postTitle ? `"${postTitle}"` : '');
    } else {
      notifTitle = t('Đã thả biểu cảm vào bài viết của bạn', 'Reacted to your post');
      notifSnippet = postTitle ? `"${postTitle}"` : '';
    }
  } else if (notif.type === 'comment') {
    iconName = 'chat_bubble';
    actorName = actor?.display_name || actor?.username || t('Thành viên AuraMeme', 'AuraMeme Member');
    notifTitle = t('Đã bình luận vào bài viết của bạn', 'Commented on your post');
    notifSnippet = commentText || body || (postTitle ? `"${postTitle}"` : '');
  } else if (notif.type === 'follow') {
    iconName = 'person_add';
    actorName = actor?.display_name || actor?.username || t('Thành viên AuraMeme', 'AuraMeme Member');
    notifTitle = t('Đã bắt đầu theo dõi bạn.', 'Started following you.');
    const handle = actor?.username || notif.payload?.follower_username;
    notifSnippet = handle ? `@${handle}` : '';
  } else if (notif.type === 'moderation') {
    iconName = 'shield';
    actorName = actor?.display_name || t('Ban Quản Trị AuraMeme', 'AuraMeme Moderation Team');
    const action = notif.payload?.action;
    if (notif.target_type === 'post' && action === 'hidden') {
      notifTitle = t('Đã ẩn bài viết của bạn.', 'Your post was hidden.');
      reasonLabel = t('Lý do ẩn:', 'Hide reason:');
    } else if (notif.target_type === 'post' && action === 'deleted') {
      notifTitle = t('Đã xóa bài viết của bạn.', 'Your post was deleted.');
      reasonLabel = t('Lý do xóa:', 'Deletion reason:');
    } else if (notif.target_type === 'comment' && action === 'hidden') {
      notifTitle = t('Đã ẩn bình luận của bạn.', 'Your comment was hidden.');
      reasonLabel = t('Lý do ẩn:', 'Hide reason:');
    } else if (notif.target_type === 'comment' && action === 'deleted') {
      notifTitle = t('Đã xóa bình luận của bạn.', 'Your comment was deleted.');
      reasonLabel = t('Lý do xóa:', 'Deletion reason:');
    } else if (action === 'deleted') {
      notifTitle = t('Nội dung đã bị xóa bởi Quản trị viên.', 'Content deleted by Moderator.');
      reasonLabel = t('Lý do xóa:', 'Deletion reason:');
    } else {
      notifTitle = t('Nội dung đã được kiểm duyệt bởi Quản trị viên.', 'Content moderated by Moderator.');
    }
    notifSnippet = reason
      ? `${t('Lý do:', 'Reason:')} ${reason}`
      : (notif.payload?.target_title ? `"${notif.payload.target_title}"` : (commentText || (postTitle ? `"${postTitle}"` : '')));
  } else if (notif.type === 'announcement') {
    iconName = 'campaign';
    actorName = actor?.display_name || t('Hệ thống AuraMeme', 'AuraMeme System');
    notifTitle = title || t('Thông báo từ Hệ Thống AuraMeme', 'Announcement from AuraMeme System');
    notifSnippet = body || '';
  } else {
    actorName = actor?.display_name || t('Hệ thống AuraMeme', 'AuraMeme System');
    notifTitle = title || t('Thông báo', 'Notification');
    notifSnippet = body || '';
  }

  return { iconName, actorName, notifTitle, notifSnippet, commentText, reasonLabel };
}

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
  const t = useCallback((vi, en) => language === 'en' ? en : vi, [language]);
  const languageRef = useRef(language);
  useEffect(() => { languageRef.current = language; }, [language]);

  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
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

  const onUnreadChangeRef = useRef(onUnreadChange);
  useEffect(() => {
    onUnreadChangeRef.current = onUnreadChange;
  }, [onUnreadChange]);

  const activeRequestIdRef = useRef(0);
  const cooldownUntilRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++activeRequestIdRef.current;
    const now = Date.now();
    if (now < cooldownUntilRef.current) {
      const remaining = Math.ceil((cooldownUntilRef.current - now) / 1000);
      setError(languageRef.current === 'en'
        ? `Too many attempts. Please wait ${remaining}s.`
        : `Quá nhiều lần thử. Vui lòng đợi ${remaining} giây.`);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setPage(1);
    try {
      const data = await getNotifications({ page: 1, pageSize: 20 });
      if (requestId !== activeRequestIdRef.current) return;
      setItems(data.items || []);
      setTotalPages(data.pagination?.total_pages || 1);
      const count = typeof data.unread_count === 'number' ? data.unread_count : 0;
      setUnreadCount(count);
      onUnreadChangeRef.current?.(count);
    } catch (err) {
      if (requestId !== activeRequestIdRef.current) return;
      if (err?.status === 429) {
        const retrySec = err.retryAfter && err.retryAfter > 0 ? err.retryAfter : 15;
        cooldownUntilRef.current = Date.now() + retrySec * 1000;
        setError(languageRef.current === 'en'
          ? `Too many attempts. Please wait ${retrySec}s.`
          : `Quá nhiều lần thử. Vui lòng đợi ${retrySec} giây.`);
      } else {
        setError(err?.message || (languageRef.current === 'en' ? 'Failed to load notifications' : 'Lỗi khi tải thông báo'));
      }
    } finally {
      if (requestId === activeRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    load();
    return () => {
      activeRequestIdRef.current++;
    };
  }, [load]);

  const handleLoadMore = async () => {
    if (loadingMore || page >= totalPages) return;
    const now = Date.now();
    if (now < cooldownUntilRef.current) {
      const remaining = Math.ceil((cooldownUntilRef.current - now) / 1000);
      setError(languageRef.current === 'en'
        ? `Too many attempts. Please wait ${remaining}s.`
        : `Quá nhiều lần thử. Vui lòng đợi ${remaining} giây.`);
      return;
    }
    setLoadingMore(true);
    try {
      const nextPage = page + 1;
      const data = await getNotifications({ page: nextPage, pageSize: 20 });
      setItems(prev => [...prev, ...(data.items || [])]);
      setPage(nextPage);
      setTotalPages(data.pagination?.total_pages || 1);
    } catch (err) {
      if (err?.status === 429) {
        const retrySec = err.retryAfter && err.retryAfter > 0 ? err.retryAfter : 15;
        cooldownUntilRef.current = Date.now() + retrySec * 1000;
        setError(languageRef.current === 'en'
          ? `Too many attempts. Please wait ${retrySec}s.`
          : `Quá nhiều lần thử. Vui lòng đợi ${retrySec} giây.`);
      } else {
        setError(err?.message || (languageRef.current === 'en' ? 'Failed to load more' : 'Lỗi khi tải thêm'));
      }
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
              <button type="button" onClick={() => {
                if (Date.now() < cooldownUntilRef.current) {
                  const remaining = Math.ceil((cooldownUntilRef.current - Date.now()) / 1000);
                  setError(language === 'en'
                    ? `Too many attempts. Please wait ${remaining}s.`
                    : `Quá nhiều lần thử. Vui lòng đợi ${remaining} giây.`);
                  return;
                }
                load();
              }}>
                {t('Thử lại', 'Retry')}
              </button>
            </div>
          ) : items.length === 0 ? (
            <div className="notifications-empty">
              {symbol('notifications_off')}
              <p>
                {t('Chưa có thông báo nào.', 'No notifications yet.')}
              </p>
            </div>
          ) : (
            <>
              {items.map(notif => {
                const actor = notif.actor;
                const { iconName, actorName, notifTitle, notifSnippet } = describeNotification(notif, t);

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
                      <span className="notification-card-actor notification-actor" translate="no">
                        {actorName}
                      </span>
                      <strong className="notification-card-title">
                        {notifTitle}
                      </strong>
                      {notifSnippet ? (
                        <span className="notification-card-snippet" translate="no">
                          {notifSnippet}
                        </span>
                      ) : null}
                      <time className="notification-card-time notification-time" dateTime={notif.created_at}>
                        {formatRelativeTime(notif.created_at, t)}
                      </time>
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

      {/* Task B: Detail Modal mounted via Portal into document.body */}
      {selectedNotif && typeof document !== 'undefined' && createPortal(
        <div
          className="notification-modal-backdrop"
          data-header-popup="notifications"
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
                    : selectedNotif.type === 'follow'
                    ? 'person_add'
                    : 'campaign'
                )}
                <span>
                  {selectedNotif.type === 'reaction'
                    ? t('Tương tác', 'Reaction')
                    : selectedNotif.type === 'comment'
                    ? t('Bình luận', 'Comment')
                    : selectedNotif.type === 'moderation'
                    ? t('Kiểm duyệt', 'Moderation')
                    : selectedNotif.type === 'follow'
                    ? t('Theo dõi', 'Follow')
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

              {(() => {
                const desc = describeNotification(selectedNotif, t);
                return (
                  <>
                    {(selectedNotif.type === 'reaction' || selectedNotif.type === 'comment' || selectedNotif.type === 'moderation' || selectedNotif.type === 'follow') && (
                      <p className="notification-modal-content">
                        {desc.notifTitle}
                      </p>
                    )}
                    {desc.commentText && (
                      <div className="notification-modal-target">
                        <span className="text-xs text-outline font-medium">
                          {t('Nội dung bình luận:', 'Comment content:')}
                        </span>
                        <p className="notification-modal-target-quote">
                          "{desc.commentText}"
                        </p>
                      </div>
                    )}
                    {selectedNotif.payload?.reason && (
                      <div className="notification-modal-reason">
                        <strong>{desc.reasonLabel}</strong>
                        <span>{selectedNotif.payload.reason}</span>
                      </div>
                    )}
                  </>
                );
              })()}

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
              {selectedNotif.type === 'follow' && (selectedNotif.actor?.username || selectedNotif.payload?.follower_username) ? (
                <button
                  type="button"
                  className="notification-modal-action-btn"
                  onClick={() => {
                    const uname = selectedNotif.actor?.username || selectedNotif.payload?.follower_username;
                    handleCloseModal();
                    onClose?.();
                    location.assign(`/u/${encodeURIComponent(uname)}`);
                  }}
                >
                  {symbol('arrow_outward')}
                  <span>{t('Xem trang cá nhân', 'View profile')}</span>
                </button>
              ) : (selectedNotif.target_type === 'post' && selectedNotif.target_id && selectedNotif.type !== 'moderation') ? (
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
        </div>,
        document.body
      )}</>
  );
}
