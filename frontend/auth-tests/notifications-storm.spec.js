import { test, expect } from '@playwright/test';

const password = 'Synthetic-test-password!';
const users = [
  {
    id: '00000000-0000-4000-8000-000000000001',
    username: 'admin_user',
    email: 'admin_user@example.com',
    display_name: 'Admin User',
    roles: ['USER', 'ADMIN'],
    status: 'active'
  },
  {
    id: '00000000-0000-4000-8000-000000000002',
    username: 'normal_user',
    email: 'normal_user@example.com',
    display_name: 'Normal User',
    roles: ['USER'],
    status: 'active'
  }
];

function makeSampleNotifications() {
  return [
    {
      id: '11111111-1111-4111-8111-111111111111',
      type: 'reaction',
      target_type: 'post',
      target_id: 'p-1',
      actor: {
        id: '22222222-2222-4222-8222-222222222222',
        username: 'khang_dev',
        display_name: 'Khang Dev',
        avatar_url: '/assets/brand/favicon-64.png'
      },
      payload: {
        reaction_type: 'fire',
        post_title: 'Bài viết meme test'
      },
      created_at: new Date(Date.now() - 3600000).toISOString(),
      read_at: null,
      is_read: false
    },
    {
      id: '33333333-3333-4333-8333-333333333333',
      type: 'announcement',
      target_type: 'system',
      target_id: null,
      actor: {
        id: '00000000-0000-4000-8000-000000000001',
        username: 'admin_user',
        display_name: 'Hệ thống AuraMeme',
        avatar_url: '/assets/brand/favicon-64.png'
      },
      payload: {
        title: 'Thông báo bảo trì hệ thống',
        body: 'Nội dung thông báo bảo trì toàn hệ thống.'
      },
      created_at: new Date(Date.now() - 7200000).toISOString(),
      read_at: new Date(Date.now() - 1800000).toISOString(),
      is_read: true
    }
  ];
}

async function setupApiMock(context) {
  const state = {
    user: users[0],
    notifications: makeSampleNotifications(),
    requests: [],
    counts: {
      notifications: 0,
      unreadCount: 0,
      usersMe: 0,
      markRead: 0,
      markAllRead: 0,
      deleteNotif: 0
    },
    simulateRateLimit: false,
    rateLimitRetryAfter: 15
  };

  await context.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    let body = null;
    try { body = request.postDataJSON(); } catch {}

    state.requests.push({ path, method, query: url.search, body, timestamp: Date.now() });

    const send = (status, data, headers = {}) => route.fulfill({
      status,
      contentType: 'application/json',
      headers: { ...headers },
      body: status === 204 ? '' : JSON.stringify(data)
    });
    const fail = (status, code, details = {}, headers = {}) => route.fulfill({
      status,
      contentType: 'application/json',
      headers: { ...headers },
      body: JSON.stringify({ error: { code, message: 'safe', details } })
    });

    if (path === '/api/v1/users/me') {
      state.counts.usersMe++;
      return state.user ? send(200, state.user) : fail(401, 'UNAUTHORIZED');
    }
    if (path.endsWith('/csrf')) {
      return send(200, { csrf_token: 'server-csrf' });
    }
    if (path.endsWith('/login')) {
      const user = users.find(u => u.email === body.email.toLowerCase());
      if (!user || body.password !== password) return fail(401, 'UNAUTHORIZED');
      state.user = user;
      return send(200, user);
    }
    if (path.endsWith('/logout')) {
      state.user = null;
      return send(204);
    }
    if (path === '/api/v1/notifications/unread-count') {
      state.counts.unreadCount++;
      const unread = state.notifications.filter(n => !n.is_read).length;
      return send(200, { unread_count: unread });
    }
    if (path === '/api/v1/notifications') {
      state.counts.notifications++;
      if (state.simulateRateLimit) {
        return fail(429, 'RATE_LIMITED', {}, { 'Retry-After': String(state.rateLimitRetryAfter) });
      }
      const unreadOnly = url.searchParams.get('unread_only') === 'true';
      const filtered = unreadOnly ? state.notifications.filter(n => !n.is_read) : state.notifications;
      const unread = state.notifications.filter(n => !n.is_read).length;
      return send(200, {
        items: filtered,
        pagination: { page: 1, page_size: 20, total: filtered.length, total_pages: 1 },
        unread_count: unread
      });
    }
    if (path.includes('/notifications/') && path.endsWith('/read')) {
      state.counts.markRead++;
      const id = path.split('/')[4];
      const notif = state.notifications.find(n => n.id === id);
      if (notif) {
        notif.is_read = true;
        notif.read_at = new Date().toISOString();
      }
      return send(200, notif || { id, is_read: true, read_at: new Date().toISOString() });
    }
    if (path === '/api/v1/notifications/read-all') {
      state.counts.markAllRead++;
      state.notifications.forEach(n => { n.is_read = true; n.read_at = new Date().toISOString(); });
      return send(200, { marked_read: state.notifications.length });
    }
    if (path.startsWith('/api/v1/notifications/') && method === 'DELETE') {
      state.counts.deleteNotif++;
      const id = path.split('/')[4];
      state.notifications = state.notifications.filter(n => n.id !== id);
      return send(204);
    }
    if (path === '/api/v1/posts' || path.startsWith('/api/v1/categories') || path.startsWith('/api/v1/admin/')) {
      return send(200, { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } });
    }

    return send(200, { items: [] });
  });

  return state;
}

test.describe('P0 Hotfix: Notifications Request Storm Prevention', () => {

  test('opening bell only fetches notifications once and does not storm when kept open for 12 seconds', async ({ page, context }) => {
    const api = await setupApiMock(context);

    await page.goto('/');
    // Check initial unread count fetch
    await expect(page.locator('.notification-trigger')).toBeVisible();
    const initialNotifCount = api.counts.notifications;
    expect(initialNotifCount).toBe(0);

    // Open bell dropdown
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();
    await expect(page.locator('.notification-item')).toHaveCount(2);

    // Exactly 1 fetch to /notifications
    expect(api.counts.notifications).toBe(1);

    // Keep dropdown open for 12 seconds and verify NO continuous polling / storm
    await page.waitForTimeout(12000);
    expect(api.counts.notifications).toBe(1);
    expect(api.counts.unreadCount).toBeLessThanOrEqual(2);
  });

  test('re-rendering header via search or focus does not trigger notifications request loop', async ({ page, context }) => {
    const api = await setupApiMock(context);

    await page.goto('/');
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();
    expect(api.counts.notifications).toBe(1);

    // Type into desktop search bar, re-rendering header
    const searchInput = page.locator('.site-search input').first();
    await searchInput.fill('cyberpunk');
    await searchInput.fill('cultivation');
    await searchInput.fill('');

    // Request count to notifications must stay exactly 1
    expect(api.counts.notifications).toBe(1);
  });

  test('switching tabs (All <-> Unread) triggers exactly one request per switch and preserves filter', async ({ page, context }) => {
    const api = await setupApiMock(context);

    await page.goto('/');
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();
    expect(api.counts.notifications).toBe(1);

    // Switch to "Chưa đọc"
    await page.getByRole('tab', { name: 'Chưa đọc' }).click();
    await expect(page.locator('.notification-item')).toHaveCount(1);
    expect(api.counts.notifications).toBe(2);

    // Switch back to "Tất cả"
    await page.getByRole('tab', { name: 'Tất cả' }).click();
    await expect(page.locator('.notification-item')).toHaveCount(2);
    expect(api.counts.notifications).toBe(3);

    // Wait 3 seconds: no extra requests
    await page.waitForTimeout(3000);
    expect(api.counts.notifications).toBe(3);
  });

  test('item click opens detail modal, mark read, delete item, mark all without storming', async ({ page, context }) => {
    const api = await setupApiMock(context);

    await page.goto('/');
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();

    // Click first item -> opens modal
    await page.locator('.notification-item').first().click();
    await expect(page.locator('.notification-modal')).toBeVisible();
    await expect(page.locator('.notification-modal').getByText('Bài viết meme test')).toBeVisible();

    // Close modal via close button
    await page.locator('.notification-modal-dismiss-btn').click();
    await expect(page.locator('.notification-modal')).toHaveCount(0);

    // Mark all read
    if (await page.locator('.notifications-mark-all-btn').count() > 0) {
      await page.locator('.notifications-mark-all-btn').click();
    }

    // Delete an item
    const deleteBtn = page.locator('.notification-delete-btn').first();
    await deleteBtn.click();
    await expect(page.locator('.notification-item')).toHaveCount(1);

    // Total notifications fetch count must remain 1
    expect(api.counts.notifications).toBe(1);
  });

  test('multiple open/close toggles of notification bell behave predictably without storms', async ({ page, context }) => {
    const api = await setupApiMock(context);

    await page.goto('/');

    // Toggle 1: Open
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();
    expect(api.counts.notifications).toBe(1);

    // Toggle 1: Close
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toHaveCount(0);

    // Toggle 2: Open
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();
    expect(api.counts.notifications).toBe(2);

    // Toggle 2: Close via outside click
    await page.locator('.site-brand').click();
    await expect(page.locator('.notifications-dropdown')).toHaveCount(0);

    // Wait 2s
    await page.waitForTimeout(2000);
    expect(api.counts.notifications).toBe(2);
  });

  test('simulating HTTP 429 and Retry-After: respects cooldown and prevents retrying before expiry', async ({ page, context }) => {
    const api = await setupApiMock(context);
    api.simulateRateLimit = true;
    api.rateLimitRetryAfter = 10;

    await page.goto('/');
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();

    // Error message displayed
    await expect(page.locator('.notifications-error')).toBeVisible();
    await expect(page.locator('.notifications-error p')).toContainText('Quá nhiều lần thử');

    // Request count should be 1
    expect(api.counts.notifications).toBe(1);

    // Clicking "Thử lại" before 10s cooldown expires must NOT send another network request
    const retryBtn = page.locator('.notifications-error button');
    await retryBtn.click();
    await page.waitForTimeout(500);

    // Count must stay strictly 1!
    expect(api.counts.notifications).toBe(1);
    await expect(page.locator('.notifications-error p')).toContainText('Quá nhiều lần thử');
  });

  test('navigation to Home, Explore, and Admin remains intact and unread count is stable', async ({ page, context }) => {
    const api = await setupApiMock(context);

    await page.goto('/');
    await expect(page.locator('.site-brand')).toBeVisible();

    await page.goto('/explore');
    await expect(page.locator('.site-brand')).toBeVisible();

    await page.goto('/admin');
    await expect(page.locator('.admin-page')).toBeVisible();

    // Unread count calls should be bounded, not continuously firing
    expect(api.counts.unreadCount).toBeLessThanOrEqual(4);
  });

});
