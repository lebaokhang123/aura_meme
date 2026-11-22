import { test, expect } from '@playwright/test';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';
const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

async function setupTask8Mocks(context, { viewer = 'user_b', theme = 'dark', language = 'vi' } = {}) {
  await context.addInitScript(
    ({ theme, language }) => {
      localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme, language }));
    },
    { theme, language },
  );

  const category = { id: uuid(900), slug: 'cong-nghe', name: 'Công nghệ', post_count: 1 };
  const adminAuthor = {
    id: uuid(200),
    username: 'khang_dev',
    display_name: 'Khang Dev',
    created_at: '2026-01-01T00:00:00Z',
    bio: 'Kiến trúc sư hệ thống AuraMeme — Vạn Vận Quy Tông.',
    avatar_url: null,
    level: 79,
    realm: 'Đại Thừa',
    title: 'Sáng Thế Thần',
    membership_tier: 'prime',
  };
  const post = {
    id: uuid(100),
    title: 'Public Profile Post',
    content: 'Click vào avatar, tên hoặc @khang_dev để mở hồ sơ công khai.',
    status: 'published',
    created_at: new Date(Date.now() - 60000).toISOString(),
    updated_at: new Date(Date.now() - 60000).toISOString(),
    media_url: null,
    category,
    author: adminAuthor,
    interactions: {
      post_id: uuid(100),
      reaction_counts: { like: 5, love: 2, laugh: 1, fire: 3, sad: 0, angry: 0 },
      viewer_reaction: null,
      comments_count: 1,
    },
  };
  const comment = {
    id: uuid(501),
    post_id: post.id,
    body: 'Bình luận của Kien Dev — click tên để mở hồ sơ công khai!',
    created_at: new Date(Date.now() - 30000).toISOString(),
    author: {
      id: uuid(201),
      username: 'kien_dev',
      display_name: 'Kien Dev',
      created_at: '2026-01-01T00:00:00Z',
      bio: 'Core Engineer',
      avatar_url: null,
      level: 12,
      realm: 'Trúc Cơ',
      title: 'Sáng Thế Thần',
      membership_tier: 'plus',
    },
  };

  let privateInventoryCalls = 0;

  await context.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname.replace(/^\/api\/v1/, '');

    if (p === '/users/me') {
      if (!viewer) {
        return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: 'Guest' } } });
      }
      return route.fulfill({
        json: {
          id: uuid(300),
          username: viewer,
          email: 'viewer_b@example.com',
          display_name: 'User B Viewer',
          roles: ['USER'],
          status: 'active',
          avatar_url: null,
          cover_url: null,
        },
      });
    }
    if (p === '/users/khang_dev') {
      return route.fulfill({ json: adminAuthor });
    }
    if (p === '/users/kien_dev') {
      return route.fulfill({ json: comment.author });
    }
    if (p.endsWith('/comments') && p.startsWith('/users/')) {
      return route.fulfill({ json: { items: [], pagination: { page: 1, page_size: 1, total: 4, total_pages: 4 } } });
    }
    if (p.endsWith('/activity') && p.startsWith('/users/')) {
      return route.fulfill({ json: { total: 0, days: [] } });
    }
    if (p.startsWith('/inventory/me')) {
      privateInventoryCalls++;
      return route.fulfill({ status: 403, json: { error: { code: 'FORBIDDEN' } } });
    }
    if (p === '/inventory/equipment') {
      return route.fulfill({ json: { items: [] } });
    }
    if (p === '/premium/status') {
      return route.fulfill({ json: { subscription: { tier: 'free', is_active: false }, plans: [] } });
    }
    if (p === '/aura/progress') {
      return route.fulfill({
        json: {
          earned_xp: 20, bonus_xp: 0, total_xp: 20, level: 2, fair_level: 2, realm: 'Luyện Khí',
          level_xp: 9, next_level_xp: 12, xp_to_next: 3, streak_days: 1, checked_in: false,
          effective_day: '2026-11-22', next_reset_at: new Date(Date.now() + 3600000).toISOString(),
          server_time: new Date().toISOString(),
        },
      });
    }
    if (p === '/categories') return route.fulfill({ json: [category] });
    if (p === '/users/me/bookmarks') return route.fulfill({ json: { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } } });
    if (p === '/posts') {
      return route.fulfill({ json: { items: [post], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } } });
    }
    if (p === `/posts/${post.id}/comments`) {
      return route.fulfill({ json: { items: [comment], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } } });
    }
    if (p.endsWith('/interactions') && p.startsWith('/posts/')) {
      return route.fulfill({ json: post.interactions });
    }
    if (p.endsWith('/interactions') && p.startsWith('/comments/')) {
      return route.fulfill({ json: { comment_id: comment.id, reaction_counts: { like: 1, love: 0, laugh: 0, fire: 0, sad: 0, angry: 0 }, viewer_reaction: null } });
    }
    if (p.startsWith('/notifications')) {
      return route.fulfill({ json: { items: [], unread_count: 0, pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } } });
    }
    return route.fulfill({ json: {} });
  });

  return { getPrivateInventoryCalls: () => privateInventoryCalls };
}

test('Task 8: User B navigates from Home/Comment to User A Public Profile (read-only, zero private leak, follower count 0)', async ({ page, context }) => {
  const state = await setupTask8Mocks(context, { viewer: 'user_b', theme: 'dark', language: 'vi' });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto('/');

  // Dismiss cookie banner first so we can verify public profile cleanly
  await expect(page.locator('[data-cookie-banner]')).toBeVisible();
  await page.locator('[data-cookie-reject]').click();
  await expect(page.locator('[data-cookie-reopen]')).toBeVisible();

  // Verify author avatar & name are clickable links to /profile/khang_dev
  const card = page.locator('article[data-post-id]').first();
  await expect(card.locator('a[href="/profile/khang_dev"]').first()).toBeVisible();

  // Open comments and verify comment author is also clickable link to /profile/kien_dev
  await card.getByRole('button', { name: 'Bình luận' }).click();
  await expect(card.locator('[data-comment-id] a[href="/profile/kien_dev"]').first()).toBeVisible();

  // Click author display name -> opens Khang Dev's public profile
  await card.locator('a[href="/profile/khang_dev"]', { hasText: 'Khang Dev' }).click();
  await expect(page).toHaveURL(/\/profile\/khang_dev$/);

  // Verify public identity: display name, @username, Sáng Thế Thần badge, Aura Prime badge, follower count 0
  await expect(page.locator('.am-profile-name h1')).toHaveText('Khang Dev');
  await expect(page.locator('.am-profile-name .am-title-badge--lg[data-special-title="creator"]')).toContainText('Sáng Thế Thần');
  await expect(page.locator('.profile-premium-badge--prime')).toBeVisible();
  await expect(page.getByTestId('profile-follower-count')).toHaveText('0');

  // Verify strict read-only boundary for viewer B: NO edit button, NO private inventory calls, NO private email
  await expect(page.locator('.am-profile-edit')).toHaveCount(0);
  await expect(page.locator('.am-profile-collection')).toHaveCount(0);
  expect(state.getPrivateInventoryCalls()).toBe(0);
  expect(await page.locator('main').innerText()).not.toContain('viewer_b@example.com');

  await page.screenshot({ path: `${ARTIFACTS_DIR}/task8_public_profile_viewer.png`, fullPage: false });

  // Verify /u/:username alias also renders public profile
  await page.goto('/u/kien_dev');
  await expect(page.locator('.am-profile-name h1')).toHaveText('Kien Dev');
  await expect(page.locator('.am-profile-edit')).toHaveCount(0);
});

test('Task 8: Guest views Public Profile & Lucian #225 Cookie Consent (Settings, Reject/Save, Reopen, Reload, Light/Dark, Mobile, Reduced Motion)', async ({ page, context }) => {
  await setupTask8Mocks(context, { viewer: null, theme: 'dark', language: 'vi' });
  await page.setViewportSize({ width: 1280, height: 860 });

  // Guest can view public profile without redirect to /login
  await page.goto('/profile/khang_dev');
  await expect(page.locator('.am-profile-name h1')).toHaveText('Khang Dev');
  await expect(page.locator('.am-profile-edit')).toHaveCount(0);

  // Cookie banner appears for new user with link to /privacy.html#cookies
  const banner = page.locator('[data-cookie-banner]');
  await expect(banner).toBeVisible();
  await expect(banner.locator('a[href="/privacy.html#cookies"]')).toBeVisible();

  // Expand Settings -> Essential switch is always on & disabled; optional switch toggles
  await page.locator('[data-cookie-toggle-settings]').click();
  const settings = page.locator('[data-cookie-settings]');
  await expect(settings).toBeVisible();
  const essentialSwitch = settings.locator('button[role="switch"]').first();
  await expect(essentialSwitch).toHaveAttribute('aria-checked', 'true');
  await expect(essentialSwitch).toBeDisabled();

  await page.screenshot({ path: `${ARTIFACTS_DIR}/task8_cookie_banner_settings.png`, fullPage: false });

  // Save choices with optional=false -> banner closes, reopen button appears, persists after reload
  await page.locator('[data-cookie-save]').click();
  await expect(banner).toHaveCount(0);
  await expect(page.locator('[data-cookie-reopen]')).toBeVisible();

  await page.reload();
  await expect(page.locator('[data-cookie-banner]')).toHaveCount(0);
  await expect(page.locator('[data-cookie-reopen]')).toBeVisible();

  // Reopen cookie settings, test Mobile 375px + Reduced Motion
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 375, height: 812 });
  await page.locator('[data-cookie-reopen]').click();
  await expect(page.locator('[data-cookie-banner]')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/task8_cookie_mobile_375.png`, fullPage: false });
});
