import { test, expect } from '@playwright/test';
import path from 'node:path';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

test('Capture All Checkpoint QA Evidence Screenshots', async ({ page, context }) => {
  test.setTimeout(90000);
  await page.setViewportSize({ width: 1440, height: 900 });

  // Cookie consent
  await page.addInitScript(() => {
    localStorage.setItem('aurameme-cookie-consent-v1', JSON.stringify({
      version: 1,
      essential: true,
      optional: false,
      updatedAt: '2026-11-20T10:00:00Z',
    }));
  });

  const normalUser = {
    id: id(1),
    username: 'khang_dev',
    display_name: 'Khang Dev',
    roles: ['USER'],
    status: 'active',
    email: 'khang@aurameme.com',
  };

  const adminUser = {
    id: id(2),
    username: 'admin_qa',
    display_name: 'Admin QA',
    roles: ['USER', 'ADMIN'],
    status: 'active',
    email: 'admin@aurameme.com',
  };

  let currentUser = null;

  await context.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname.replace('/api/v1', '');
    const send = (status, data) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: status === 204 ? '' : JSON.stringify(data),
      });

    if (p === '/users/me') {
      return currentUser ? send(200, currentUser) : send(401, { error: { code: 'UNAUTHORIZED' } });
    }
    if (p === '/auth/csrf') return send(200, { csrf_token: 'evidence-csrf' });
    if (p === '/posts' || p === '/categories') return send(200, { items: [], pagination: { total: 0 } });
    if (p === '/aura/progress') {
      return send(200, {
        earned_xp: 15,
        bonus_xp: 0,
        total_xp: 15,
        level: 1,
        fair_level: 1,
        realm: 'Luyện Khí',
        streak_days: 1,
        checked_in: true,
      });
    }

    if (p === '/admin/users') {
      return send(200, {
        items: [
          adminUser,
          normalUser,
          {
            id: id(3),
            username: 'deleted_user',
            display_name: 'Deleted Cultivator',
            roles: ['USER'],
            status: 'deleted',
            deleted_at: new Date(Date.now() - 5 * 86400000).toISOString(),
          },
        ],
        pagination: { page: 1, page_size: 20, total: 3, total_pages: 1 },
      });
    }

    if (p === '/admin/assets') {
      return send(200, {
        items: [
          {
            id: id(100),
            slug: 'S_231126_01',
            display_name: 'Thần Thú Thanh Long',
            kind: 'avatar',
            rarity: 'S',
            active: false,
            review_status: 'pending',
            media_url: '/assets/brand/symbol-dark-2048.png',
          },
          {
            id: id(101),
            slug: 'bg-deep-sea',
            display_name: 'Deep Sea Abyss',
            kind: 'background',
            rarity: 'S',
            active: true,
            review_status: 'approved',
            effect_key: 'lucian-352-deep-sea',
          },
        ],
        pagination: { page: 1, page_size: 20, total: 2, total_pages: 1 },
      });
    }

    if (p.startsWith('/admin/assets/') && p.endsWith('/media')) {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6S8AAAAASUVORK5CYII=', 'base64'),
      });
    }

    return send(200, { items: [], pagination: { total: 0 } });
  });

  // 1. qa_17_search_header_fix.png
  console.log('Capturing qa_17_search_header_fix.png...');
  currentUser = normalUser;
  await page.goto('/');
  const searchInput = page.locator('.site-search input').first();
  await searchInput.fill('cyber');
  await page.keyboard.press('Backspace');
  await page.keyboard.press('Backspace');
  await searchInput.fill('tu tien');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/q=tu\+tien/);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_17_search_header_fix.png') });

  // 3. qa_19_contact_identity_locked.png
  console.log('Capturing qa_19_contact_identity_locked.png...');
  await page.goto('/contact');
  await expect(page.locator('.am-contact-lock-icon').first()).toBeVisible();
  await expect(page.locator('#contact-name')).toHaveValue('Khang Dev');
  await expect(page.locator('#contact-email')).toHaveValue('khang@aurameme.com');
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_19_contact_identity_locked.png') });

  // 4. qa_20_lucian_401_google_button.png
  console.log('Capturing qa_20_lucian_401_google_button.png...');
  currentUser = null;
  await page.goto('/login');
  await expect(page.locator('.u401-b')).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_20_lucian_401_google_button.png') });

  // 5. qa_21_lucian_244_register_validation.png
  console.log('Capturing qa_21_lucian_244_register_validation.png...');
  await page.goto('/register');
  await page.locator('#submitBtn').click();
  await expect(page.locator('.u244-sm')).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_21_lucian_244_register_validation.png') });

  // 6. qa_22_register_privacy_checkbox.png
  console.log('Capturing qa_22_register_privacy_checkbox.png...');
  const checkboxWrap = page.locator('.u244-ag-wrap');
  await checkboxWrap.scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_22_register_privacy_checkbox.png') });

  // 7. qa_23_admin_sidebar_cleaned.png
  console.log('Capturing qa_23_admin_sidebar_cleaned.png...');
  currentUser = adminUser;
  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Không gian quản trị', exact: true })).toBeVisible();
  await expect(page.locator('.admin-nav-caption')).toHaveCount(0);
  await expect(page.locator('.admin-access-note')).toHaveCount(0);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_23_admin_sidebar_cleaned.png') });

  // 8. qa_24_admin_users_30day_restore.png
  console.log('Capturing qa_24_admin_users_30day_restore.png...');
  await expect(page.locator('[data-admin-id]').nth(2)).toContainText('ngày khôi phục');
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_24_admin_users_30day_restore.png') });

  // 9. qa_25_admin_catalog_meme_upload.png
  console.log('Capturing qa_25_admin_catalog_meme_upload.png...');
  await page.locator('.workspace-tabs button').filter({ hasText: 'Kiểm duyệt' }).click();
  await page.locator('.workspace-subtabs button').filter({ hasText: 'Trạng thái vật phẩm' }).click();
  await expect(page.locator('.admin-add-asset-btn')).toBeVisible();
  await page.locator('.admin-add-asset-btn').click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.admin-asset-upload-modal')).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_25_admin_catalog_meme_upload.png') });
  await page.getByRole('dialog').getByRole('button', { name: 'Hủy' }).click();

  // 10. qa_26_admin_catalog_pending_preview.png
  console.log('Capturing qa_26_admin_catalog_pending_preview.png...');
  const firstRowView = page.locator(`[data-admin-id="${id(100)}"] .admin-icon-btn`).first();
  await firstRowView.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.admin-asset-preview-modal')).toBeVisible();
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_26_admin_catalog_pending_preview.png') });
});
