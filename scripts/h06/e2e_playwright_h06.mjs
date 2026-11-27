import assert from 'node:assert/strict';
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const BASE_URL = process.env.H06_BASE_URL || 'http://127.0.0.1:15173';
const SEC_ADMIN_EMAIL = process.env.H06_SEC_ADMIN_EMAIL;
const ASSET_NAME = process.env.H06_ASSET_NAME;
const PASSWORD = 'H01SimAdmin!2026';

async function loginThroughApi(page, email, password) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  const res = await page.evaluate(async ({ email, password }) => {
    const csrf = await fetch('/api/v1/auth/csrf', { credentials: 'include' }).then((r) => r.json());
    const r = await fetch('/api/v1/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.csrf_token },
      body: JSON.stringify({ email, password }),
    });
    return r.status;
  }, { email, password });
  assert.equal(res, 200, `Login failed for ${email}`);
}

async function openAssetsTab(page, searchName) {
  await page.goto(`${BASE_URL}/admin`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /Kiểm duyệt|Moderation/i }).click();
  await page.getByRole('button', { name: /Trạng thái vật phẩm|Asset status/i }).click();
  await page.locator('#admin-search-input').fill(searchName);
  await page.locator('#admin-search-input').press('Enter');
  await page.locator('.workspace-row').first().waitFor({ state: 'visible' });
}

async function main() {
  assert.ok(SEC_ADMIN_EMAIL && ASSET_NAME, 'Missing H06_SEC_ADMIN_EMAIL or H06_ASSET_NAME');
  const browser = await chromium.launch({ headless: true });
  const renamed = `${ASSET_NAME} Renamed`;
  try {
    // 1. Secondary (non-Founder) Admin: edit name+rank, archive, verify NO permanent delete button, restore, archive again
    const secCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const secPage = await secCtx.newPage();
    await loginThroughApi(secPage, SEC_ADMIN_EMAIL, PASSWORD);
    await openAssetsTab(secPage, ASSET_NAME);

    const row1 = secPage.locator('.workspace-row', { hasText: ASSET_NAME }).first();
    await row1.getByRole('button', { name: /Sửa vật phẩm|Edit asset/i }).click();
    const dialog1 = secPage.locator('dialog[open]');
    await dialog1.waitFor({ state: 'visible' });
    await dialog1.locator('input:not([disabled])').fill(renamed);
    await dialog1.locator('select').selectOption('B');
    await dialog1.getByRole('button', { name: /Xác nhận|Confirm/i }).click();
    await dialog1.waitFor({ state: 'hidden' });

    await secPage.locator('#admin-search-input').fill(renamed);
    await secPage.locator('#admin-search-input').press('Enter');
    const rowRenamed = secPage.locator('.workspace-row', { hasText: renamed }).first();
    await rowRenamed.waitFor({ state: 'visible' });

    // Archive
    await rowRenamed.getByRole('button', { name: /Ngừng lưu hành|Archive asset/i }).click();
    await secPage.locator('dialog[open]').getByRole('button', { name: /Xác nhận|Confirm/i }).click();
    await secPage.locator('dialog[open]').waitFor({ state: 'hidden' });
    await rowRenamed.getByText(/Ngừng lưu hành|Archived/i).waitFor({ state: 'visible' });

    // Non-Founder Admin MUST NOT see Permanent Delete button
    const secPermCount = await rowRenamed.getByRole('button', { name: /Xóa vĩnh viễn|Permanently delete/i }).count();
    assert.equal(secPermCount, 0, 'Non-Founder Admin must not see permanent delete button');

    // Restore
    await rowRenamed.getByRole('button', { name: /Khôi phục|Restore asset/i }).click();
    await secPage.locator('dialog[open]').getByRole('button', { name: /Xác nhận|Confirm/i }).click();
    await secPage.locator('dialog[open]').waitFor({ state: 'hidden' });
    await rowRenamed.getByText(/Đang hoạt động|Active/i).waitFor({ state: 'visible' });

    // Archive again for Founder permanent delete
    await rowRenamed.getByRole('button', { name: /Ngừng lưu hành|Archive asset/i }).click();
    await secPage.locator('dialog[open]').getByRole('button', { name: /Xác nhận|Confirm/i }).click();
    await secPage.locator('dialog[open]').waitFor({ state: 'hidden' });
    await secCtx.close();

    // 2. Founder Khang Dev: sees Permanent Delete on Archived row, modal requires "XÓA VĨNH VIỄN", deletes cleanly
    const founderCtx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const fPage = await founderCtx.newPage();
    await loginThroughApi(fPage, 'khang_dev@example.com', PASSWORD);
    await openAssetsTab(fPage, renamed);

    const fRow = fPage.locator('.workspace-row', { hasText: renamed }).first();
    await fRow.waitFor({ state: 'visible' });
    const permBtn = fRow.getByRole('button', { name: /Xóa vĩnh viễn|Permanently delete/i });
    assert.equal(await permBtn.count(), 1, 'Founder must see permanent delete button on Archived asset');
    await permBtn.click();

    const delDialog = fPage.locator('dialog[open]');
    await delDialog.waitFor({ state: 'visible' });
    const submitBtn = delDialog.getByRole('button', { name: /Xóa vĩnh viễn|Permanently delete/i });
    assert.equal(await submitBtn.isDisabled(), true, 'Submit must be disabled before typing XÓA VĨNH VIỄN');
    await delDialog.locator('input').fill('XÓA VĨNH VIỄN');
    assert.equal(await submitBtn.isDisabled(), false, 'Submit must be enabled after typing XÓA VĨNH VIỄN');
    await submitBtn.click();
    await delDialog.waitFor({ state: 'hidden' });

    await fPage.locator('.workspace-success').waitFor({ state: 'visible' });
    assert.equal(await fPage.locator('.workspace-row', { hasText: renamed }).count(), 0, 'Deleted asset must disappear from Admin list');

    // Mobile viewport overflow check
    await fPage.setViewportSize({ width: 390, height: 844 });
    const hasOverflow = await fPage.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    assert.equal(hasOverflow, false, 'Mobile Admin Assets page must not overflow horizontally');
    await founderCtx.close();

    console.log('H06 Playwright E2E PASS: secondary Admin + Founder permanent delete verified.');
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
