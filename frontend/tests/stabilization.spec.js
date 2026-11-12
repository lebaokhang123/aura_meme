import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import crypto from 'node:crypto';

const routes = { home: '/', explore: '/explore', about: '/about', contact: '/contact', rank: '/rank', vault: '/vault', login: '/login', register: '/register' };
const manifest = JSON.parse(fs.readFileSync(new URL('../manifest.json', import.meta.url)));

for (const key of Object.keys(manifest)) {
  test(`${key}: mobile content and header controls fit 375px`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 900 });
    await page.addInitScript(user => {
      if (user) localStorage.setItem('aurameme-stitch-demo-user', JSON.stringify({ displayName: 'Khang Dev', username: 'Khang_dev' }));
    }, key.startsWith('user-'));
    await page.goto(routes[key.replace(/^(guest|user)-/, '')], { waitUntil: 'networkidle' });
    await expect(page.locator('#root header')).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const dimensions = await page.evaluate(() => ({
      viewport: innerWidth, document: document.documentElement.scrollWidth,
      controls: [...document.querySelectorAll('header a, header button')].flatMap(el => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height || getComputedStyle(el).visibility !== 'visible') return [];
        return [{ label: el.textContent.trim() || el.getAttribute('aria-label'), left: r.left, right: r.right, top: r.top, bottom: r.bottom }];
      }),
    }));
    expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
    for (const control of dimensions.controls) {
      expect(control.left, control.label).toBeGreaterThanOrEqual(0);
      expect(control.right, control.label).toBeLessThanOrEqual(375);
      expect(control.top, control.label).toBeGreaterThanOrEqual(0);
      expect(control.bottom, control.label).toBeLessThanOrEqual(80);
    }
    for (const [index, control] of dimensions.controls.entries()) {
      for (const next of dimensions.controls.slice(index + 1)) {
        const overlapWidth = Math.min(control.right, next.right) - Math.max(control.left, next.left);
        const overlapHeight = Math.min(control.bottom, next.bottom) - Math.max(control.top, next.top);
        expect(overlapWidth > 0 && overlapHeight > 0, `${control.label} overlaps ${next.label}`).toBe(false);
      }
    }
    if (!key.startsWith('user-')) {
      await page.getByRole('button', { name: 'Mở menu điều hướng', exact: true }).click();
      for (const name of ['Đăng nhập', 'Đăng ký']) {
        await expect(page.locator('#compact-navigation').getByText(name, { exact: true })).toBeVisible();
      }
      await page.getByRole('button', { name: 'Mở menu điều hướng', exact: true }).click();
    }
    if (key.endsWith('explore')) {
      const categories = page.locator('main .overflow-x-auto').first();
      await categories.evaluate(el => { el.scrollLeft = el.scrollWidth; });
      await expect(categories.getByRole('button').last()).toBeInViewport();
    }
  });
}

test('broken source images resolve to the exact local files', async ({ request }) => {
  for (const [url, expectedSha] of [
    ['/assets/brand/favicon-64.png', 'ef78bc3699ed0fe1326c8c89c50722a9dc80f133a350b38526d377bc2a0e1a68'],
    ['/assets/brand/symbol-dark-2048.png', 'dc2bba4532836ce4c8089360e1d17dbd5986fda690c752237f38e6dfff01965a'],
  ]) {
    const response = await request.get(url);
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('image/png');
    const sha = buffer => crypto.createHash('sha256').update(buffer).digest('hex');
    expect(sha(await response.body())).toBe(expectedSha);
  }
});

for (const [key, route] of [
  ['guest-contact', '/contact'],
  ['guest-rank', '/rank'],
  ['user-rank', '/rank'],
]) {
  test(`${key}: shared maintenance image and heading remain centered in the viewport`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    if (key.startsWith('user-')) await page.addInitScript(() => localStorage.setItem('aurameme-stitch-demo-user', '{}'));
    await page.goto(route, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    const image = await page.locator('.maintenance-art').boundingBox();
    const heading = await page.locator('h1').boundingBox();
    expect(image.width).toBeCloseTo(image.height, 2);
    expect(heading.y).toBeGreaterThan(image.y + image.height);
    expect(heading.x + heading.width / 2).toBeCloseTo(720, 1);
    await expect(page.getByRole('link', { name: 'Quay lại Trang chủ' })).toBeInViewport();
  });
}
