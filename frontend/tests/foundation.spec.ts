import { test, expect } from '@playwright/test';

const routes = ['/', '/explore', '/about', '/contact', '/login', '/register'];

for (const width of [375, 768, 1440]) {
  for (const route of routes) {
    test(`${route} refreshes without overflow at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      const errors: string[] = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.goto(route);
      await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
      await expect(page.getByRole('note')).toContainText('Frontend preview');
      await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth), route).toBeLessThanOrEqual(
        width,
      );
      await expect(page.locator('main')).toHaveCount(1);
      expect(
        await page
          .locator('img')
          .evaluateAll((images) => images.every((image) => image.complete && image.naturalWidth > 0)),
      ).toBe(true);
      await page.screenshot({
        path: test.info().outputPath(`${route.replaceAll('/', '') || 'home'}-${width}.png`),
        fullPage: true,
      });
      await page.reload();
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      expect(errors).toEqual([]);
    });
  }
}

for (const [alias, target] of [
  ['/home', '/'],
  ['/about-us', '/about'],
  ['/team', '/about#team'],
  ['/signup', '/register'],
]) {
  test(`${alias} redirects to ${target}`, async ({ page }) => {
    await page.goto(alias);
    await expect(page).toHaveURL(`http://127.0.0.1:4173${target}`);
  });
}
for (const route of ['/rank', '/vault', '/admin', '/api-practice', '/something-missing']) {
  test(`${route} is not a pretend feature route`, async ({ page }) => {
    await page.goto(route);
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  });
}

test('mobile search and menu work with keyboard and return focus', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();
  const search = page.getByRole('button', { name: 'Search demo posts' });
  await search.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Search demo posts' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('searchbox')).toBeFocused();
  await dialog.getByRole('searchbox').fill('centering');
  await expect(dialog.getByText('CSS in real life:', { exact: false })).toBeVisible();
  await dialog.getByRole('searchbox').fill('no-such-demo-post');
  await expect(dialog.getByText('No sample posts found')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(search).toBeFocused();
  await page.keyboard.press('Control+k');
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  const menu = page.getByRole('button', { name: 'Toggle navigation menu' });
  await menu.focus();
  await page.keyboard.press('Enter');
  await expect(menu).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await expect(menu).toBeFocused();
});

test('team section receives focus after keyboard navigation', async ({ page }) => {
  await page.goto('/about');
  await page.getByRole('link', { name: 'Meet the team', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#team')).toBeFocused();
});

test('forms and post actions do not send requests or invent success', async ({ page }) => {
  const writes: string[] = [];
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) writes.push(request.url());
  });
  await page.goto('/login');
  await page.getByLabel('Email or username').fill('preview-user');
  await page.getByLabel('Password', { exact: true }).fill('not-a-real-password');
  await page.getByRole('button', { name: 'Preview sign-in' }).click();
  await expect(page.getByRole('status')).toContainText('No request was sent');
  await page.goto('/register');
  await page.getByLabel('Username', { exact: true }).fill('preview-user');
  await page.getByLabel('Email', { exact: true }).fill('preview@example.com');
  await page.getByLabel('Password', { exact: true }).fill('not-a-real-password');
  await page.getByLabel('Confirm password').fill('different-password');
  await page.getByRole('button', { name: 'Preview registration' }).click();
  await expect(page.getByRole('status')).toContainText('Passwords do not match');
  await page.getByLabel('Confirm password').fill('not-a-real-password');
  await page.getByRole('button', { name: 'Preview registration' }).click();
  await expect(page.getByRole('status')).toContainText('No account was created');
  await page.goto('/contact');
  await page.getByLabel('Your name').fill('Preview visitor');
  await page.getByLabel('Email address').fill('preview@example.com');
  await page.getByLabel('Subject').selectOption('feedback');
  await page.getByLabel('Message', { exact: true }).fill('A local preview message.');
  await page.getByRole('button', { name: 'Preview message' }).click();
  await expect(page.getByRole('status')).toContainText('not sent or saved');
  await page.goto('/');
  await page.getByRole('button', { name: 'Create post preview' }).click();
  await expect(page.getByRole('status')).toContainText('No post was created');
  expect(writes).toEqual([]);
});

test('reduced motion disables decoration; offline UI has no third-party requests', async ({ page }) => {
  const external: string[] = [];
  page.on('request', (request) => {
    if (!request.url().startsWith('http://127.0.0.1:4173')) external.push(request.url());
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const route of routes) {
    await page.goto(route);
    await page.evaluate(() => document.fonts.ready);
    expect(
      await page.evaluate(
        () => document.getAnimations().filter((animation) => animation.playState === 'running').length,
      ),
    ).toBe(0);
  }
  expect(external).toEqual([]);
});
