import { expect, test } from '@playwright/test';
import { mockPublicBlog } from './blog-fixtures';
test.beforeEach(async ({ page }) => {
  await mockPublicBlog(page);
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED' } } }));
});

for (const width of [320, 1024]) {
  for (const route of ['/', '/explore', '/about']) {
    test(`polished ${route} also fits ${width}px without hidden page overflow`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(route);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      const menu = page.getByRole('button', { name: 'Toggle navigation menu' });
      await expect(menu).toBeVisible();
      const bounds = await menu.boundingBox();
      expect(bounds?.x).toBeGreaterThanOrEqual(0);
      expect((bounds?.x ?? 0) + (bounds?.width ?? 0)).toBeLessThanOrEqual(width);
      await page.emulateMedia({ reducedMotion: 'reduce' });
      expect(
        await page.evaluate(
          () => document.getAnimations().filter((item) => item.playState === 'running').length,
        ),
      ).toBe(0);
    });
  }
}
