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

async function apiCsrf(req) {
  const r = await req.get(`${API_URL}/api/v1/auth/csrf`);
  assert.equal(r.status(), 200);
  return (await r.json()).csrf_token;
}

async function apiLogin(ctx, email, password) {
  await ctx.clearCookies();
  const req = ctx.request;
  const csrf = await apiCsrf(req);
  const r = await req.post(`${API_URL}/api/v1/auth/login`, {
    data: { email, password },
    headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf },
  });
  assert.equal(r.status(), 200, await r.text());
  return apiCsrf(req);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const suffix = Date.now().toString(36);
  let postId = null;

  try {
    // 1. Seed a published post by sim_user_002 with 1 root comment & 1 reaction
    const apiCtx = await browser.newContext();
    const req = apiCtx.request;
    let csrf2 = await apiLogin(apiCtx, 'sim_user_002@example.com', 'H01SimUser!2026');
    const cats = await (await req.get(`${API_URL}/api/v1/categories`)).json();
    const pr = await req.post(`${API_URL}/api/v1/posts`, {
      data: { title: `H07 E2E Post ${suffix}`, content: `Noi dung H07 E2E ${suffix}`, category_id: cats.items[0].id, status: 'published' },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
    });
    assert.equal(pr.status(), 201, await pr.text());
    postId = (await pr.json()).id;

    const rxRes = await req.put(`${API_URL}/api/v1/posts/${postId}/reactions`, {
      data: { reaction_type: 'fire' },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
    });
    assert.equal(rxRes.status(), 200);

    const cr = await req.post(`${API_URL}/api/v1/posts/${postId}/comments`, {
      data: { body: `Root comment H07 ${suffix}` },
      headers: { Origin: BASE_URL, 'X-CSRF-Token': csrf2 },
    });
    assert.equal(cr.status(), 201);
    const rootCommentId = (await cr.json()).id;
    await apiCtx.close();

    // 2. Guest visits /posts/:id directly -> sees post, reaction pill, and login link on Reply
    {
      const gCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const gPage = await gCtx.newPage();
      await gPage.goto(`${BASE_URL}/posts/${postId}`, { waitUntil: 'networkidle' });
      await gPage.locator(`#comment-${rootCommentId}`).waitFor({ state: 'visible', timeout: 10000 });
      const replyHref = await gPage.locator(`#comment-${rootCommentId} a`, { hasText: /Trả lời|Reply/i }).first().getAttribute('href');
      assert.ok(replyHref && replyHref.includes('/login?next='), 'Guest reply must link to /login?next=');
      await gCtx.close();
    }

    // 3. sim_user_001 opens /posts/:id -> ReactionDetailsModal, Reply, Reply-to-child, Sort, Collapse
    {
      const ctx1 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const p1 = await ctx1.newPage();
      await loginUI(p1, 'sim_user_001@example.com', 'H01SimUser!2026');
      await p1.goto(`${BASE_URL}/posts/${postId}`, { waitUntil: 'networkidle' });

      // Click reaction pill -> opens ReactionDetailsModal without mutating reaction
      await p1.locator('[data-reaction-pill="fire"]').first().click();
      const rxModal = p1.locator('[role="dialog"][aria-label="Biểu cảm"]');
      await rxModal.waitFor({ state: 'visible', timeout: 5000 });
      await rxModal.locator('a', { hasText: '@sim_user_002' }).waitFor({ state: 'visible', timeout: 5000 });
      const modalText = await rxModal.innerText();
      assert.ok(modalText.includes('@sim_user_002'), 'ReactionDetailsModal must list sim_user_002');
      await p1.keyboard.press('Escape');
      await rxModal.waitFor({ state: 'hidden', timeout: 5000 });

      // Reply to root comment
      await p1.locator(`#comment-${rootCommentId} button`, { hasText: /^Trả lời$/ }).first().click();
      await p1.fill('textarea[aria-label="Nội dung trả lời"]', `Reply 1 H07 ${suffix}`);
      await Promise.all([
        p1.waitForResponse((r) => r.url().includes('/comments') && r.request().method() === 'POST' && r.status() === 201),
        p1.locator('button', { hasText: /^Gửi$/ }).last().click(),
      ]);
      await p1.locator(`#comment-${rootCommentId}`, { hasText: `Reply 1 H07 ${suffix}` }).waitFor({ state: 'visible', timeout: 5000 });

      // Change comment sort to reaction_desc
      await p1.selectOption('select[aria-label="Sắp xếp bình luận"]', 'reaction_desc');
      await p1.waitForTimeout(400);

      // Collapse replies -> "Xem 1 câu trả lời"
      await p1.locator('button', { hasText: /^Thu gọn$/ }).first().click();
      await p1.locator('button', { hasText: /Xem 1 câu trả lời/ }).first().waitFor({ state: 'visible', timeout: 5000 });
      await ctx1.close();
    }

    // 4. sim_user_002 checks reply notification -> navigates to /posts/:id?comment=... + mobile EN Light
    {
      const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const p2 = await ctx2.newPage();
      await loginUI(p2, 'sim_user_002@example.com', 'H01SimUser!2026');
      await p2.locator('button[aria-label*="Thông báo"]:visible, button[aria-label*="Notifications"]:visible').first().click();
      const dd = p2.locator('#site-notifications-menu:visible').first();
      await dd.waitFor({ state: 'visible', timeout: 10000 });
      await dd.locator('.notification-item', { hasText: 'Đã trả lời bình luận của bạn.' }).first().click();
      await p2.waitForSelector('.notification-modal', { timeout: 5000 });
      await Promise.all([
        p2.waitForURL(new RegExp(`/posts/${postId}\\?comment=`), { timeout: 10000 }),
        p2.locator('.notification-modal-action-btn').click(),
      ]);
      await p2.locator(`text=Reply 1 H07 ${suffix}`).waitFor({ state: 'visible', timeout: 10000 });

      // Mobile EN Light check
      await p2.evaluate(() => {
        localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ language: 'en', theme: 'light' }));
      });
      await p2.setViewportSize({ width: 390, height: 844 });
      await p2.reload({ waitUntil: 'networkidle' });
      const overflow = await p2.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
      assert.equal(overflow, false, 'PostDetailPage mobile must not overflow horizontally');
      await p2.screenshot({ path: path.join(EVIDENCE_DIR, 'h07_post_detail_mobile.png') });
      await ctx2.close();
    }

    console.log(JSON.stringify({ ok: true, postId, suffix }));
  } finally {
    if (postId) {
      const cleanCtx = await browser.newContext();
      const csrfAdmin = await apiLogin(cleanCtx, 'khang_dev@example.com', 'H01SimAdmin!2026');
      await cleanCtx.request.delete(`${API_URL}/api/v1/admin/posts/${postId}`, {
        headers: { Origin: BASE_URL, 'X-CSRF-Token': csrfAdmin },
      });
      await cleanCtx.close();
    }
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
