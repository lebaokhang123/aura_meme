import { expect, test } from '@playwright/test';
import { mockPublicBlog, post } from './blog-fixtures';

test.beforeEach(async ({ page }) => {
  await mockPublicBlog(page);
  await page.route('**/api/v1/users/me', route => route.fulfill({ json: { id: post.author.id, username: 'synthetic', roles: ['USER', 'ADMIN'], status: 'active' } }));
});

test('dark theme text and primary action token pairs meet normal-text contrast', async ({ page }) => {
  await page.goto('/contact');
  const ratios = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    const luminance = (name: string) => {
      const color = style.getPropertyValue('--color-' + name).trim();
      const rgb = color.match(/^#([0-9a-f]{6})$/i)?.[1];
      if (!rgb) throw new Error('Expected six-digit theme color: ' + name);
      const values = [0, 2, 4].map(offset => {
        const channel = parseInt(rgb.slice(offset, offset + 2), 16) / 255;
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
    };
    return [['on-surface', 'surface'], ['on-surface-variant', 'surface-container-low'], ['outline', 'surface'], ['on-primary', 'primary'], ['secondary', 'surface-container-low']].map(([text, background]) => {
      const values = [luminance(text), luminance(background)].sort((a, b) => b - a);
      return { text, ratio: (values[0] + 0.05) / (values[1] + 0.05) };
    });
  });
  for (const pair of ratios) expect(pair.ratio, pair.text).toBeGreaterThanOrEqual(4.5);
});

test('reduced motion hides local bitmap preview without discarding the attachment', async ({ page }) => {
  await page.goto('/posts/new');
  await page.getByLabel('Attach image (optional)').setInputFiles({ name: 'synthetic.gif', mimeType: 'image/gif', buffer: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAAAAAAALAAAAAABAAEAAAIBRAA7', 'base64') });
  const image = page.getByRole('img', { name: 'Local preview of the selected attachment' });
  await expect(image).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(image).toBeHidden();
  await expect(page.getByText('Preview hidden for reduced motion. Your attachment remains selected.')).toBeVisible();
  expect(await page.getByLabel('Attach image (optional)').evaluate((element: HTMLInputElement) => element.files?.[0].name)).toBe('synthetic.gif');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await expect(image).toBeVisible();
});

test('loading the final channel page keeps keyboard focus and announces completion', async ({ page }) => {
  await page.route('**/api/v1/categories?*', async route => {
    const number = Number(new URL(route.request().url()).searchParams.get('page'));
    if (number === 2) await new Promise(resolve => setTimeout(resolve, 150));
    await route.fulfill({ json: { items: [{ ...post.category, id: String(number), name: 'Channel ' + number }], pagination: { page: number, page_size: 100, total: 101, total_pages: 2 } } });
  });
  await page.goto('/explore');
  const more = page.getByRole('button', { name: 'More channels', exact: true });
  await more.focus();
  await page.keyboard.press('Enter');
  const done = page.getByRole('button', { name: 'All channels loaded', exact: true });
  await expect(done).toBeFocused();
  await expect(done).toHaveAttribute('aria-disabled', 'true');
  await expect(page.getByRole('combobox', { name: 'Category', exact: true }).getByRole('option', { name: 'Channel 2' })).toHaveCount(1);
  await page.keyboard.press('Enter');
  await expect(done).toBeFocused();
});

for (const width of [375, 768, 1024, 1440]) {
  for (const route of ['/posts/new', '/my-posts', '/settings', '/admin?tab=audit-logs']) {
    test(`connected workspace ${route} fits ${width}px with reduced motion`, async ({ page }) => {
      await page.route('**/api/v1/users/me/posts?*', request => request.fulfill({ json: { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } } }));
      await page.route('**/api/v1/admin/**', request => request.fulfill({ json: { items: [{ id: post.id, action: 'post.update', actor_id: post.author.id, target_type: 'post', target_id: post.id, created_at: post.created_at }], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } } }));
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.goto(route);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      expect(await page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length)).toBe(0);
      if (route.startsWith('/admin')) {
        const region = page.getByRole('region', { name: 'Admin results' });
        await expect(region).toBeVisible();
        await region.focus();
        await expect(region).toBeFocused();
      }
    });
  }
}
