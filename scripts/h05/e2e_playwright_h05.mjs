import assert from 'node:assert/strict';
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const BASE_URL = process.env.H05_BASE_URL || 'http://127.0.0.1:15173';
const SCREENSHOT_PATH = process.env.H05_SCREENSHOT_PATH || 'h05_admin_overview.png';

async function loginThroughApi(page, email, password) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  const res = await page.evaluate(async ({ email, password }) => {
    const csrf = await fetch('/api/v1/auth/csrf', { credentials: 'include' }).then((r) => r.json());
    const r = await fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.csrf_token },
      body: JSON.stringify({ email, password }),
    });
    return r.status;
  }, { email, password });
  assert.equal(res, 200, `Login failed for ${email}`);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    // 1. Guest context
    const guestCtx = await browser.newContext();
    const guestPage = await guestCtx.newPage();
    const guestHbPromise = guestPage.waitForResponse(
      (r) => r.url().includes('/api/v1/presence/heartbeat') && r.request().method() === 'POST'
    );
    await guestPage.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const guestHb = await guestHbPromise;
    assert.equal(guestHb.status(), 200);

    // 2. USER context with 2 tabs (must count as 1 user, not 2)
    const userCtx = await browser.newContext();
    const userTab1 = await userCtx.newPage();
    await loginThroughApi(userTab1, 'sim_user_001@example.com', 'H01SimUser!2026');
    const u1HbPromise = userTab1.waitForResponse(
      (r) => r.url().includes('/api/v1/presence/heartbeat') && r.request().method() === 'POST'
    );
    await userTab1.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    assert.equal((await u1HbPromise).status(), 200);

    const userTab2 = await userCtx.newPage();
    const u2HbPromise = userTab2.waitForResponse(
      (r) => r.url().includes('/api/v1/presence/heartbeat') && r.request().method() === 'POST'
    );
    await userTab2.goto(`${BASE_URL}/explore`, { waitUntil: 'domcontentloaded' });
    assert.equal((await u2HbPromise).status(), 200);

    // 3. Admin context opens /admin -> Overview tab
    const adminCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const adminPage = await adminCtx.newPage();
    await loginThroughApi(adminPage, 'khang_dev@example.com', 'H01SimAdmin!2026');
    await adminPage.goto(`${BASE_URL}/admin`, { waitUntil: 'networkidle' });

    const overviewBtn = adminPage.locator('.workspace-tabs button').first();
    await overviewBtn.click();
    await adminPage.locator('[data-testid="presence-total"]').waitFor({ state: 'visible' });

    const totalBeforeLogout = Number(await adminPage.locator('[data-testid="presence-total"]').innerText());
    const usersBeforeLogout = Number(await adminPage.locator('[data-testid="presence-users"]').innerText());
    const guestsBeforeLogout = Number(await adminPage.locator('[data-testid="presence-guests"]').innerText());

    assert.equal(usersBeforeLogout, 2, `Expected 2 distinct users (sim_user_001 + khang_dev), got ${usersBeforeLogout}`);
    assert.equal(guestsBeforeLogout, 1, `Expected 1 guest, got ${guestsBeforeLogout}`);
    assert.equal(totalBeforeLogout, 3, `Expected total 3, got ${totalBeforeLogout}`);

    await adminPage.screenshot({ path: SCREENSHOT_PATH, fullPage: false });

    // Mobile viewport check (no horizontal overflow)
    await adminPage.setViewportSize({ width: 390, height: 844 });
    const hasOverflow = await adminPage.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    assert.equal(hasOverflow, false, 'Mobile Admin Overview should not overflow horizontally');

    // 4. Logout USER -> Admin refresh shows active_users drop from 2 to 1
    const logoutStatus = await userTab1.evaluate(async () => {
      const csrf = await fetch('/api/v1/auth/csrf', { credentials: 'include' }).then((r) => r.json());
      const r = await fetch('/api/v1/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrf.csrf_token },
      });
      return r.status;
    });
    assert.ok([200, 204].includes(logoutStatus), `Unexpected logout status: ${logoutStatus}`);
    const adminRespPromise = adminPage.waitForResponse(
      (r) => r.url().includes('/api/v1/admin/presence') && r.request().method() === 'GET'
    );
    await adminPage.locator('.admin-refresh').click();
    const adminResp = await adminRespPromise;
    assert.equal(adminResp.status(), 200);
    await adminPage.waitForFunction(
      () => Number(document.querySelector('[data-testid="presence-users"]')?.textContent) === 1,
      null,
      { timeout: 5000 }
    );

    const usersAfterLogout = Number(await adminPage.locator('[data-testid="presence-users"]').innerText());
    assert.equal(usersAfterLogout, 1);

    console.log(JSON.stringify({
      before_logout: { total: totalBeforeLogout, users: usersBeforeLogout, guests: guestsBeforeLogout },
      after_logout: { users: usersAfterLogout },
      mobile_overflow: hasOverflow,
      screenshot: SCREENSHOT_PATH,
    }, null, 2));

    await guestCtx.close();
    await userCtx.close();
    await adminCtx.close();
  } finally {
    await browser.close();
  }
}

main();
