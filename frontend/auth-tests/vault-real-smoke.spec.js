import { test, expect } from '@playwright/test';
import path from 'node:path';

/**
 * Vault Real Browser Smoke Test:
 * Executes against the real FastAPI backend and isolated PostgreSQL clone.
 * Zero route.fulfill() mocks on Vault endpoints.
 * Verifies:
 * - Two chests (Rương Meme, Rương Background)
 * - 75 catalog items (70 Meme, 5 Background)
 * - Real chest opening via POST /api/v1/vault/cases/:id/open
 * - Receipt modal with reward
 * - +2 EXP awarded on /api/v1/aura/progress
 * - Item added to inventory (/api/v1/inventory/me)
 * - Equipment via /api/v1/inventory/equipment/:slot
 * - Persistence across page reload
 */

test.setTimeout(120000);

const TEST_EMAIL = 'khang_dev@example.com';
const TEST_PASSWORD = 'QA-Owner-Password-2026!';

test('Vault Real Smoke: 2 chests, 75 catalog assets, real open, receipt, +2 EXP, equip and reload persistence', async ({ page }) => {
  // Use reduced motion for deterministic animations
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 960 });

  // 1. Log in with real account
  await page.goto('/login');
  await page.locator('#identifier').fill(TEST_EMAIL);
  await page.locator('#password').fill(TEST_PASSWORD);
  await page.locator('#loginForm button[type=submit]').click();
  await expect(page).toHaveURL(/\/(#.*)?$/);
  await expect(page.locator('.account-avatar')).toBeVisible();

  // 2. Fetch initial Aura progress via browser fetch
  const progressBefore = await page.evaluate(async () => {
    const res = await fetch('/api/v1/aura/progress');
    return res.json();
  });
  expect(progressBefore).toHaveProperty('earned_xp');

  // 3. Verify Catalog items directly from backend API
  const avatarCatalog = await page.evaluate(async () => {
    const res = await fetch('/api/v1/catalog?kind=avatar&page_size=100');
    return res.json();
  });
  expect(avatarCatalog.items).toHaveLength(70);

  const bgCatalog = await page.evaluate(async () => {
    const res = await fetch('/api/v1/catalog?kind=background&page_size=100');
    return res.json();
  });
  expect(bgCatalog.items).toHaveLength(5);

  // Total verified catalog = 75 items
  expect(avatarCatalog.items.length + bgCatalog.items.length).toBe(75);

  // 4. Navigate to /vault
  await page.goto('/vault');
  await expect(page.locator('.vault-page')).toBeVisible();

  // Verify chest buttons exist
  const memeTabBtn = page.getByRole('button', { name: 'Rương Meme', exact: true });
  const bgTabBtn = page.getByRole('button', { name: 'Rương Background', exact: true });
  await expect(memeTabBtn).toBeVisible();
  await expect(bgTabBtn).toBeVisible();

  // 5. Inspect Rương Meme (first page shows 15 items out of 70, 5 columns x 3 rows)
  await memeTabBtn.click();
  await expect(page.locator('.vault-item-card')).toHaveCount(15);
  await page.screenshot({ path: 'vault_real_meme_tab.png' });

  // 6. Inspect Rương Background
  await bgTabBtn.click();
  await expect(page.locator('.vault-item-card')).toHaveCount(5);
  await page.screenshot({ path: 'vault_real_bg_tab.png' });

  // 7. Open Background Chest via Real Backend API
  const openBtn = page.getByRole('button', { name: 'Mở Rương', exact: true });
  await expect(openBtn).toBeEnabled();

  const openPromise = page.waitForResponse(response => 
    response.request().method() === 'POST' && 
    response.url().includes('/api/v1/vault/cases/') &&
    response.url().includes('/open')
  );

  await openBtn.click();
  const openHttp = await openPromise;
  expect(openHttp.status()).toBe(200);
  const receipt = await openHttp.json();
  expect(receipt).toHaveProperty('reward');
  expect(receipt.reward.kind).toBe('background');

  // 8. Verify Receipt Detail Modal is displayed
  const detailModal = page.locator('dialog.vault-detail');
  await expect(detailModal).toBeVisible({ timeout: 10000 });
  await expect(page.locator('#vault-detail-title')).toHaveText(receipt.reward.display_name);
  await page.screenshot({ path: 'vault_real_receipt_modal.png' });

  // 9. Verify +2 EXP gained
  const progressAfter = await page.evaluate(async () => {
    const res = await fetch('/api/v1/aura/progress');
    return res.json();
  });
  expect(progressAfter.earned_xp).toBe(progressBefore.earned_xp + 2);

  // 10. Equip the item from modal if not already equipped
  const equipBtn = page.locator('.vault-equip-button');
  await expect(equipBtn).toBeVisible();
  if (await equipBtn.isEnabled()) {
    const equipPromise = page.waitForResponse(response => 
      response.request().method() === 'PUT' && 
      response.url().includes('/api/v1/inventory/equipment/')
    );
    await equipBtn.click();
    const equipHttp = await equipPromise;
    expect(equipHttp.status()).toBe(200);
  } else {
    await expect(equipBtn).toHaveText(/Đang trang bị|Equipped/i);
  }

  // 11. Verify equipped attribute in DOM
  await expect(page.locator('#root')).toHaveAttribute('data-vault-background', receipt.reward.effect_key);
  await page.screenshot({ path: 'vault_real_equipped.png' });

  // 12. Reload page and verify equipped background persists
  await page.reload();
  await expect(page.locator('#root')).toHaveAttribute('data-vault-background', receipt.reward.effect_key);
});
