import { test, expect } from '@playwright/test';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const testUser = {
  id: uuid(1),
  username: 'test_cultivator',
  display_name: 'Test Cultivator',
  roles: ['USER'],
  status: 'active',
  avatar_url: null,
};

// 70 Meme avatars + 5 Backgrounds
const memeAssets = Array.from({ length: 70 }, (_, i) => ({
  id: uuid(100 + i),
  slug: `meme-avatar-${i + 1}`,
  kind: 'avatar',
  display_name: `Meme Thần Thú #${i + 1}`,
  rarity: i === 0 ? 'S' : i < 5 ? 'A' : i < 15 ? 'B' : i < 35 ? 'C' : 'D',
  effect_key: null,
  available: true,
  media_url: `/api/v1/catalog/assets/${uuid(100 + i)}`,
}));

const bgAssets = [
  { id: uuid(200), slug: 'bg-1', kind: 'background', display_name: 'Deep Sea Abyss', rarity: 'S', effect_key: 'lucian-352-deep-sea', available: true, media_url: `/api/v1/catalog/assets/${uuid(200)}` },
  { id: uuid(201), slug: 'bg-2', kind: 'background', display_name: 'Neon Ripple', rarity: 'A', effect_key: 'lucian-363', available: true, media_url: `/api/v1/catalog/assets/${uuid(201)}` },
  { id: uuid(202), slug: 'bg-3', kind: 'background', display_name: 'Cyber Beams', rarity: 'B', effect_key: 'lucian-226', available: true, media_url: `/api/v1/catalog/assets/${uuid(202)}` },
  { id: uuid(203), slug: 'bg-4', kind: 'background', display_name: 'Cosmic Stars', rarity: 'C', effect_key: 'lucian-330', available: true, media_url: `/api/v1/catalog/assets/${uuid(203)}` },
  { id: uuid(204), slug: 'bg-5', kind: 'background', display_name: 'Violet Base', rarity: 'D', effect_key: 'violet-base', available: true, media_url: `/api/v1/catalog/assets/${uuid(204)}` },
];

const allAssets = [...memeAssets, ...bgAssets];

test('Vault Browser Smoke Test: 70 memes, 5 bgs, roulette, receipt, inventory persistence, equipment, +2 EXP', async ({ page, context }) => {
  const ownedQuantities = new Map();
  const equipment = { avatar: null, background: null };
  let earnedXp = 0;
  const openedKeys = new Set();

  await context.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.slice('/api/v1'.length);
    const method = request.method();
    const idempotencyKey = request.headers()['idempotency-key'];

    const send = (status, data) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: status === 204 ? '' : JSON.stringify(data),
      });

    // 1x1 png image
    if (path.startsWith('/catalog/assets/')) {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6S8AAAAASUVORK5CYII=', 'base64'),
      });
    }

    if (path === '/users/me') {
      const u = { ...testUser };
      if (equipment.avatar) {
        const a = allAssets.find((x) => x.id === equipment.avatar);
        if (a) u.avatar_url = a.media_url;
      }
      return send(200, u);
    }

    if (path === '/auth/csrf') return send(200, { csrf_token: 'vault-smoke-csrf' });
    if (path === '/categories' || path === '/posts') return send(200, { items: [], pagination: { total: 0 } });

    if (path === '/aura/progress') {
      return send(200, {
        earned_xp: earnedXp,
        bonus_xp: 0,
        total_xp: earnedXp,
        level: Math.floor(earnedXp / 100) + 1,
        fair_level: Math.floor(earnedXp / 100) + 1,
        streak_days: 1,
        checked_in: true,
      });
    }

    if (path === '/vault/cases') {
      return send(200, {
        items: [
          { id: uuid(10), runtime_kind: 'avatar', label: 'Rương Meme', cost_khi_van: 0, status: 'active' },
          { id: uuid(11), runtime_kind: 'background', label: 'Rương Background', cost_khi_van: 0, status: 'active' },
        ],
      });
    }

    if (/^\/vault\/cases\/[^/]+$/.test(path)) {
      const isMeme = path.includes(uuid(10));
      return send(200, {
        case: {
          id: isMeme ? uuid(10) : uuid(11),
          runtime_kind: isMeme ? 'avatar' : 'background',
          label: isMeme ? 'Rương Meme' : 'Rương Background',
          cost_khi_van: 0,
          status: 'active',
        },
        bands: [
          {
            min_earned_xp: 0,
            max_earned_xp: null,
            odds_version: 1,
            weights_bps: { D: 6890, C: 2000, B: 1000, A: 100, S: 10 },
          },
        ],
      });
    }

    if (path === '/catalog') {
      const kind = url.searchParams.get('kind');
      const pageNum = Number(url.searchParams.get('page') || 1);
      const pageSize = Number(url.searchParams.get('page_size') || 100);
      const filtered = allAssets.filter((a) => a.kind === kind);
      const items = filtered.slice((pageNum - 1) * pageSize, pageNum * pageSize).map((a) => ({
        asset: a,
        owned: ownedQuantities.has(a.id),
      }));
      return send(200, {
        items,
        pagination: { page: pageNum, page_size: pageSize, total: filtered.length, total_pages: Math.ceil(filtered.length / pageSize) },
      });
    }

    if (path === '/inventory/me') {
      const kind = url.searchParams.get('kind');
      const pageNum = Number(url.searchParams.get('page') || 1);
      const pageSize = Number(url.searchParams.get('page_size') || 100);
      const filtered = allAssets.filter((a) => a.kind === kind && ownedQuantities.has(a.id));
      const items = filtered.slice((pageNum - 1) * pageSize, pageNum * pageSize).map((a) => ({
        asset: a,
        quantity: ownedQuantities.get(a.id),
        equipped: equipment[kind] === a.id,
      }));
      return send(200, {
        items,
        pagination: { page: pageNum, page_size: pageSize, total: filtered.length, total_pages: Math.ceil(filtered.length / pageSize) },
      });
    }

    if (path === '/inventory/equipment') {
      return send(200, {
        items: Object.entries(equipment)
          .filter(([, id]) => Boolean(id))
          .map(([slot_kind, id]) => ({ slot_kind, asset: allAssets.find((a) => a.id === id) })),
      });
    }

    if (path.startsWith('/inventory/equipment/') && method === 'PUT') {
      const slot = path.split('/').at(-1);
      const body = request.postDataJSON();
      equipment[slot] = body.asset_id;
      return send(200, { slot_kind: slot, asset_id: body.asset_id });
    }

    if (path.startsWith('/vault/opens/by-request')) {
      const isMeme = true;
      const reward = memeAssets[0];
      return send(200, {
        open_id: uuid(999),
        case_id: uuid(10),
        cost_khi_van: 0,
        khi_van_balance: 0,
        reward,
        already_processed: true,
        next_open_at: new Date(Date.now() - 1000).toISOString(),
      });
    }

    if (path.endsWith('/open') && method === 'POST') {
      const isMeme = path.includes(uuid(10));
      const reward = isMeme ? memeAssets[0] : bgAssets[0]; // Meme #1 or Deep Sea Abyss
      const caseId = isMeme ? uuid(10) : uuid(11);

      if (idempotencyKey && openedKeys.has(idempotencyKey)) {
        return send(200, {
          open_id: uuid(900 + openedKeys.size),
          case_id: caseId,
          cost_khi_van: 0,
          khi_van_balance: 0,
          reward,
          already_processed: true,
          next_open_at: new Date(Date.now() - 1000).toISOString(),
        });
      }

      if (idempotencyKey) openedKeys.add(idempotencyKey);
      ownedQuantities.set(reward.id, (ownedQuantities.get(reward.id) || 0) + 1);
      earnedXp += 2;

      return send(200, {
        open_id: uuid(900 + openedKeys.size),
        case_id: caseId,
        cost_khi_van: 0,
        khi_van_balance: 0,
        reward,
        already_processed: false,
        next_open_at: new Date(Date.now() - 1000).toISOString(),
      });
    }

    return send(200, {});
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/vault');

  // Step 1: Check Meme tab active by default and 70 meme items present (paginated 15 per page, 5 pages)
  const memeTabBtn = page.getByRole('button', { name: 'Rương Meme', exact: true });
  await expect(memeTabBtn).toHaveAttribute('aria-pressed', 'true');
  const memeCards = page.locator('.vault-item-card');
  await expect(memeCards).toHaveCount(15);
  await expect(page.locator('.vault-pagination')).toContainText('1 / 5');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/vault_browser_smoke_meme_tab.png` });

  // Step 2: Switch to Background tab and check 5 backgrounds present
  const bgTabBtn = page.getByRole('button', { name: 'Rương Background', exact: true });
  await bgTabBtn.click();
  await expect(bgTabBtn).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.vault-item-card')).toHaveCount(5);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/vault_browser_smoke_bg_tab.png` });

  // Step 3: Open Background chest -> roulette animation & receipt modal
  const openBtn = page.getByRole('button', { name: 'Mở Rương', exact: true });
  await expect(openBtn).toBeEnabled();
  await openBtn.click();

  // Check receipt dialog appears with rarity and reward details
  const receiptDialog = page.getByRole('dialog');
  await expect(receiptDialog).toBeVisible({ timeout: 10000 });
  await expect(receiptDialog.getByText('Deep Sea Abyss')).toBeVisible();
  await page.screenshot({ path: `${ARTIFACTS_DIR}/vault_browser_smoke_receipt_modal.png` });

  // Equip Background
  const equipBgBtn = receiptDialog.getByRole('button', { name: 'Trang bị Background', exact: true });
  await equipBgBtn.click();
  await expect(receiptDialog).toBeHidden();

  // Step 4: Switch back to Meme tab and open Meme chest
  await memeTabBtn.click();
  await expect(openBtn).toBeEnabled();
  await openBtn.click();

  const memeReceiptDialog = page.getByRole('dialog');
  await expect(memeReceiptDialog).toBeVisible({ timeout: 10000 });
  await expect(memeReceiptDialog.getByText('Meme Thần Thú #1')).toBeVisible();

  // Equip Avatar
  const equipAvatarBtn = memeReceiptDialog.getByRole('button', { name: 'Trang bị Avatar', exact: true });
  await equipAvatarBtn.click();
  await expect(memeReceiptDialog).toBeHidden();

  // Step 5: Reload page and verify inventory & equipment persistence
  await page.reload();
  await expect(page.locator('.global-background')).toHaveAttribute('data-effect', 'lucian-352-deep-sea');
  await expect(page.getByRole('button', { name: 'Dùng Avatar mặc định', exact: true })).toBeEnabled();
  await expect(memeCards.first()).toContainText('Đang trang bị');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/vault_browser_smoke_equipped.png` });

  // Step 6: Verify Aura progress earned +4 EXP (+2 for each of the 2 opens)
  const progress = await page.evaluate(async () => {
    const res = await fetch('/api/v1/aura/progress');
    return res.json();
  });
  expect(progress.earned_xp).toBe(4);
});
