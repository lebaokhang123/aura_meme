import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:5173';
const MANIFEST = JSON.parse(fs.readFileSync(path.resolve('backend/h01.local/seed_manifest.json'), 'utf8'));
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

async function main() {
  const browser = await chromium.launch({ headless: true });
  const results = {};

  try {
    // 1. Guest: unknown route -> 404 ErrorPage; deep-link #post-800 works; public profile hides email
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();

      await page.goto(`${BASE_URL}/khong-ton-tai-h03`, { waitUntil: 'networkidle' });
      const err404 = await page.locator('[data-error-status="404"]').count();
      assert.equal(err404, 1, 'Unknown route must render ErrorPage 404');
      await page.screenshot({ path: path.join(EVIDENCE_DIR, 'h03_error_404.png') });
      results.unknown_route_404 = true;

      await page.goto(`${BASE_URL}/#post-${MANIFEST.post_800_id}`, { waitUntil: 'networkidle' });
      const deepVisible = await page.locator(`[id="post-${MANIFEST.post_800_id}"], [data-post-id="${MANIFEST.post_800_id}"]`).count();
      assert.ok(deepVisible >= 1, 'Deep-link #post-UUID must still work');
      results.deep_link_post_800 = true;

      await page.goto(`${BASE_URL}/u/sim_user_001`, { waitUntil: 'networkidle' });
      const profileText = await page.evaluate(() => document.body.innerText);
      assert.equal(profileText.includes('sim_user_001@example.com'), false, 'Public profile must never expose email');
      results.public_profile_no_email = true;

      await ctx.close();
    }

    // 2. Authenticated USER: /admin shows 404 ErrorPage without admin details; API /api/v1/admin/users returns 403
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await loginUI(page, 'sim_user_001@example.com', 'H01SimUser!2026');

      await page.goto(`${BASE_URL}/admin`, { waitUntil: 'networkidle' });
      const userAdmin404 = await page.locator('[data-error-status="404"]').count();
      assert.equal(userAdmin404, 1, 'Authenticated USER on /admin must see 404 ErrorPage');
      const bodyText = await page.evaluate(() => document.body.innerText);
      assert.equal(/Admin Workspace|Không gian quản trị/i.test(bodyText), false, 'Must not leak admin workspace details');
      await page.screenshot({ path: path.join(EVIDENCE_DIR, 'h03_user_admin_404.png') });
      results.user_admin_shows_404 = true;

      const apiStatus = await page.evaluate(async () => {
        const r = await fetch('/api/v1/admin/users', { credentials: 'include' });
        return r.status;
      });
      assert.equal(apiStatus, 403, 'Backend API must still return 403 for USER');
      results.user_admin_api_403 = true;

      await ctx.close();
    }

    // 3. Authenticated ADMIN: sees email in Admin Users, searches by email, mobile no overflow
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await loginUI(page, 'khang_dev@example.com', 'H01SimAdmin!2026');

      await page.goto(`${BASE_URL}/admin`, { waitUntil: 'networkidle' });
      await page.waitForSelector('.admin-user-email', { timeout: 10000 });
      const emailCount = await page.locator('.admin-user-email').count();
      assert.ok(emailCount >= 1, 'Admin Users must render .admin-user-email');
      await page.screenshot({ path: path.join(EVIDENCE_DIR, 'h03_admin_users_email.png') });
      results.admin_sees_email = true;

      // Search by email
      await page.fill('#admin-search-input', 'sim_user_042@example.com');
      await Promise.all([
        page.waitForResponse((r) => r.url().includes('/api/v1/admin/users') && r.url().includes('sim_user_042') && r.status() === 200),
        page.click('.admin-search-button'),
      ]);
      await page.waitForSelector('.admin-user-email', { timeout: 10000 });
      const searchEmails = await page.locator('.admin-user-email').allInnerTexts();
      assert.ok(searchEmails.some((t) => t.includes('sim_user_042@example.com')), 'Search by email must return matching user');
      results.admin_search_by_email = true;

      // Mobile 375x812 overflow check
      await page.setViewportSize({ width: 375, height: 812 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      assert.equal(overflow, false, 'Admin Users mobile view must not overflow horizontally');
      results.admin_mobile_no_overflow = true;

      await ctx.close();
    }
  } finally {
    await browser.close();
  }

  console.log('H03 Playwright Verification PASS:', JSON.stringify(results));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
