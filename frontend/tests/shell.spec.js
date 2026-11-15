import { test, expect } from '@playwright/test';

const routes = ['/', '/explore', '/about', '/contact', '/rank', '/vault', '/login', '/register'];

test('one header keeps logo, navigation, search and controls aligned on every route', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let baseline;
  for (const route of routes) {
    await page.goto(route, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    const header = page.locator('.site-header');
    await expect(header).toHaveCount(1);
    const geometry = await header.evaluate(el => ['.site-brand', '.site-nav', '.site-search', '.site-tools'].map(selector => {
      const box = el.querySelector(selector).getBoundingClientRect();
      return [box.x, box.y, box.width, box.height];
    }));
    if (!baseline) baseline = geometry;
    expect(geometry).toEqual(baseline);
    const active = header.locator('.site-nav [aria-current="page"]');
    if (['/login', '/register', '/rank'].includes(route)) await expect(active).toHaveCount(0);
    else await expect(active).toHaveAttribute('href', route);
  }
});

for (const width of [375, 768, 1024, 1280, 1920]) {
  test(`navigation menu only appears when the header is compact at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    const button = page.getByRole('button', { name: 'Mở menu điều hướng', exact: true });
    if (width >= 1280) {
      await expect(button).toBeHidden();
      await expect(page.locator('.site-nav')).toBeVisible();
    } else {
      await expect(button).toBeVisible();
      await expect(page.locator('.site-nav')).toBeHidden();
      await button.click();
      await expect(button).toHaveAttribute('aria-expanded', 'true');
      if (width === 375) await page.screenshot({ path: testInfo.outputPath('compact-menu-375.png') });
      await page.locator('#compact-navigation').getByRole('link', { name: 'Khám phá', exact: true }).click();
      await expect(page).toHaveURL(/\/explore$/);
      await expect(page.locator('#compact-navigation')).toBeHidden();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test('footer is shared, omitted on Home and opens a blank policy page', async ({ page, context }) => {
  await page.goto('/');
  await expect(page.locator('footer')).toHaveCount(0);
  await expect(page.getByText('Chính sách bảo mật', { exact: true })).toHaveCount(0);
  let baseline;
  for (const route of routes.slice(1)) {
    await page.goto(route);
    const footer = page.locator('.site-footer');
    await expect(footer).toHaveCount(1);
    const text = await footer.innerText();
    if (!baseline) baseline = text;
    expect(text).toBe(baseline);
    await expect(footer.getByRole('link', { name: 'Github', exact: true })).toHaveAttribute('href', 'https://github.com/lebaokhang123/aura_meme');
  }
  const popupPromise = context.waitForEvent('page');
  await page.locator('.site-footer').getByRole('link', { name: 'Chính sách bảo mật', exact: true }).click();
  const popup = await popupPromise;
  await popup.waitForLoadState();
  expect(popup.url()).toContain('/privacy.html');
  expect(await popup.locator('body').innerText()).toBe('');
  await popup.close();
});

for (const route of ['/login', '/register']) {
  test(`${route} shows only the form panel on mobile and retains artwork on desktop`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(route, { waitUntil: 'networkidle' });
    await expect(page.locator('#photoTrailStage, #trailStage')).toBeHidden();
    const heading = await page.locator('main h1').boundingBox();
    const submit = await page.locator('#submitBtn').boundingBox();
    expect(heading.y).toBeLessThan(200);
    expect(submit.y + submit.height).toBeLessThanOrEqual(900);
    await page.setViewportSize({ width: 1440, height: 900 });
    await expect(page.locator('#photoTrailStage, #trailStage')).toBeVisible();
  });
}

for (const [username, name, avatar] of [['Khang_dev', 'Khang Dev', 'khang.jpg'], ['Kien_dev', 'Kien Dev', 'kien.jpg'], ['Gigachad', 'Gigachad', 'gigachad.jpg']]) {
  test(`demo identity follows ${username} without changing authors of sample posts`, async ({ page }, testInfo) => {
    await page.goto('/login');
    await page.locator('#identifier').fill(`${username}@example.com`);
    await page.locator('#password').fill('demo-only');
    await page.locator('#submitBtn').click();
    await expect(page).toHaveURL('http://127.0.0.1:4186/');
    await expect(page.locator('.site-header .account-avatar')).toHaveAttribute('src', `/assets/demo/${avatar}`);
    await expect(page.locator('.site-header .account-avatar')).toHaveAttribute('alt', `Ảnh đại diện ${name}`);
    await expect(page.locator('[data-current-user-avatar]').first()).toHaveAttribute('src', `/assets/demo/${avatar}`);
    await page.getByRole('button', { name: 'Mở menu tài khoản' }).click();
    await page.getByRole('button', { name: 'Thông tin', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Thông tin demo' })).toContainText(name);
    await page.screenshot({ path: testInfo.outputPath(`${username}-profile.png`) });
    await page.getByRole('button', { name: 'Đóng thông tin' }).click();
    await expect(page.getByRole('button', { name: 'Mở menu tài khoản' })).toBeFocused();
    await expect(page.locator('main')).toContainText('Khang Dev');
    await expect(page.locator('main')).toContainText('Kien Dev');
    await expect(page.locator('main')).toContainText('Gigachad');
  });
}

test('Home expands evenly on a wide screen and ends the three-post demo without a spinner', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/');
  const layout = await page.locator('.home-layout').boundingBox();
  const feed = await page.locator('.home-feed').boundingBox();
  expect(layout.width).toBeGreaterThan(1750);
  expect(feed.width).toBeGreaterThan(900);
  expect(Math.abs(layout.x - (1920 - layout.x - layout.width))).toBeLessThan(2);
  await expect(page.locator('.demo-feed-end')).toContainText('3 bài');
  await expect(page.locator('.demo-feed-end .animate-spin')).toHaveCount(0);
});

test('Contact, Rank and Vault share the supplied maintenance art and layout', async ({ page }) => {
  let baseline;
  for (const route of ['/contact', '/rank', '/vault']) {
    await page.goto(route, { waitUntil: 'networkidle' });
    await expect(page.locator('.maintenance-art')).toHaveAttribute('src', '/assets/brand/baotri.png');
    await expect(page.getByRole('heading', { name: 'Tính năng đang phát triển...' })).toBeVisible();
    const box = await page.locator('.maintenance-content').boundingBox();
    if (!baseline) baseline = box;
    expect(box).toEqual(baseline);
    await expect(page.getByRole('link', { name: 'Quay lại Trang chủ' })).toHaveAttribute('href', '/');
  }
});

test('compact menu supports Escape, search shortcut works and reduced motion disables page animation', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  expect(await page.locator('main').evaluate(el => getComputedStyle(el).animationName)).toBe('site-page-enter');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const menu = page.getByRole('button', { name: 'Mở menu điều hướng', exact: true });
  await menu.click();
  await expect(menu).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(menu).toHaveAttribute('aria-expanded', 'false');
  await expect(menu).toBeFocused();
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('searchbox', { name: 'Tìm kiếm meme, tác giả, thẻ' })).toBeFocused();
  expect(await page.locator('main').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
});

test('a failed page chunk keeps the header and offers a reload instead of a blank page', async ({ page }) => {
  await page.route(/\/assets\/guest-about-[^/]+\.js$/, route => route.abort());
  await page.goto('/about');
  await expect(page.locator('.site-header')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Không tải được trang.');
  await expect(page.getByRole('button', { name: 'Tải lại', exact: true })).toBeVisible();
});

test('header and content reveal together when a page chunk is delayed', async ({ page }) => {
  let release;
  let requested;
  const gate = new Promise(resolve => { release = resolve; });
  const started = new Promise(resolve => { requested = resolve; });
  await page.route(/\/assets\/guest-about-[^/]+\.js$/, async route => {
    requested();
    await gate;
    await route.continue();
  });
  await page.goto('/about', { waitUntil: 'domcontentloaded' });
  await started;
  try { await expect(page.locator('.site-header')).toHaveCount(0); }
  finally { release(); }
  await expect(page.locator('.site-header')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Về AuraMeme', exact: true })).toBeVisible();
});

test('compact navigation remains usable in a short landscape viewport', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 844, height: 320 });
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'Mở menu điều hướng', exact: true }).click();
  const menu = page.locator('#compact-navigation');
  const box = await menu.boundingBox();
  expect(box.y + box.height).toBeLessThanOrEqual(320);
  const register = menu.getByRole('link', { name: 'Đăng ký', exact: true });
  await register.scrollIntoViewIfNeeded();
  await expect(register).toBeInViewport({ ratio: 1 });
  await page.screenshot({ path: testInfo.outputPath('compact-menu-landscape.png') });
  await register.click();
  await expect(page).toHaveURL(/\/register$/);
});
