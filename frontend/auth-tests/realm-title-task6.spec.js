import { test, expect } from '@playwright/test';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

const REALM_FIXTURES = [
  { tier: 1, level: 5, realm: 'Luyện Khí', title: 'Luyện Khí', username: 'tu_si_01', name: 'Linh Tân Thủ' },
  { tier: 2, level: 15, realm: 'Trúc Cơ', title: 'Trúc Cơ', username: 'tu_si_02', name: 'Thanh Ngọc Đạo Nhân' },
  { tier: 3, level: 25, realm: 'Kim Đan', title: 'Kim Đan', username: 'tu_si_03', name: 'Kim Đan Tán Tu' },
  { tier: 4, level: 35, realm: 'Nguyên Anh', title: 'Nguyên Anh', username: 'tu_si_04', name: 'Băng Lam Kiếm Khách' },
  { tier: 5, level: 45, realm: 'Hóa Thần', title: 'Hóa Thần', username: 'tu_si_05', name: 'Tinh Lam Trưởng Lão' },
  { tier: 6, level: 55, realm: 'Luyện Hư', title: 'Luyện Hư', username: 'tu_si_06', name: 'Hư Không Hành Giả' },
  { tier: 7, level: 65, realm: 'Hợp Thể', title: 'Hợp Thể', username: 'tu_si_07', name: 'Tử Hoa Tông Chủ' },
  { tier: 8, level: 75, realm: 'Đại Thừa', title: 'Đại Thừa', username: 'tu_si_08', name: 'Xích Diễm Đại Đế' },
  { tier: 9, level: 88, realm: 'Độ Kiếp', title: 'Độ Kiếp', username: 'tu_si_09', name: 'Thiên Kiếp Chí Tôn' },
  { tier: 10, level: 100, realm: 'Phi Thăng', title: 'Phi Thăng', username: 'tu_si_10', name: 'Nguyễn Trần Hoàng Minh Quân' },
];

const SPECIAL_FIXTURES = [
  { tier: 8, level: 79, realm: 'Đại Thừa', title: 'Bá Chủ Thiên Lôi', special: 'thunder', username: 'khang_dev', name: 'Khang Dev' },
  { tier: 2, level: 12, realm: 'Trúc Cơ', title: 'Thiên Tướng Độ Ách', special: 'warden', username: 'kien_dev', name: 'Kien Dev' },
];

const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

async function setupFeedMocks(context, { theme = 'dark', language = 'vi' } = {}) {
  await context.addInitScript(
    ({ theme, language }) => {
      localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme, language }));
    },
    { theme, language },
  );

  const category = { id: uuid(900), slug: 'cong-nghe', name: 'Công nghệ', post_count: 13 };
  const allAuthors = [
    ...SPECIAL_FIXTURES,
    ...REALM_FIXTURES,
    { tier: null, level: null, realm: null, title: null, username: 'no_level_user', name: 'Khách Chưa Có Level' },
  ];

  const posts = allAuthors.map((item, idx) => ({
    id: uuid(100 + idx),
    title: `Meme Cảnh Giới #${idx + 1}`,
    content:
      item.special === 'thunder'
        ? 'Khi deploy thứ 6 lúc 17:59 mà production vẫn xanh 100% — uy lực Thiên Lôi!'
        : item.special === 'warden'
        ? 'Review 400 dòng diff trong 5 phút và bắt trúng race condition trước khi merge.'
        : item.level
        ? `Tu luyện đạt ${item.realm} (LVL ${item.level}) — kiểm tra hiển thị huy hiệu cấp bậc và độ tương phản.`
        : 'Bài viết của tài khoản chưa có Level — tuyệt đối không được bịa chức danh.',
    status: 'published',
    created_at: new Date(Date.now() - idx * 120000).toISOString(),
    updated_at: new Date(Date.now() - idx * 120000).toISOString(),
    media_url: null,
    category,
    author: {
      id: uuid(200 + idx),
      username: item.username,
      display_name: item.name,
      created_at: '2026-01-01T00:00:00Z',
      bio: null,
      avatar_url: null,
      ...(item.level ? { level: item.level, realm: item.realm, title: item.title } : {}),
      membership_tier: idx === 0 ? 'prime' : idx === 1 ? 'plus' : 'free',
    },
    interactions: {
      post_id: uuid(100 + idx),
      reaction_counts: { like: 12 + idx, love: 4, laugh: 7, fire: 9, sad: 0, angry: 0 },
      viewer_reaction: null,
      comments_count: idx === 0 ? 3 : 0,
    },
  }));

  const comments = [
    {
      id: uuid(501),
      post_id: posts[0].id,
      body: 'Huy hiệu Thiên Tướng Độ Ách vẫn giữ nguyên LVL 12 (Trúc Cơ) thật!',
      created_at: new Date(Date.now() - 60000).toISOString(),
      author: {
        id: uuid(201),
        username: 'kien_dev',
        display_name: 'Kien Dev',
        created_at: '2026-01-01T00:00:00Z',
        bio: null,
        avatar_url: null,
        level: 12,
        realm: 'Trúc Cơ',
        title: 'Thiên Tướng Độ Ách',
        membership_tier: 'plus',
      },
    },
    {
      id: uuid(502),
      post_id: posts[0].id,
      body: 'Phi Thăng LVL 100 nhìn cực kỳ thanh thoát, không bị chói mắt hay đè tên dài.',
      created_at: new Date(Date.now() - 45000).toISOString(),
      author: {
        id: uuid(211),
        username: 'tu_si_10',
        display_name: 'Nguyễn Trần Hoàng Minh Quân',
        created_at: '2026-01-01T00:00:00Z',
        bio: null,
        avatar_url: null,
        level: 100,
        realm: 'Phi Thăng',
        title: 'Phi Thăng',
        membership_tier: 'free',
      },
    },
    {
      id: uuid(503),
      post_id: posts[0].id,
      body: 'Luyện Khí LVL 5 gọn gàng, sạch sẽ.',
      created_at: new Date(Date.now() - 30000).toISOString(),
      author: {
        id: uuid(202),
        username: 'tu_si_01',
        display_name: 'Linh Tân Thủ',
        created_at: '2026-01-01T00:00:00Z',
        bio: null,
        avatar_url: null,
        level: 5,
        realm: 'Luyện Khí',
        title: 'Luyện Khí',
        membership_tier: 'free',
      },
    },
  ];

  await context.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname.replace(/^\/api\/v1/, '');
    if (p === '/users/me') {
      return route.fulfill({
        json: {
          id: uuid(200),
          username: 'khang_dev',
          email: 'khang@example.com',
          display_name: 'Khang Dev',
          roles: ['USER', 'ADMIN'],
          status: 'active',
          title: 'Bá Chủ Thiên Lôi',
          avatar_url: null,
          cover_url: null,
        },
      });
    }
    if (p === '/aura/progress') {
      return route.fulfill({
        json: {
          earned_xp: 3800,
          bonus_xp: 120,
          total_xp: 3920,
          level: 79,
          fair_level: 78,
          realm: 'Đại Thừa',
          level_xp: 45,
          next_level_xp: 89,
          xp_to_next: 44,
          streak_days: 14,
          checked_in: true,
          effective_day: '2026-11-22',
          next_reset_at: new Date(Date.now() + 3600000).toISOString(),
          server_time: new Date().toISOString(),
        },
      });
    }
    if (p === '/premium/status') {
      return route.fulfill({
        json: {
          subscription: { tier: 'prime', is_active: true, days_remaining: 300, boost_multiplier: 3 },
          plans: [],
          paypal_configured: true,
        },
      });
    }
    if (p === '/categories') {
      return route.fulfill({ json: [category] });
    }
    if (p === '/users/me/bookmarks') {
      return route.fulfill({ json: { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } } });
    }
    if (p === '/posts') {
      return route.fulfill({
        json: { items: posts, pagination: { page: 1, page_size: 20, total: posts.length, total_pages: 1 } },
      });
    }
    if (p.endsWith('/comments')) {
      return route.fulfill({
        json: { items: comments, pagination: { page: 1, page_size: 20, total: comments.length, total_pages: 1 } },
      });
    }
    const postInter = p.match(/^\/posts\/([^/]+)\/interactions$/);
    if (postInter) {
      return route.fulfill({
        json: {
          post_id: postInter[1],
          reaction_counts: { like: 12, love: 4, laugh: 7, fire: 9, sad: 0, angry: 0 },
          viewer_reaction: null,
          comments_count: postInter[1] === posts[0].id ? 3 : 0,
        },
      });
    }
    const commentInter = p.match(/^\/comments\/([^/]+)\/interactions$/);
    if (commentInter) {
      return route.fulfill({
        json: {
          comment_id: commentInter[1],
          reaction_counts: { like: 3, love: 1, laugh: 2, fire: 4, sad: 0, angry: 0 },
          viewer_reaction: null,
        },
      });
    }
    if (p === '/inventory/equipment') {
      return route.fulfill({ json: { items: [] } });
    }
    if (p.startsWith('/notifications')) {
      return route.fulfill({ json: { items: [], unread_count: 0, pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } } });
    }
    return route.fulfill({ json: {} });
  });

  return { posts, comments };
}

test('Task 6: All 10 realms + 2 Admin titles render accurately in feed & comments without fabrication or overflow', async ({ page, context }) => {
  const { posts } = await setupFeedMocks(context, { theme: 'dark', language: 'vi' });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto('/');

  // Wait for all 13 posts to render
  const cards = page.locator('article[data-post-id]');
  await expect(cards).toHaveCount(posts.length);

  // Verify AuraProgress sidebar card uses backend-authorized special title (Khang Dev, LVL 79)
  const auraCard = page.locator('[data-aura]');
  await expect(auraCard.locator('.am-lvl-pill[data-realm-tier="8"]')).toHaveText('LVL 79');
  await expect(auraCard.locator('.am-title-badge[data-special-title="thunder"]')).toContainText('Bá Chủ Thiên Lôi');

  // Verify all 10 realm tiers exist across feed posts
  for (const r of REALM_FIXTURES) {
    const lvl = page.locator(`article .am-lvl-pill[data-realm-tier="${r.tier}"]`, { hasText: `LVL ${r.level}` });
    const title = page.locator(`article .am-title-badge[data-realm-tier="${r.tier}"]`, { hasText: r.title });
    await expect(lvl.first()).toBeVisible();
    await expect(title.first()).toBeVisible();
  }

  // Verify 2 Admin special titles keep their real LVL tier (Khang = tier 8, Kien = tier 2)
  const khangCard = page.locator(`article[data-post-id="${posts[0].id}"]`);
  await expect(khangCard.locator('.am-lvl-pill[data-realm-tier="8"]')).toHaveText('LVL 79');
  await expect(khangCard.locator('.am-title-badge[data-special-title="thunder"]')).toContainText('Bá Chủ Thiên Lôi');

  const kienCard = page.locator(`article[data-post-id="${posts[1].id}"]`);
  await expect(kienCard.locator('.am-lvl-pill[data-realm-tier="2"]')).toHaveText('LVL 12');
  await expect(kienCard.locator('.am-title-badge[data-special-title="warden"]')).toContainText('Thiên Tướng Độ Ách');

  // Verify user without level renders ZERO level/title badges (never fabricated)
  const noLevelCard = page.locator(`article[data-post-id="${posts[posts.length - 1].id}"]`);
  await expect(noLevelCard.locator('.am-lvl-pill')).toHaveCount(0);
  await expect(noLevelCard.locator('.am-title-badge')).toHaveCount(0);

  // Open comments on first post and verify compact sm badges
  await khangCard.getByRole('button', { name: 'Bình luận' }).click();
  await expect(khangCard.locator('[data-comment-id]')).toHaveCount(3);
  await expect(khangCard.locator('[data-comment-id] .am-title-badge--sm[data-special-title="warden"]')).toContainText('Thiên Tướng Độ Ách');
  await expect(khangCard.locator('[data-comment-id] .am-lvl-pill--sm[data-realm-tier="10"]')).toHaveText('LVL 100');

  // Verify feed performance: zero running CSS animations on compact feed cards at rest
  const feedRunningAnims = await page.evaluate(() => {
    const badges = Array.from(document.querySelectorAll('article .am-lvl-pill, article .am-title-badge'));
    return badges.reduce((sum, el) => sum + el.getAnimations({ subtree: true }).length, 0);
  });
  expect(feedRunningAnims).toBe(0);

  // Verify zero horizontal overflow
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.screenshot({ path: `${ARTIFACTS_DIR}/task6_feed_comments_dark.png`, fullPage: false });

  // Mobile 375px Dark Feed + Comments
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(100);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/task6_feed_mobile_375.png`, fullPage: false });

  // Dedicated 10-Realm + 2 Admin Title Matrix in TRUE Dark Mode
  await page.setViewportSize({ width: 1280, height: 880 });
  await renderMatrix(page, 'dark');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/task6_realm_matrix_dark.png`, fullPage: true });
});

async function renderMatrix(page, theme) {
  await page.evaluate(({ realms, specials, theme }) => {
    const isLight = theme === 'light';
    document.body.style.background = isLight ? '#F4F2EE' : '#12131b';
    const root = document.getElementById('root');
    const cardBg = isLight ? '#ffffff' : '#1a1b23';
    const border = isLight ? '#dedbe4' : '#292932';
    const textMain = isLight ? '#16151b' : '#e3e1ed';
    const textMuted = isLight ? '#57535f' : '#948f9a';

    const rowsHtml = realms
      .map(
        (r) => `
        <div style="display:grid;grid-template-columns:64px 110px 1fr 1fr 1fr;align-items:center;gap:12px;padding:10px 14px;border-radius:10px;background:${cardBg};border:1px solid ${border};">
          <span style="font:700 11px/16px 'JetBrains Mono',monospace;color:${textMuted};">TIER ${String(r.tier).padStart(2, '0')}</span>
          <span style="font:600 12px/16px 'JetBrains Mono',monospace;color:${textMain};">LVL ${(r.tier - 1) * 10 + 1}–${r.tier * 10}</span>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="am-lvl-pill am-lvl-pill--sm" data-realm-tier="${r.tier}">LVL ${r.level}</span>
            <span class="am-title-badge am-title-badge--sm" data-realm-tier="${r.tier}">${r.title}</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="am-lvl-pill am-lvl-pill--md" data-realm-tier="${r.tier}">LVL ${r.level}</span>
            <span class="am-title-badge am-title-badge--md" data-realm-tier="${r.tier}">${r.title}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="am-lvl-pill am-lvl-pill--lg" data-realm-tier="${r.tier}">LVL ${r.level}</span>
            <span class="am-title-badge am-title-badge--lg" data-realm-tier="${r.tier}">${r.title}</span>
          </div>
        </div>`,
      )
      .join('');

    const boltSvg = '<span class="am-title-badge-glyph"><svg viewBox="0 0 16 16" fill="currentColor"><path d="M9.6 1.2 3.5 8.8h4.1L6.4 14.8l6.1-7.6H8.4l1.2-6Z"/></svg></span>';
    const shieldSvg = '<span class="am-title-badge-glyph"><svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 1.4 2.4 3.6v4.1c0 3.3 2.3 6.2 5.6 6.9 3.3-.7 5.6-3.6 5.6-6.9V3.6L8 1.4Zm0 2.1 3.6 1.4v2.8c0 2.3-1.5 4.4-3.6 5-2.1-.6-3.6-2.7-3.6-5V4.9L8 3.5Z"/></svg></span>';

    const specialsHtml = specials
      .map(
        (s) => `
        <div style="display:grid;grid-template-columns:186px 1fr 1fr 1fr;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;background:${cardBg};border:1px solid ${border};">
          <div style="display:flex;flex-direction:column;">
            <span style="font:700 13px/18px 'Plus Jakarta Sans',sans-serif;color:${textMain};">${s.name} (@${s.username})</span>
            <span style="font:500 11px/15px 'JetBrains Mono',monospace;color:${textMuted};">Real Tier ${s.tier} (${s.realm})</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="am-lvl-pill am-lvl-pill--sm" data-realm-tier="${s.tier}">LVL ${s.level}</span>
            <span class="am-title-badge am-title-badge--sm" data-realm-tier="${s.tier}" data-special-title="${s.special}">${s.special === 'thunder' ? boltSvg : shieldSvg}<span>${s.title}</span></span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="am-lvl-pill am-lvl-pill--md" data-realm-tier="${s.tier}">LVL ${s.level}</span>
            <span class="am-title-badge am-title-badge--md" data-realm-tier="${s.tier}" data-special-title="${s.special}">${s.special === 'thunder' ? boltSvg : shieldSvg}<span>${s.title}</span></span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="am-lvl-pill am-lvl-pill--lg" data-realm-tier="${s.tier}">LVL ${s.level}</span>
            <span class="am-title-badge am-title-badge--lg" data-realm-tier="${s.tier}" data-special-title="${s.special}">${s.special === 'thunder' ? boltSvg : shieldSvg}<span>${s.title}</span></span>
          </div>
        </div>`,
      )
      .join('');

    root.innerHTML = `
      <div style="max-width:1180px;margin:0 auto;padding:24px;display:flex;flex-direction:column;gap:16px;background:${isLight ? '#F4F2EE' : '#12131b'};min-height:100vh;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;">
          <div>
            <h1 style="margin:0;font:800 22px/28px 'Plus Jakarta Sans',sans-serif;color:${textMain};">AuraMeme Task 6 — 10 Cảnh Giới &amp; 2 Chức Danh Đặc Biệt (${theme.toUpperCase()})</h1>
            <p style="margin:4px 0 0;font:400 13px/18px Inter,sans-serif;color:${textMuted};">Cột hiển thị: Comment (SM) · PostCard / Rank (MD) · Profile / Aura Card (LG)</p>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;">${rowsHtml}</div>
        <h2 style="margin:6px 0 0;font:700 14px/20px 'Plus Jakarta Sans',sans-serif;color:${textMuted};text-transform:uppercase;letter-spacing:0.06em;">Special Cosmetic Titles (Preserves Real Level &amp; Realm Tier)</h2>
        <div style="display:flex;flex-direction:column;gap:8px;">${specialsHtml}</div>
      </div>
    `;
  }, { realms: REALM_FIXTURES, specials: SPECIAL_FIXTURES, theme });
}

test('Task 6: Visual QA Matrix (10 Realms + 2 Admin Titles) in Light Mode, EN & Reduced Motion', async ({ page, context }) => {
  await setupFeedMocks(context, { theme: 'light', language: 'en' });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto('/');
  await expect(page.locator('article[data-post-id]').first()).toBeVisible();
  await page.locator('article[data-post-id]').first().getByRole('button', { name: /Comment|Bình luận/i }).click();
  await expect(page.locator('[data-comment-id]').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/task6_feed_comments_light.png`, fullPage: false });

  await page.setViewportSize({ width: 1280, height: 880 });
  await renderMatrix(page, 'light');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/task6_realm_matrix_light.png`, fullPage: true });

  // Verify prefers-reduced-motion disables sheen animations completely
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const reducedAnims = await page.evaluate(() => {
    const badges = Array.from(document.querySelectorAll('.am-lvl-pill, .am-title-badge'));
    return badges.reduce((sum, el) => sum + el.getAnimations({ subtree: true }).length, 0);
  });
  expect(reducedAnims).toBe(0);
});
