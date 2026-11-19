import { auth, MOCK_AUTH } from './auth.js';

const MOCK_KEY = 'aurameme-mock-notifications';

const DEFAULT_MOCK = [
  {
    id: 'notif-mock-1',
    type: 'announcement',
    target_type: 'system',
    target_id: null,
    actor: {
      id: 'system',
      username: 'aurameme_admin',
      display_name: 'Hệ Thống AuraMeme',
      avatar_url: '/assets/brand/favicon-64.png'
    },
    payload: {
      title: 'Chào mừng chư vị Đạo hữu!',
      body: 'Hệ thống Thông Báo Cá Nhân của AuraMeme đã chính thức hoạt động. Đạo hữu sẽ nhận được tin tức khi có tương tác mới!'
    },
    created_at: new Date(Date.now() - 3600000).toISOString(),
    read_at: null,
    is_read: false
  },
  {
    id: 'notif-mock-2',
    type: 'reaction',
    target_type: 'post',
    target_id: 'p-1',
    actor: {
      id: 'khang_dev',
      username: 'khang_dev',
      display_name: 'Khang Dev',
      avatar_url: '/assets/brand/favicon-64.png'
    },
    payload: {
      reaction_type: 'fire',
      post_title: 'Tu chân giới đệ nhất meme'
    },
    created_at: new Date(Date.now() - 7200000).toISOString(),
    read_at: null,
    is_read: false
  }
];

function readMockNotifications() {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(MOCK_KEY) : null;
    if (raw) return JSON.parse(raw);
  } catch {}
  return DEFAULT_MOCK;
}

function writeMockNotifications(items) {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(MOCK_KEY, JSON.stringify(items));
    }
  } catch {}
}

export async function getNotifications({ page = 1, pageSize = 20, unreadOnly = false, client = auth } = {}) {
  if (MOCK_AUTH) {
    const all = readMockNotifications();
    const filtered = unreadOnly ? all.filter(n => !n.is_read) : all;
    const total = filtered.length;
    const start = (page - 1) * pageSize;
    const items = filtered.slice(start, start + pageSize);
    const unreadCount = all.filter(n => !n.is_read).length;
    return {
      items,
      pagination: {
        page,
        page_size: pageSize,
        total,
        total_pages: Math.max(1, Math.ceil(total / pageSize))
      },
      unread_count: unreadCount
    };
  }

  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    unread_only: String(unreadOnly)
  });
  return client.read(`/notifications?${query.toString()}`);
}

export async function getUnreadCount({ client = auth } = {}) {
  if (MOCK_AUTH) {
    const all = readMockNotifications();
    return { unread_count: all.filter(n => !n.is_read).length };
  }
  return client.read('/notifications/unread-count');
}

export async function markRead(notificationId, { client = auth } = {}) {
  if (MOCK_AUTH) {
    const all = readMockNotifications();
    let updated = null;
    const next = all.map(n => {
      if (n.id === notificationId) {
        updated = { ...n, is_read: true, read_at: new Date().toISOString() };
        return updated;
      }
      return n;
    });
    writeMockNotifications(next);
    return updated || { id: notificationId, is_read: true, read_at: new Date().toISOString() };
  }
  return client.write('PATCH', `/notifications/${notificationId}/read`);
}

export async function markAllRead({ client = auth } = {}) {
  if (MOCK_AUTH) {
    const all = readMockNotifications();
    const count = all.filter(n => !n.is_read).length;
    const next = all.map(n => ({ ...n, is_read: true, read_at: new Date().toISOString() }));
    writeMockNotifications(next);
    return { marked_read: count };
  }
  return client.write('POST', '/notifications/read-all');
}

export async function createAnnouncement({ title, body }, { client = auth } = {}) {
  if (MOCK_AUTH) {
    const all = readMockNotifications();
    const item = {
      id: `notif-mock-${Date.now()}`,
      type: 'announcement',
      target_type: 'system',
      target_id: null,
      actor: {
        id: 'admin',
        username: 'admin',
        display_name: 'Quản trị viên',
        avatar_url: '/assets/brand/favicon-64.png'
      },
      payload: { title, body },
      created_at: new Date().toISOString(),
      read_at: null,
      is_read: false
    };
    writeMockNotifications([item, ...all]);
    return { success: true, recipients_count: 1, created_at: item.created_at };
  }
  return client.write('POST', '/admin/announcements', { title, body });
}
