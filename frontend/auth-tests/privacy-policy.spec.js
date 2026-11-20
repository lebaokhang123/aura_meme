import { test, expect } from '@playwright/test';
import path from 'node:path';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

test.describe('AuraMeme Privacy Policy Suite (Task 3)', () => {
  test('1. Direct navigation to /privacy.html returns 200 and non-empty content', async ({ page }) => {
    const response = await page.goto('/privacy.html');
    expect(response.status()).toBe(200);
    const title = await page.title();
    expect(title).toContain('Chính sách bảo mật');
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
    await expect(heading).toContainText('Chính sách bảo mật');
  });

  test('2. Refreshing /privacy.html preserves content intact', async ({ page }) => {
    await page.goto('/privacy.html');
    await expect(page.locator('#sec-1')).toBeVisible();
    await page.reload();
    await expect(page.locator('#sec-1')).toBeVisible();
    await expect(page.locator('#sec-11')).toBeVisible();
  });

  test('3. Back link navigates to home page and direct /privacy.html link works', async ({ page }) => {
    await page.goto('/privacy.html');
    const backLink = page.locator('.policy-back-link');
    await expect(backLink).toBeVisible();
    expect(await backLink.getAttribute('href')).toBe('/');

    await backLink.click();
    await page.waitForURL('**/');
    expect(page.url()).toMatch(/\/$/);

    // Direct navigation back to /privacy.html
    const resp = await page.goto('/privacy.html');
    expect(resp.status()).toBe(200);
    await expect(page.locator('h1')).toBeVisible();
  });

  test('4. Default VI displays Vietnamese sections and hides English', async ({ page }) => {
    await page.goto('/privacy.html');
    const htmlLang = await page.locator('html').getAttribute('lang');
    expect(htmlLang).toBe('vi');

    const viH1 = page.locator('h1 .lang-vi');
    await expect(viH1).toBeVisible();
    await expect(viH1).toContainText('Chính sách bảo mật AuraMeme');

    const enH1 = page.locator('h1 .lang-en');
    await expect(enH1).toBeHidden();

    await expect(page.locator('#sec-1 .lang-vi').first()).toBeVisible();
    await expect(page.locator('#sec-1 .lang-en').first()).toBeHidden();
  });

  test('5. Switching language to EN displays English and updates title', async ({ page }) => {
    await page.goto('/privacy.html');
    const langBtn = page.locator('#lang-toggle');
    await langBtn.click();

    expect(await page.locator('html').getAttribute('lang')).toBe('en');
    expect(await page.title()).toBe('Privacy Policy — AuraMeme');

    await expect(page.locator('h1 .lang-en')).toBeVisible();
    await expect(page.locator('h1 .lang-vi')).toBeHidden();

    const prefs = await page.evaluate(() => JSON.parse(localStorage.getItem('aurameme-ui-preferences') || '{}'));
    expect(prefs.language).toBe('en');

    await langBtn.click();
    expect(await page.locator('html').getAttribute('lang')).toBe('vi');
    expect(await page.title()).toBe('Chính sách bảo mật — AuraMeme');
  });

  test('6. Switching theme toggles data-theme and dark class', async ({ page }) => {
    await page.goto('/privacy.html');
    const html = page.locator('html');
    expect(await html.getAttribute('data-theme')).toBe('dark');
    expect(await html.getAttribute('class')).toContain('dark');

    const themeBtn = page.locator('#theme-toggle');
    await themeBtn.click();

    expect(await html.getAttribute('data-theme')).toBe('light');
    expect(await html.getAttribute('class')).not.toContain('dark');

    const prefs = await page.evaluate(() => JSON.parse(localStorage.getItem('aurameme-ui-preferences') || '{}'));
    expect(prefs.theme).toBe('light');

    await themeBtn.click();
    expect(await html.getAttribute('data-theme')).toBe('dark');
    expect(await html.getAttribute('class')).toContain('dark');
  });

  test('7. Preferences restore from localStorage on page reload', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('aurameme-ui-preferences', JSON.stringify({
        theme: 'light',
        language: 'en'
      }));
    });

    await page.goto('/privacy.html');
    const html = page.locator('html');
    expect(await html.getAttribute('data-theme')).toBe('light');
    expect(await html.getAttribute('lang')).toBe('en');
    expect(await page.title()).toBe('Privacy Policy — AuraMeme');
    await expect(page.locator('h1 .lang-en')).toBeVisible();
  });

  test('8. Anchor links (#sec-1 to #sec-11) point to valid sections and scroll', async ({ page }) => {
    await page.goto('/privacy.html');
    for (let i = 1; i <= 11; i++) {
      const section = page.locator(`#sec-${i}`);
      await expect(section).toBeAttached();
      const tocLink = page.locator(`.policy-sidebar a[href="#sec-${i}"]`);
      await expect(tocLink).toBeAttached();
    }

    const link11 = page.locator(`.policy-sidebar a[href="#sec-11"]`);
    await link11.click();
    await page.waitForTimeout(300);
    const isVisibleInViewport = await page.locator('#sec-11').isVisible();
    expect(isVisibleInViewport).toBe(true);
  });

  test('9. Responsive layout has no horizontal overflow across viewports', async ({ page }) => {
    const viewports = [
      { width: 375, height: 812, name: 'mobile' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 1440, height: 900, name: 'desktop' },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/privacy.html');

      const hasOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasOverflow, `Overflow detected on ${vp.name} (${vp.width}x${vp.height})`).toBe(false);

      if (vp.width < 1024) {
        await expect(page.locator('.policy-sidebar')).toBeHidden();
        await expect(page.locator('.policy-mobile-toc')).toBeAttached();
      } else {
        await expect(page.locator('.policy-sidebar')).toBeVisible();
      }
    }
  });

  test('10. Zero-JS fallback displays Vietnamese content properly', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto('/privacy.html');

    const title = await page.title();
    expect(title).toContain('Chính sách bảo mật');

    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();

    const sec1Vi = page.locator('#sec-1 .lang-vi').first();
    await expect(sec1Vi).toBeVisible();

    const sec1En = page.locator('#sec-1 .lang-en').first();
    await expect(sec1En).toBeHidden();

    await context.close();
  });

  test('11. Capture visual screenshots for Desktop Dark, Desktop Light, and Mobile Dark', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/privacy.html');
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'privacy_policy_desktop_dark.png'),
      fullPage: false
    });

    const themeBtn = page.locator('#theme-toggle');
    await themeBtn.click();
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'privacy_policy_desktop_light.png'),
      fullPage: false
    });

    await themeBtn.click();
    await page.setViewportSize({ width: 375, height: 812 });
    await page.reload();
    await page.screenshot({
      path: path.join(ARTIFACTS_DIR, 'privacy_policy_mobile_dark.png'),
      fullPage: false
    });
  });
});
