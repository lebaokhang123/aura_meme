import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:5173';

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
    // 1. Multi-tab Login sync (Tab A logs in -> Tab B on /register redirects to /)
    {
      const ctx = await browser.newContext();
      const tabA = await ctx.newPage();
      const tabB = await ctx.newPage();
      await tabA.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
      await tabB.goto(`${BASE_URL}/register`, { waitUntil: 'networkidle' });

      await loginUI(tabA, 'sim_user_004@example.com', 'H01SimUser!2026');
      for (let i = 0; i < 10; i++) {
        if (new URL(tabB.url()).pathname === '/') break;
        await tabB.waitForTimeout(500);
      }
      results.multitab_login_register_redirect = new URL(tabB.url()).pathname === '/';
      assert.equal(results.multitab_login_register_redirect, true, `Expected tabB on /, got ${tabB.url()}`);

      // 2. Refresh & navigating back to /login while authenticated redirects to /
      await tabB.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
      for (let i = 0; i < 10; i++) {
        if (new URL(tabB.url()).pathname === '/') break;
        await tabB.waitForTimeout(500);
      }
      results.authenticated_login_redirect = new URL(tabB.url()).pathname === '/';
      assert.equal(results.authenticated_login_redirect, true, `Expected /login redirect to /, got ${tabB.url()}`);

      // 3. /verify-email and /reset-password are NOT blindly redirected while authenticated
      await tabB.goto(`${BASE_URL}/verify-email`, { waitUntil: 'networkidle' });
      assert.equal(new URL(tabB.url()).pathname, '/verify-email');
      await tabB.goto(`${BASE_URL}/reset-password`, { waitUntil: 'networkidle' });
      assert.equal(new URL(tabB.url()).pathname, '/reset-password');
      results.verify_and_reset_preserved = true;

      // 4. Logout from Tab A when Tab B is on /vault -> Tab B redirects to /login?next=%2Fvault
      await tabB.goto(`${BASE_URL}/vault`, { waitUntil: 'networkidle' });
      await tabA.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
      await tabA.evaluate(async () => {
        const csrfRes = await fetch('/api/v1/auth/csrf', { credentials: 'include' });
        const { csrf_token } = await csrfRes.json();
        await fetch('/api/v1/auth/logout', {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-CSRF-Token': csrf_token },
        });
        const ch = new BroadcastChannel('aurameme-auth');
        ch.postMessage('changed');
        ch.close();
      });
      await tabB.waitForURL((u) => u.pathname === '/login', { timeout: 10000 });
      results.multitab_logout_vault_redirect = tabB.url().includes('/login?next=%2Fvault');
      assert.equal(results.multitab_logout_vault_redirect, true);

      // 5. Independent context isolation check
      const ctx2 = await browser.newContext();
      const page2 = await ctx2.newPage();
      await page2.goto(`${BASE_URL}/vault`, { waitUntil: 'networkidle' });
      await page2.waitForURL((u) => u.pathname === '/login', { timeout: 10000 });
      results.independent_context_isolated = new URL(page2.url()).pathname === '/login';
      assert.equal(results.independent_context_isolated, true);
      await ctx2.close();
      await ctx.close();
    }

    // 6. Concurrent login attempts in 2 tabs of same context (guest_guard prevents double login)
    {
      const ctx = await browser.newContext();
      const t1 = await ctx.newPage();
      const t2 = await ctx.newPage();
      await t1.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
      await t2.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
      const [s1, s2] = await Promise.all([
        t1.evaluate(async () => {
          const c = await (await fetch('/api/v1/auth/csrf', { credentials: 'include' })).json();
          const r = await fetch('/api/v1/auth/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': c.csrf_token },
            body: JSON.stringify({ email: 'sim_user_006@example.com', password: 'H01SimUser!2026' }),
          });
          return r.status;
        }),
        t2.evaluate(async () => {
          const c = await (await fetch('/api/v1/auth/csrf', { credentials: 'include' })).json();
          const r = await fetch('/api/v1/auth/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': c.csrf_token },
            body: JSON.stringify({ email: 'sim_user_006@example.com', password: 'H01SimUser!2026' }),
          });
          return r.status;
        }),
      ]);
      results.concurrent_login_statuses = [s1, s2];
      assert.ok(s1 === 200 || s2 === 200);
      assert.ok([s1, s2].every((s) => s === 200 || s === 403));
      await ctx.close();
    }
  } finally {
    await browser.close();
  }

  console.log('H02 Multi-tab Playwright Regression PASS:', JSON.stringify(results));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
