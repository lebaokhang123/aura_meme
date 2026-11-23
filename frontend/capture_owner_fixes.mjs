import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

if (!process.env.AURAMEME_QA_ADMIN_PASSWORD) throw new Error('Missing AURAMEME_QA_ADMIN_PASSWORD');

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/fab52a17-7f8a-434b-ab78-2c874ac15db9';
const SCREENSHOT_DIR = path.join(ARTIFACTS_DIR, 'screenshots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function run() {
  console.log('Launching browser for Owner Fixes Evidence Capture...');
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
    viewport: { width: 1280, height: 850 },
    locale: 'vi-VN'
  });
  await context.addInitScript(cookieInit);
  const page = await context.newPage();

  async function dismissCookieBanner(p) {
    try {
      const bannerBtn = p.locator('button.u409-ok, button.u409-ess, [data-cookie-banner] button').first();
      if (await bannerBtn.isVisible({ timeout: 400 })) {
        await bannerBtn.click();
        await p.waitForTimeout(300);
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
    // Log in as admin khang_dev
    console.log('Logging in as admin khang_dev...');
    await page.goto('http://localhost:4187/login');
    await page.fill('#identifier', 'khang_dev@example.com');
    await page.fill('#password', process.env.AURAMEME_QA_ADMIN_PASSWORD);
    await page.locator('#password').press('Enter');
    await page.waitForTimeout(1500);

    // -------------------------------------------------------------------------
    // 1. EVIDENCE 1: /contact (Text acknowledgment completely removed, cookie auto-accepted)
    // -------------------------------------------------------------------------
    console.log('Capturing Evidence 1: /contact page without acknowledgment text...');
    await page.goto('http://localhost:4187/contact');
    await page.waitForLoadState('networkidle');
    await dismissCookieBanner(page);
    await page.waitForTimeout(800);
    await snap('fix_01_contact_clean.png');

    // -------------------------------------------------------------------------
    // 2. EVIDENCE 2: /admin -> Tab "Nội dung" -> "Danh mục" (Add button icon only, row edit icon only)
    // -------------------------------------------------------------------------

    // Go to admin
    await page.goto('http://localhost:4187/admin');
    await page.waitForLoadState('networkidle');
    await dismissCookieBanner(page);
    await page.waitForSelector('.workspace-row');

    // Click tab "Nội dung"
    await page.click('nav.workspace-tabs button:has-text("Nội dung"), nav.workspace-tabs button:has-text("Content")');
    await page.waitForTimeout(600);

    // Click subtab "Danh mục"
    const catSubtab = page.locator('nav.workspace-subtabs button:has-text("Danh mục"), nav.workspace-subtabs button:has-text("Categories")');
    if (await catSubtab.isVisible()) {
      await catSubtab.click();
      await page.waitForTimeout(600);
    }
    await dismissCookieBanner(page);
    await snap('fix_02_admin_categories_icons.png');

    // -------------------------------------------------------------------------
    // 3. EVIDENCE 3: /admin -> Tab "Kiểm duyệt" -> "Giao dịch" -> Real PDF File Preview
    // -------------------------------------------------------------------------
    console.log('Capturing Evidence 3: /admin Orders Real PDF Viewer...');
    await page.click('nav.workspace-tabs button:has-text("Kiểm duyệt"), nav.workspace-tabs button:has-text("Moderation")');
    await page.waitForTimeout(600);

    const ordersSubtab = page.locator('nav.workspace-subtabs button:has-text("Giao dịch"), nav.workspace-subtabs button:has-text("Transactions"), nav.workspace-subtabs button:has-text("Orders")');
    if (await ordersSubtab.isVisible()) {
      await ordersSubtab.click();
      await page.waitForTimeout(800);
    }
    await page.waitForSelector('.workspace-row');
    await dismissCookieBanner(page);

    // Click receipt icon on first success row
    const receiptBtn = page.locator('article.workspace-row button[title*="Biên lai thu tiền điện tử"], article.workspace-row button:has(.material-symbols-outlined:has-text("receipt_long"))').first();
    await receiptBtn.click();
    await page.waitForTimeout(2000); // Wait for iframe to render PDF
    await snap('fix_03_admin_receipt_real_pdf.png');

    // Close receipt modal
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);

    // -------------------------------------------------------------------------
    // 4. EVIDENCE 4: /admin -> Tab "Kiểm duyệt" -> "Trạng thái vật phẩm" -> Asset Upload
    // -------------------------------------------------------------------------
    console.log('Capturing Evidence 4: Asset Upload Modal & Safe Validation...');
    const assetSubtab = page.locator('nav.workspace-subtabs button:has-text("Trạng thái vật phẩm"), nav.workspace-subtabs button:has-text("Asset")');
    if (await assetSubtab.isVisible()) {
      await assetSubtab.click();
      await page.waitForTimeout(800);
    }
    await page.waitForSelector('.workspace-row');
    await dismissCookieBanner(page);

    // Click "Thêm vật phẩm" button
    const addAssetBtn = page.locator('.admin-toolbar-actions button.admin-add-asset-btn');
    await addAssetBtn.click();
    await page.waitForTimeout(600);
    await snap('fix_04_admin_asset_upload_modal.png');

    // 1. Test duplicate file upload to show clean error message without "(trùng mã băm SHA-256)"
    const duplicateFilePath = path.join(ARTIFACTS_DIR, 'S_241126_99.png');
    const fileInput = page.locator('#admin-asset-file-input');
    await fileInput.setInputFiles(duplicateFilePath);
    await page.waitForTimeout(400);

    const submitBtn = page.locator('dialog form button.workspace-primary[type="submit"]');
    await submitBtn.click();
    await page.waitForTimeout(1000);
    await snap('fix_06_duplicate_hash_error.png');

    // Close and reopen to demonstrate successful upload with a new valid hash
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    await addAssetBtn.click();
    await page.waitForTimeout(500);

    const validNewFilePath = path.join(ARTIFACTS_DIR, 'S_241126_77.png');
    await page.locator('#admin-asset-file-input').setInputFiles(validNewFilePath);
    await page.waitForTimeout(500);
    await page.locator('dialog form button.workspace-primary[type="submit"]').click();
    await page.waitForTimeout(2500);

    // Capture success state in assets list showing success alert and pending item
    await dismissCookieBanner(page);
    await snap('fix_05_admin_asset_uploaded_pending.png');

    console.log('All evidence screenshots captured successfully!');
  } catch (err) {
    console.error('Error during evidence capture:', err);
    await snap('error_evidence.png');
    throw err;
  } finally {
    await browser.close();
  }
}

run();
