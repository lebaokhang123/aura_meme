import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

if (!process.env.AURAMEME_QA_USER_PASSWORD) throw new Error('Missing AURAMEME_QA_USER_PASSWORD');
if (!process.env.AURAMEME_QA_ADMIN_PASSWORD) throw new Error('Missing AURAMEME_QA_ADMIN_PASSWORD');

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/fab52a17-7f8a-434b-ab78-2c874ac15db9';
const SCREENSHOT_DIR = path.join(ARTIFACTS_DIR, 'screenshots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function run() {
  console.log('Launching browser for Owner QA Verification...');
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const cookieInit = () => {
    try {
      const consent = {
        version: 1,
        essential: true,
        optional: true,
        updatedAt: new Date().toISOString()
      };
      localStorage.setItem('aurameme-cookie-consent-v1', JSON.stringify(consent));
      localStorage.setItem('aurameme-cookie-consent', JSON.stringify(consent));
    } catch {}
  };

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    locale: 'vi-VN'
  });
  await context.addInitScript(cookieInit);
  const page = await context.newPage();

  async function dismissCookieBanner(p) {
    try {
      const bannerBtn = p.locator('button.u409-ok, button.u409-ess, [data-cookie-banner] button').first();
      if (await bannerBtn.isVisible({ timeout: 500 })) {
        await bannerBtn.click();
        await p.waitForTimeout(400);
      }
    } catch {}
  }

  async function snap(filename) {
    await dismissCookieBanner(page);
    const filePath = path.join(SCREENSHOT_DIR, filename);
    await page.screenshot({ path: filePath, fullPage: false });
    console.log(`Saved screenshot: ${filename}`);
  }

  try {
    // -------------------------------------------------------------------------
    // CHECKPOINT A: HEADER SEARCH & STABILITY
    // -------------------------------------------------------------------------
    console.log('Testing Checkpoint A: Search & Vault...');
    await page.goto('http://localhost:4187/explore');
    await page.waitForLoadState('networkidle');
    await dismissCookieBanner(page);

    // 01_search_header_input.png
    const searchInput = page.locator('header input[type="search"], .site-search input, .am-header-search input').first();
    await searchInput.click();
    await searchInput.fill('gigachad');
    // Test backspace does not navigate
    await searchInput.press('Backspace');
    await searchInput.fill('gigachad');
    await snap('01_search_header_input.png');

    // 02_search_results_explore.png
    await searchInput.press('Enter');
    await page.waitForTimeout(1500);
    await snap('02_search_results_explore.png');

    // 03_search_not_found.png
    await searchInput.fill('xyznonexistentquery999');
    await searchInput.press('Enter');
    await page.waitForTimeout(1500);
    await snap('03_search_not_found.png');

    // 04_vault_rapid_switching.png
    await page.goto('http://localhost:4187/vault');
    await page.waitForLoadState('networkidle');
    await dismissCookieBanner(page);
    for (let i = 0; i < 5; i++) {
      const bgTab = page.locator('button:has-text("Background"), button:has-text("Nền")').first();
      const memeTab = page.locator('button:has-text("Meme"), button:has-text("Avatar")').first();
      if (await bgTab.isVisible()) await bgTab.click();
      await page.waitForTimeout(100);
      if (await memeTab.isVisible()) await memeTab.click();
      await page.waitForTimeout(100);
    }
    await page.waitForTimeout(800);
    await snap('04_vault_rapid_switching.png');

    // -------------------------------------------------------------------------
    // CHECKPOINT B: FOLLOW & PUBLIC PROFILE
    // -------------------------------------------------------------------------
    console.log('Testing Checkpoint B: Follow & Profile Collections...');
    // Login as gigachad
    await page.goto('http://localhost:4187/login');
    await page.fill('#identifier', 'gigachad@example.com');
    await page.fill('#password', process.env.AURAMEME_QA_USER_PASSWORD);
    await page.locator('#password').press('Enter');
    await page.waitForTimeout(1500);

    // Visit kien_dev's public profile
    await page.goto('http://localhost:4187/u/kien_dev');
    await page.waitForLoadState('networkidle');
    await dismissCookieBanner(page);
    await page.waitForTimeout(1000);

    // 05_profile_public_view.png
    await snap('05_profile_public_view.png');

    // 06_profile_follow_click.png
    const followBtn = page.locator('[data-testid="profile-follow-button"]');
    await followBtn.click();
    await page.waitForTimeout(1200);
    await snap('06_profile_follow_click.png');

    // 07_profile_unfollow_hover.png
    await followBtn.hover();
    await page.waitForTimeout(500);
    await snap('07_profile_unfollow_hover.png');

    // -------------------------------------------------------------------------
    // CHECKPOINT C: ADMIN USERS INVARIANT & PAGINATION
    // -------------------------------------------------------------------------
    console.log('Testing Checkpoint C: Admin Invariants & Pagination...');
    const adminContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      locale: 'vi-VN'
    });
    await adminContext.addInitScript(cookieInit);
    const adminPage = await adminContext.newPage();

    async function snapAdmin(filename) {
      await dismissCookieBanner(adminPage);
      const filePath = path.join(SCREENSHOT_DIR, filename);
      await adminPage.screenshot({ path: filePath, fullPage: false });
      console.log(`Saved screenshot: ${filename}`);
    }

    // Login as khang_dev
    await adminPage.goto('http://localhost:4187/login');
    await adminPage.fill('#identifier', 'khang_dev@example.com');
    await adminPage.fill('#password', process.env.AURAMEME_QA_ADMIN_PASSWORD);
    await adminPage.locator('#password').press('Enter');
    await adminPage.waitForTimeout(1500);

    // Go to /admin
    await adminPage.goto('http://localhost:4187/admin');
    await adminPage.waitForLoadState('networkidle');
    await dismissCookieBanner(adminPage);
    await adminPage.waitForSelector('.workspace-row');
    await adminPage.waitForTimeout(800);

    // 08_admin_users_invariant.png
    await snapAdmin('08_admin_users_invariant.png');

    // 10_admin_search_layout.png
    const adminSearch = adminPage.locator('.workspace-filters').first();
    await adminSearch.scrollIntoViewIfNeeded();
    await adminPage.waitForTimeout(300);
    await snapAdmin('10_admin_search_layout.png');

    // 09_admin_pagination_ten.png
    const pagination = adminPage.locator('.workspace-pagination').first();
    if (await pagination.isVisible()) {
      await pagination.scrollIntoViewIfNeeded();
    }
    await adminPage.waitForTimeout(300);
    await snapAdmin('09_admin_pagination_ten.png');

    // -------------------------------------------------------------------------
    // CHECKPOINT D: ADMIN CATALOG 3 ROWS, EDIT MODAL, LIVE BG PREVIEW
    // -------------------------------------------------------------------------
    console.log('Testing Checkpoint D: Admin Catalog Layout & Previews...');
    await adminPage.click('nav.workspace-tabs button:has-text("Kiểm duyệt"), nav.workspace-tabs button:has-text("Moderation")');
    await adminPage.waitForTimeout(800);
    const assetSubtab = adminPage.locator('nav.workspace-subtabs button:has-text("Trạng thái vật phẩm"), nav.workspace-subtabs button:has-text("Asset")');
    if (await assetSubtab.isVisible()) {
      await assetSubtab.click();
      await adminPage.waitForTimeout(800);
    }
    await adminPage.waitForSelector('.workspace-row');
    await dismissCookieBanner(adminPage);

    // 11_admin_catalog_three_rows.png
    await snapAdmin('11_admin_catalog_three_rows.png');

    // 12_admin_catalog_edit_modal.png
    const editAssetBtn = adminPage.locator('article.workspace-row button[title*="Sửa"]').first();
    await editAssetBtn.click();
    await adminPage.waitForTimeout(800);
    await snapAdmin('12_admin_catalog_edit_modal.png');
    // Close modal
    await adminPage.click('dialog .workspace-dialog-actions button:has-text("Hủy"), dialog .workspace-dialog-actions button:has-text("Cancel"), dialog button[aria-label="Đóng"]');
    await adminPage.waitForTimeout(500);

    // 13_admin_catalog_bg_preview.png
    // Filter to Background
    await adminPage.selectOption('.workspace-filters select:near(label:has-text("Loại"))', 'background');
    await adminPage.waitForTimeout(1000);
    await adminPage.waitForSelector('.workspace-row');
    const viewBgBtn = adminPage.locator('article.workspace-row button[title*="Xem"]').first();
    await viewBgBtn.click();
    await adminPage.waitForTimeout(1500); // Wait for canvas animation to run
    await snapAdmin('13_admin_catalog_bg_preview.png');
    // Close modal
    await adminPage.keyboard.press('Escape');
    await adminPage.waitForTimeout(500);

    // -------------------------------------------------------------------------
    // CHECKPOINT E: ADMIN TRANSACTIONS & RECEIPT VIEWER
    // -------------------------------------------------------------------------
    console.log('Testing Checkpoint E: Admin Orders & Receipt PDF Viewer...');
    const ordersSubtab = adminPage.locator('nav.workspace-subtabs button:has-text("Giao dịch"), nav.workspace-subtabs button:has-text("Transactions"), nav.workspace-subtabs button:has-text("Orders")');
    await ordersSubtab.click();
    await adminPage.waitForTimeout(1000);
    await adminPage.waitForSelector('.workspace-row');
    await dismissCookieBanner(adminPage);

    // Click receipt eye icon on success order
    const receiptBtn = adminPage.locator('article.workspace-row button[title*="Xem biên lai PDF"], article.workspace-row button:has(.material-symbols-outlined:has-text("receipt_long"))').first();
    await receiptBtn.click();
    await adminPage.waitForTimeout(2500); // Wait for PDF iframe load
    await snapAdmin('14_admin_order_receipt_viewer.png');

    console.log('All 14 QA screenshots captured successfully!');
    await adminContext.close();
  } catch (err) {
    console.error('Error during QA capture:', err);
    await snap('error_state.png');
    throw err;
  } finally {
    await browser.close();
  }
}

run();
