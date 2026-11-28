import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://127.0.0.1:8000';
const EVIDENCE_DIR = path.resolve('backend/h01.local/playwright_evidence');
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

async function loginUI(page, email, password) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  await page.fill('#identifier', email);
  await page.fill('#password', password);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 15000 }),
    page.click('#loginForm button[type="submit"]'),
  ]);
  await page.waitForLoadState('networkidle');
}

async function apiCsrf(request) {
  const res = await request.get(`${API_URL}/api/v1/auth/csrf`);
  assert.equal(res.status(), 200);
  return (await res.json()).csrf_token;
}

async function apiLogin(ctx, email, password) {
  await ctx.clearCookies();
  const req = ctx.request;
  const csrf = await apiCsrf(req);
  const res = await req.post(`${API_URL}/api/v1/auth/login`, {
    data: { email, password },
    headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf },
  });
  assert.equal(res.status(), 200, await res.text());
  return apiCsrf(req);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const suffix = Date.now().toString(36);
  const createdPostIds = [];

  try {
    // 1. Seed real interactions via API on isolated backend (sim_user_001 -> sim_user_002, Admin moderation)
    const apiCtx = await browser.newContext();
    const req = apiCtx.request;

    // sim_user_002 creates 2 posts + sim_user_001 comments & reacts on them
    let csrf2 = await apiLogin(apiCtx, 'sim_user_002@example.com', 'H01SimUser!2026');
    const cats = await (await req.get(`${API_URL}/api/v1/categories`)).json();
    const catId = cats.items[0].id;

    for (const label of [`H06 Post An ${suffix}`, `H06 Post Xoa ${suffix}`]) {
      const pr = await req.post(`${API_URL}/api/v1/posts`, {
        data: { title: label, content: `Noi dung kiem thu ${suffix}`, category_id: catId, status: 'published' },
        headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
      });
      assert.equal(pr.status(), 201, await pr.text());
      createdPostIds.push((await pr.json()).id);
    }

    // sim_user_001 reacts (fire) and comments on post 0, then sim_user_002 creates a comment to be moderated
    let csrf1 = await apiLogin(apiCtx, 'sim_user_001@example.com', 'H01SimUser!2026');
    const reactRes = await req.put(`${API_URL}/api/v1/posts/${createdPostIds[0]}/reactions`, {
      data: { reaction_type: 'fire' },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf1 },
    });
    assert.equal(reactRes.status(), 200, await reactRes.text());

    csrf2 = await apiLogin(apiCtx, 'sim_user_002@example.com', 'H01SimUser!2026');
    const c1Res = await req.post(`${API_URL}/api/v1/posts/${createdPostIds[0]}/comments`, {
      data: { body: `Comment bi an ${suffix}` },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
    });
    assert.equal(c1Res.status(), 201, await c1Res.text());
    const c1Id = (await c1Res.json()).id;

    const c2Res = await req.post(`${API_URL}/api/v1/posts/${createdPostIds[0]}/comments`, {
      data: { body: `Comment bi xoa ${suffix}` },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
    });
    assert.equal(c2Res.status(), 201, await c2Res.text());
    const c2Id = (await c2Res.json()).id;

    // Admin moderates c1 (hidden), c2 (deleted), post0 (hidden), post1 (deleted)
    const csrfAdmin = await apiLogin(apiCtx, 'khang_dev@example.com', 'H01SimAdmin!2026');
    const modC1 = await req.patch(`${API_URL}/api/v1/admin/comments/${c1Id}`, {
      data: { status: 'hidden', reason: `Ly do an cmt ${suffix}` },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrfAdmin },
    });
    assert.ok([200, 204].includes(modC1.status()), await modC1.text());

    const modC2 = await req.delete(`${API_URL}/api/v1/admin/comments/${c2Id}?reason=${encodeURIComponent(`Ly do xoa cmt ${suffix}`)}`, {
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrfAdmin },
    });
    assert.ok([200, 204].includes(modC2.status()), await modC2.text());

    const modP0 = await req.patch(`${API_URL}/api/v1/admin/posts/${createdPostIds[0]}`, {
      data: { status: 'hidden', reason: `Ly do an bai ${suffix}` },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrfAdmin },
    });
    assert.ok([200, 204].includes(modP0.status()), await modP0.text());

    const modP1 = await req.delete(`${API_URL}/api/v1/admin/posts/${createdPostIds[1]}?reason=${encodeURIComponent(`Ly do xoa bai ${suffix}`)}`, {
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrfAdmin },
    });
    assert.ok([200, 204].includes(modP1.status()), await modP1.text());

    // Ensure clean follow state u1 -> u2 and clear any old follow notifications for u2
    csrf2 = await apiLogin(apiCtx, 'sim_user_002@example.com', 'H01SimUser!2026');
    const u2Notifs = await (await req.get(`${API_URL}/api/v1/notifications?page=1&page_size=50`)).json();
    for (const n of u2Notifs.items || []) {
      if (n.type === 'follow') {
        await req.delete(`${API_URL}/api/v1/notifications/${n.id}`, {
          headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
        });
      }
    }
    csrf1 = await apiLogin(apiCtx, 'sim_user_001@example.com', 'H01SimUser!2026');
    await req.delete(`${API_URL}/api/v1/users/sim_user_002/follow`, {
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf1 },
    });
    await apiCtx.close();

    // 2. User 1 follows -> unfollows -> re-follows User 2 in real UI
    {
      const ctx1 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page1 = await ctx1.newPage();
      await loginUI(page1, 'sim_user_001@example.com', 'H01SimUser!2026');
      await page1.goto(`${BASE_URL}/u/sim_user_002`, { waitUntil: 'networkidle' });
      const followBtn = page1.getByTestId('profile-follow-button');
      await followBtn.waitFor({ state: 'visible', timeout: 10000 });
      await Promise.all([
        page1.waitForResponse((r) => r.url().includes('/follow') && r.request().method() === 'POST' && r.status() === 200),
        followBtn.click(),
      ]);
      await page1.locator('[data-testid="profile-follow-button"].am-follow-btn--active').waitFor({ state: 'visible', timeout: 5000 });
      await Promise.all([
        page1.waitForResponse((r) => r.url().includes('/follow') && r.request().method() === 'DELETE' && r.status() === 200),
        followBtn.click(),
      ]);
      await page1.locator('[data-testid="profile-follow-button"]:not(.am-follow-btn--active)').waitFor({ state: 'visible', timeout: 5000 });
      await Promise.all([
        page1.waitForResponse((r) => r.url().includes('/follow') && r.request().method() === 'POST' && r.status() === 200),
        followBtn.click(),
      ]);
      await page1.locator('[data-testid="profile-follow-button"].am-follow-btn--active').waitFor({ state: 'visible', timeout: 5000 });
      await ctx1.close();
    }

    // 3. User 2 checks Notifications UI (desktop VI, EN, Light/Dark, and mobile 390x844)
    {
      const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page2 = await ctx2.newPage();
      await loginUI(page2, 'sim_user_002@example.com', 'H01SimUser!2026');

      // Open bell dropdown
      await page2.locator('button[aria-label*="Thông báo"]:visible, button[aria-label*="Notifications"]:visible').first().click();
      const dropdown = page2.locator('#site-notifications-menu:visible').first();
      await dropdown.waitFor({ state: 'visible', timeout: 10000 });
      await dropdown.locator('.notification-item').first().waitFor({ state: 'visible', timeout: 10000 });
      const dropdownText = await dropdown.innerText();

      assert.ok(dropdownText.includes('Đã ẩn bài viết của bạn.'), 'Missing hidden post VI notification');
      assert.ok(dropdownText.includes('Đã xóa bài viết của bạn.'), 'Missing deleted post VI notification');
      assert.ok(dropdownText.includes('Đã ẩn bình luận của bạn.'), 'Missing hidden comment VI notification');
      assert.ok(dropdownText.includes('Đã xóa bình luận của bạn.'), 'Missing deleted comment VI notification');
      assert.ok(!dropdownText.includes('Nội dung đã được kiểm duyệt bởi Quản trị viên'), 'Must not use generic moderation text');
      assert.ok(dropdownText.includes('Đã thả biểu cảm vào bài viết của bạn'), 'Missing reaction VI notification');
      assert.ok(!dropdownText.includes('(fire)'), 'Reaction notification must not contain raw (fire)');

      // Follow notification appears exactly once
      const followMatches = dropdownText.match(/Đã bắt đầu theo dõi bạn\./g) || [];
      assert.equal(followMatches.length, 1, `Expected 1 follow notification, got ${followMatches.length}`);

      // Click moderated post notification -> modal must NOT show "Xem bài viết"
      await page2.locator('.notification-item', { hasText: 'Đã ẩn bài viết của bạn.' }).first().click();
      await page2.waitForSelector('.notification-modal', { timeout: 5000 });
      const modModalText = await page2.locator('.notification-modal').innerText();
      assert.ok(modModalText.includes(`Ly do an bai ${suffix}`), 'Moderation modal must show reason');
      assert.equal(await page2.locator('.notification-modal-action-btn', { hasText: 'Xem bài viết' }).count(), 0, 'Moderated post modal must hide View post button');
      await page2.locator('.notification-modal-close-btn').click();

      // Click follow notification -> modal shows "Xem trang cá nhân" and navigates to /u/sim_user_001
      if ((await page2.locator('#site-notifications-menu:visible').count()) === 0) {
        await page2.locator('button[aria-label*="Thông báo"]:visible, button[aria-label*="Notifications"]:visible').first().click();
        await page2.locator('#site-notifications-menu:visible').first().waitFor({ state: 'visible', timeout: 5000 });
      }
      await page2.locator('.notification-item', { hasText: 'Đã bắt đầu theo dõi bạn.' }).first().click();
      await page2.waitForSelector('.notification-modal', { timeout: 5000 });
      await Promise.all([
        page2.waitForURL(/\/u\/sim_user_001/, { timeout: 10000 }),
        page2.locator('.notification-modal-action-btn', { hasText: 'Xem trang cá nhân' }).click(),
      ]);
      assert.ok(page2.url().includes('/u/sim_user_001'));

      // Switch to EN + Light theme + Mobile viewport
      await page2.evaluate(() => {
        localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ language: 'en', theme: 'light' }));
      });
      await page2.setViewportSize({ width: 390, height: 844 });
      await page2.reload({ waitUntil: 'networkidle' });
      await page2.locator('button[aria-label*="Notifications"]:visible, button[aria-label*="Thông báo"]:visible').first().click();
      const mobileDropdown = page2.locator('#site-notifications-menu:visible').first();
      await mobileDropdown.waitFor({ state: 'visible', timeout: 5000 });
      await mobileDropdown.locator('.notification-item').first().waitFor({ state: 'visible', timeout: 5000 });
      const enText = await mobileDropdown.innerText();
      assert.ok(enText.includes('Started following you.'), 'EN follow notification missing');
      assert.ok(enText.includes('Your post was hidden.'), 'EN hidden post notification missing');
      const hasOverflow = await page2.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
      assert.equal(hasOverflow, false, 'Mobile notifications view must not overflow horizontally');
      await page2.screenshot({ path: path.join(EVIDENCE_DIR, 'h06_notifications_mobile_en_light.png') });
      await ctx2.close();
    }

    // 4. Admin Workspace: Search (@username, author), Date Range, Presets, Sort, Pagination, VI/EN, Mobile
    {
      const ctxA = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const pageA = await ctxA.newPage();
      await pageA.addInitScript(() => {
        localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ language: 'vi', theme: 'dark' }));
      });
      await loginUI(pageA, 'khang_dev@example.com', 'H01SimAdmin!2026');
      await pageA.goto(`${BASE_URL}/admin`, { waitUntil: 'networkidle' });
      const cookieAccept = pageA.locator('.am-cookie-root button').first();
      if ((await cookieAccept.count()) > 0 && (await cookieAccept.isVisible())) {
        await cookieAccept.click();
      }

      // Go to Content section -> Posts subtab
      await pageA.locator('.workspace-tabs button', { hasText: /Nội dung|Content/i }).first().click();
      await pageA.locator('.workspace-subtabs button', { hasText: /^Bài viết$|^Posts$/i }).first().click();
      await pageA.waitForSelector('input[aria-label="Từ ngày"]', { timeout: 10000 });

      // Search by @sim_user_002
      await pageA.fill('#admin-search-input', '@sim_user_002');
      await pageA.click('.admin-search-button');
      await pageA.waitForTimeout(500);
      const postsText = await pageA.locator('.workspace-rows').innerText();
      assert.ok(postsText.includes('@sim_user_002'), 'Admin posts search by @username failed');

      // Preset "Hôm nay", Sort "created_asc", Clear filters
      await pageA.locator('.admin-preset-btn', { hasText: 'Hôm nay' }).click();
      await pageA.waitForTimeout(400);
      await pageA.selectOption('select[aria-label="Sắp xếp"]', 'created_asc');
      await pageA.waitForTimeout(400);
      assert.ok((await pageA.inputValue('input[aria-label="Từ ngày"]')).length === 10);
      await pageA.locator('.admin-clear-filters-btn').click();
      await pageA.waitForTimeout(400);
      assert.equal(await pageA.inputValue('input[aria-label="Từ ngày"]'), '');

      // Pagination check on Users or Posts if >10 items
      const nextBtn = pageA.locator('.workspace-pagination button', { hasText: /Sau|Next/i }).first();
      if ((await nextBtn.count()) > 0 && (await nextBtn.isEnabled())) {
        await nextBtn.click();
        await pageA.waitForTimeout(400);
      }

      // Go to Comments subtab & search by @sim_user_002
      await pageA.locator('.workspace-subtabs button', { hasText: /^Bình luận$|^Comments$/i }).first().click();
      await pageA.fill('#admin-search-input', '@sim_user_002');
      await pageA.click('.admin-search-button');
      await pageA.waitForTimeout(500);
      const cmtsText = await pageA.locator('.workspace-rows').innerText();
      assert.ok(cmtsText.includes('@sim_user_002'), 'Admin comments search by @username failed');

      // Mobile Admin check
      await pageA.setViewportSize({ width: 390, height: 844 });
      await pageA.waitForTimeout(300);
      await pageA.screenshot({ path: path.join(EVIDENCE_DIR, 'h06_admin_mobile.png') });
      await ctxA.close();
    }

    console.log(JSON.stringify({ ok: true, suffix, createdPostIds }));
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
