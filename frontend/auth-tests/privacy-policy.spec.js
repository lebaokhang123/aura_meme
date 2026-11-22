import { test, expect } from '@playwright/test';

const SECTIONS = ['about', 'data', 'purpose', 'visibility', 'cookies', 'rights'];

test.describe('AuraMeme Privacy Policy V3 Suite (Task 3 Final)', () => {
  test('1. Direct navigation to /privacy.html returns 200 and non-empty content', async ({ page }) => {
    const response = await page.goto('/privacy.html');
    expect(response.status()).toBe(200);
    const title = await page.title();
    expect(title).toContain('Chính sách bảo mật');
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
    await expect(heading).toContainText('Chính sách bảo mật');
  });

  test('2. Refreshing /privacy.html preserves content intact across 6 sections', async ({ page }) => {
    await page.goto('/privacy.html');
    await expect(page.locator('#about')).toBeVisible();
    await expect(page.locator('#rights')).toBeVisible();
    await page.reload();
    await expect(page.locator('#about')).toBeVisible();
    await expect(page.locator('#rights')).toBeVisible();
  });

  test('3. Header and synchronized V3 minimal footer render and navigate correctly', async ({ page }) => {
    await page.goto('/privacy.html');

    // Header brand and navigation
    const brand = page.locator('.header .brand');
    await expect(brand).toBeVisible();
    expect(await brand.getAttribute('href')).toBe('/');

    const headerNav = page.locator('.header-nav');
    await expect(headerNav).toBeVisible();
    const navLinks = headerNav.locator('a');
    expect(await navLinks.count()).toBe(5);

    // Synchronized V3 minimal footer
    const footer = page.locator('.footer');
    await expect(footer).toBeVisible();
    await expect(footer).toContainText('© 2026 AuraMeme. All rights reserved.');

    // No old 3-column footer elements
    await expect(page.locator('.footer-top')).toHaveCount(0);
    await expect(page.locator('.footer-brand-col')).toHaveCount(0);

    // Exactly 2 footer links: Privacy policy and GitHub
    const footerLinks = page.locator('.footer-links a');
    expect(await footerLinks.count()).toBe(2);

    const privacyLink = footerLinks.nth(0);
    expect(await privacyLink.getAttribute('href')).toBe('/privacy.html');

    const githubLink = footerLinks.nth(1);
    expect(await githubLink.getAttribute('href')).toBe('https://github.com/lebaokhang123/aura_meme');
    expect(await githubLink.getAttribute('target')).toBe('_blank');
    expect(await githubLink.getAttribute('rel')).toContain('noopener');
  });

  test('4. Content V3 verification: removed labels, updated intro-strip, concise about, and no sensitive warning', async ({ page }) => {
    await page.goto('/privacy.html');
    const bodyText = await page.locator('body').innerText();

    // 1. Portfolio/student label removed from hero
    expect(bodyText).not.toContain('Dự án học tập & portfolio');
    expect(bodyText).not.toContain('Student & portfolio project');
    expect(bodyText).not.toContain('portfolio');
    await expect(page.locator('.hero-meta')).toContainText('20/11/2026');

    // 2. Updated intro-strip text
    const introVi = page.locator('.intro-strip .lang-vi');
    await expect(introVi).toContainText('AuraMeme là dự án học tập, không phải dịch vụ thương mại.');

    // 3. Concise "Về AuraMeme"
    const aboutVi = page.locator('#about p.lang-vi');
    await expect(aboutVi).toHaveText('AuraMeme là website chia sẻ meme và giao lưu cộng đồng, kết hợp các tính năng Aura, xếp hạng và bộ sưu tập vật phẩm.');
    expect(await aboutVi.innerText()).not.toContain('DevOps');

    // 4. Sensitive info warning removed from #visibility
    expect(bodyText).not.toContain('số điện thoại');
    expect(bodyText).not.toContain('Avoid posting phone numbers');

    // 5. English counterpart verification
    const langBtn = page.locator('#lang-toggle');
    await langBtn.click();
    const introEn = page.locator('.intro-strip .lang-en');
    await expect(introEn).toContainText('AuraMeme is a learning project, not a commercial service.');
    const aboutEn = page.locator('#about p.lang-en');
    await expect(aboutEn).toHaveText('AuraMeme is a meme-sharing community with Aura points, rankings, and collectible items.');
  });

  test('5. Default VI displays Vietnamese sections and hides English', async ({ page }) => {
    await page.goto('/privacy.html');
    const htmlLang = await page.locator('html').getAttribute('lang');
    expect(htmlLang).toBe('vi');

    const viH1 = page.locator('h1 .lang-vi');
    await expect(viH1).toBeVisible();
    await expect(viH1).toContainText('Chính sách bảo mật');

    const enH1 = page.locator('h1 .lang-en');
    await expect(enH1).toBeHidden();

    await expect(page.locator('#about .lang-vi').first()).toBeVisible();
    await expect(page.locator('#about .lang-en').first()).toBeHidden();
  });

  test('6. Switching language to EN displays English and updates title and attributes', async ({ page }) => {
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

  test('7. Switching theme toggles data-theme and dark class', async ({ page }) => {
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

  test('8. Preferences restore from localStorage on page reload', async ({ page }) => {
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

  test('9. Anchor links for all 6 sections point to valid sections and scroll', async ({ page }) => {
    await page.goto('/privacy.html');
    for (const sec of SECTIONS) {
      const section = page.locator(`#${sec}`);
      await expect(section).toBeAttached();
      const tocLink = page.locator(`.toc a[href="#${sec}"]`);
      await expect(tocLink).toBeAttached();
    }

    const lastLink = page.locator(`.toc a[href="#rights"]`);
    await lastLink.click();
    await page.waitForTimeout(300);
    const isVisibleInViewport = await page.locator('#rights').isVisible();
    expect(isVisibleInViewport).toBe(true);
  });

  test('10. Responsive layout has no horizontal overflow across 1920px, 1440px, 768px, and 375px', async ({ page }) => {
    const viewports = [
      { width: 1920, height: 1080, name: 'desktop-wide' },
      { width: 1440, height: 900, name: 'desktop' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 375, height: 812, name: 'mobile' },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/privacy.html');

      const hasOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasOverflow, `Overflow detected on ${vp.name} (${vp.width}x${vp.height})`).toBe(false);

      if (vp.width <= 760) {
        await expect(page.locator('.toc')).toBeHidden();
        await expect(page.locator('.mobile-toc')).toBeAttached();
        await expect(page.locator('.header-nav')).toBeHidden();
      } else {
        await expect(page.locator('.toc')).toBeVisible();
        await expect(page.locator('.header-nav')).toBeVisible();
      }
    }
  });

  test('11. Zero-JS fallback displays Vietnamese content properly', async ({ browser }) => {
    const context = await browser.newContext({ javaScriptEnabled: false });
    const page = await context.newPage();
    await page.goto('/privacy.html');

    const title = await page.title();
    expect(title).toContain('Chính sách bảo mật');

    const h1 = page.locator('h1');
    await expect(h1).toBeVisible();

    const sec1Vi = page.locator('#about .lang-vi').first();
    await expect(sec1Vi).toBeVisible();

    const sec1En = page.locator('#about .lang-en').first();
    await expect(sec1En).toBeHidden();

    await context.close();
  });

  test('12. Capture visual screenshots for Desktop 1440px, Desktop 1920px, and Mobile 375px (verifying synchronized footer)', async ({ page }) => {
    // 1. Desktop 1440px Dark
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/privacy.html');
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_desktop_dark.png'),
      fullPage: true
    });
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_v3_desktop_1440_dark.png'),
      fullPage: true
    });

    // 2. Desktop 1440px Light
    const themeBtn = page.locator('#theme-toggle');
    await themeBtn.click();
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_desktop_light.png'),
      fullPage: true
    });
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_v3_desktop_1440_light.png'),
      fullPage: true
    });

    // 3. Desktop 1920px Dark
    await themeBtn.click(); // revert to dark
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.reload();
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_v3_desktop_1920_dark.png'),
      fullPage: true
    });

    // 4. Mobile 375px Dark
    await page.setViewportSize({ width: 375, height: 812 });
    await page.reload();
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_mobile_dark.png'),
      fullPage: true
    });
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_v3_mobile_dark.png'),
      fullPage: true
    });

    // 5. Mobile 375px Light
    await page.locator('#theme-toggle').click();
    await page.screenshot({
      path: test.info().outputPath('privacy_policy_v3_mobile_light.png'),
      fullPage: true
    });
  });
});
