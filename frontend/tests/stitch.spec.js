import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import crypto from 'node:crypto';

const manifest = JSON.parse(fs.readFileSync(new URL('../manifest.json', import.meta.url)));
const userKey = 'aurameme-stitch-demo-user';
const users = [
  { displayName: 'Khang Dev', username: 'Khang_dev' },
  { displayName: 'Kien Dev', username: 'Kien_dev' },
  { displayName: 'Gigachad', username: 'Gigachad' },
];
const routes = { home: '/', explore: '/explore', about: '/about', contact: '/contact', rank: '/rank', vault: '/vault', login: '/login', register: '/register' };

test('all 14 screens have complete source, styles, effects and public references', async ({ request }) => {
  expect(Object.keys(manifest)).toHaveLength(14);
  for (const [key, screen] of Object.entries(manifest)) {
    for (const suffix of ['js', 'css', 'effects.json']) {
      expect(fs.existsSync(new URL(`../src/generated/${key}.${suffix}`, import.meta.url))).toBeTruthy();
    }
    const original = await request.get(screen.original);
    expect(original.status()).toBe(200);
    expect(crypto.createHash('sha256').update(await original.body()).digest('hex')).toBe(screen.html_sha256);
    const image = await request.get(screen.reference);
    expect(image.status()).toBe(200);
    expect(image.headers()['content-type']).toContain('image/png');
  }
});

for (const width of [375, 768, 1440]) {
  for (const [key, screen] of Object.entries(manifest)) {
    test(`${key} at ${width}px: direct route, reload, effects and assets`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(({ userKey, user }) => {
        if (user) localStorage.setItem(userKey, JSON.stringify(user));
        else localStorage.removeItem(userKey);
      }, { userKey, user: key.startsWith('user-') ? users[0] : null });
      const errors = [];
      const apiCalls = [];
      const failedRequests = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', req => {
        if (/\/api(?:\/|$)|:800[01](?:\/|$)/.test(req.url())) apiCalls.push(req.url());
      });
      page.on('requestfailed', req => failedRequests.push({ url: req.url(), error: req.failure()?.errorText }));
      const route = routes[key.replace(/^(guest|user)-/, '')];
      const response = await page.goto(route);
      expect(response.status()).toBe(200);
      await expect(page.locator('#root header')).toBeVisible();
      await expect(page.locator('#stitch-active-styles')).toHaveCount(1);
      await expect(page.locator('body')).toHaveClass(screen.bodyClass);
      await page.waitForFunction(() => getComputedStyle(document.body).backgroundColor === 'rgb(18, 19, 27)');
      await page.evaluate(() => document.fonts.ready);
      await page.waitForFunction(() => [...document.images].every(img => img.complete));
      const observed = await page.evaluate(() => ({
        width: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        rootNodes: document.querySelectorAll('#root *').length,
        scriptSlots: document.querySelectorAll('[data-stitch-script-slot]').length,
        brokenImages: [...document.images].filter(img => !img.naturalWidth).map(img => img.src),
        animationNames: [...new Set([...document.querySelectorAll('#root *')].map(el => getComputedStyle(el).animationName).filter(name => name !== 'none'))],
      }));
      expect(observed.scriptSlots).toBe(screen.script_count);
      await expect(page.locator('#root > main')).toHaveCount(1);
      await expect(page.locator('.site-header')).toHaveCount(1);
      if (key.endsWith('home') || key.endsWith('explore')) {
        for (const author of ['Khang Dev', 'Kien Dev', 'Gigachad']) await expect(page.locator('main')).toContainText(author);
      }
      expect(observed.documentWidth).toBeLessThanOrEqual(width);
      expect(observed.brokenImages).toEqual([]);
      expect(errors).toEqual([]);
      expect(apiCalls).toEqual([]);
      const observedPath = testInfo.outputPath('observed.json');
      fs.writeFileSync(observedPath, JSON.stringify({ ...observed, failedRequests }, null, 2));
      await testInfo.attach('observed.json', { path: observedPath, contentType: 'application/json' });
      await page.screenshot({ path: testInfo.outputPath(`${key}-${width}.png`), fullPage: true, animations: 'disabled' });
      await page.reload();
      await expect(page.locator('#root header')).toBeVisible();
      await expect(page.locator('body')).toHaveClass(screen.bodyClass);
      expect(errors).toEqual([]);
      expect(apiCalls).toEqual([]);
    });
  }
}

test('header navigation reaches every mapped route', async ({ page }) => {
  const destinations = { 'trang-chu': '/', 'kham-pha': '/explore', 'gioi-thieu': '/about', 'lien-he': '/contact', 'xep-hang': '/rank', 'bao-kho': '/vault', 'dang-nhap': '/login', 'dang-ky': '/register' };
  await page.setViewportSize({ width: 1440, height: 900 });
  for (const [key, destination] of Object.entries(destinations)) {
    await page.goto('/');
    const link = page.locator(`a[data-path="${key}"]:visible`).first();
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(`http://127.0.0.1:4186${destination}`);
    await expect(page.locator('#root header')).toBeVisible();
  }
});

for (const user of users) {
  test(`frontend demo login and logout: ${user.username}`, async ({ page }) => {
    const apiCalls = [];
    page.on('request', req => { if (/\/api(?:\/|$)|:800[01](?:\/|$)/.test(req.url())) apiCalls.push(req.url()); });
    await page.goto('/login');
    await page.locator('#identifier').fill(`${user.username}@example.com`);
    await page.locator('#password').fill('demo-password-only');
    await page.locator('#loginForm button[type="submit"]').click();
    await expect(page).toHaveURL('http://127.0.0.1:4186/');
    expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)), userKey)).toEqual(user);
    expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('demo-password-only');
    const logout = page.getByRole('button', { name: /đăng xuất/i }).or(page.getByRole('link', { name: /đăng xuất/i })).first();
    if (!(await logout.isVisible())) {
      await page.locator('header button[aria-haspopup="true"]').click();
    }
    await expect(logout).toBeVisible();
    await logout.click();
    await expect.poll(() => page.evaluate(key => localStorage.getItem(key), userKey)).toBeNull();
    await expect(page.locator('body')).toHaveClass(manifest['guest-home'].bodyClass);
    expect(apiCalls).toEqual([]);
  });
}

for (const [route, stageId, cardSelector] of [
  ['/login', 'photoTrailStage', '#photoTrailContainer .meme-trail-card'],
  ['/register', 'trailStage', '#trailContainer .u323-p'],
]) {
  test(`approved pointer burst effect on ${route}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(route);
    const stage = page.locator(`#${stageId}`);
    await expect(stage).toBeVisible();
    const cards = page.locator(cardSelector);
    const before = await cards.count();
    await stage.click({ position: { x: 100, y: 100 } });
    await expect.poll(() => cards.count()).toBeGreaterThan(before);
  });
}

test('register stays frontend-only and rejects mismatched passwords', async ({ page }) => {
  const apiCalls = [];
  page.on('request', req => { if (/\/api(?:\/|$)|:800[01](?:\/|$)/.test(req.url())) apiCalls.push(req.url()); });
  await page.goto('/register');
  await page.locator('#username').fill('Kien_dev');
  await page.locator('#identifier').fill('Kien_dev@example.com');
  await page.locator('#password').fill('demo-register-only');
  await page.locator('#confirmPassword').fill('different-password');
  await page.locator('#terms').check();
  await page.locator('#submitBtn').click();
  await expect(page.locator('#aura-demo-toast')).toContainText('Mật khẩu xác nhận không khớp.');
  expect(await page.evaluate(key => localStorage.getItem(key), userKey)).toBeNull();
  await page.locator('#confirmPassword').fill('demo-register-only');
  await page.locator('#submitBtn').click();
  await expect(page).toHaveURL('http://127.0.0.1:4186/');
  expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)), userKey)).toEqual(users[1]);
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('demo-register-only');
  expect(apiCalls).toEqual([]);
});
