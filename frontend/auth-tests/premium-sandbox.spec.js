import { test, expect } from '@playwright/test';

const pageErrors = new WeakMap();
test.beforeEach(({ page }) => {
  const errors = [];
  pageErrors.set(page, errors);
  page.on('pageerror', (e) => errors.push(e.message));
});
test.afterEach(({ page }) => {
  expect(pageErrors.get(page)).toEqual([]);
});

const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const now = '2026-11-14T00:00:00Z';

async function setupMockApi(context, identity = 0, initialSub = null, vnpayApproved = false) {
  const users = ['khang_dev', 'kien_dev', 'giga_user'].map((username, n) => ({
    id: id(n + 1),
    username,
    display_name: username,
    roles: ['USER'],
    status: 'active',
  }));

  let currentSubscription = initialSub;
  const requests = [];

  await context.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.slice('/api/v1'.length);
    const method = request.method();
    let body;
    try {
      body = request.postDataJSON();
    } catch {}
    requests.push({ path, method, body, csrf: request.headers()['x-csrf-token'] });

    const send = (status, data) =>
      route.fulfill({
        status,
        contentType: 'application/json',
        body: status === 204 ? '' : JSON.stringify(data),
      });
    const fail = (status, code) => send(status, { error: { code, message: 'safe' } });

    if (path === '/users/me') {
      return identity === null ? fail(401, 'UNAUTHORIZED') : send(200, users[identity]);
    }
    if (path === '/auth/csrf') {
      return send(200, { csrf_token: 'server-csrf-test-token' });
    }

    if (path === '/premium/status') {
      return send(200, {
        subscription: currentSubscription,
        vnpay_configured: vnpayApproved,
        plans: [
          {
            tier: 'plus',
            name: 'Aura Plus',
            duration_days: 30,
            boost_multiplier: 2,
            amount_usd_formatted: '$5',
            amount_vnd: 130000,
            amount_vnd_formatted: '130.000 đ',
          },
          {
            tier: 'prime',
            name: 'Aura Prime',
            duration_days: 365,
            boost_multiplier: 3,
            amount_usd_formatted: '$50',
            amount_vnd: 1250000,
            amount_vnd_formatted: '1.250.000 đ',
          },
        ],
      });
    }

    if (path.startsWith('/premium/orders/') && method === 'GET') {
      const code = path.split('/')[3];
      return send(200, {
        order_code: code,
        tier: currentSubscription?.tier || 'plus',
        duration_days: currentSubscription?.tier === 'prime' ? 365 : 30,
        amount_usd_cents: currentSubscription?.tier === 'prime' ? 5000 : 500,
        amount_usd_formatted: currentSubscription?.tier === 'prime' ? '$50' : '$5',
        amount_vnd: currentSubscription?.tier === 'prime' ? 1250000 : 130000,
        status: currentSubscription ? 'success' : 'pending',
        provider: 'vnpay_sandbox',
      });
    }

    if (path === '/premium/orders' && method === 'POST') {
      if (request.headers()['x-csrf-token'] !== 'server-csrf-test-token') {
        return fail(403, 'CSRF_INVALID');
      }
      const orderCode = 'AM-SUB-TEST-1234';
      const isVnpay = body.provider === 'vnpay_sandbox';
      return send(201, {
        order_code: orderCode,
        plan_tier: body.plan_tier,
        amount_usd_cents: body.plan_tier === 'plus' ? 500 : 5000,
        provider: body.provider,
        payment_url: isVnpay ? 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?vnp_TxnRef=' + orderCode : null,
      });
    }

    if (path.startsWith('/premium/orders/') && path.endsWith('/simulate') && method === 'POST') {
      if (request.headers()['x-csrf-token'] !== 'server-csrf-test-token') {
        return fail(403, 'CSRF_INVALID');
      }
      if (body.action === 'pay_success') {
        currentSubscription = {
          tier: 'plus',
          is_active: true,
          days_remaining: 30,
          expires_at: '2026-12-14T00:00:00Z',
          starts_at: now,
          boost_multiplier: 2.0,
        };
        return send(200, {
          status: 'success',
          subscription: currentSubscription,
          order_code: 'AM-SUB-TEST-1234',
        });
      }
      return send(200, {
        status: 'failed',
        subscription: null,
        order_code: 'AM-SUB-TEST-1234',
      });
    }

    if (path === '/premium/vnpay-return' && method === 'GET') {
      const code = url.searchParams.get('vnp_ResponseCode');
      if (code === '00') {
        currentSubscription = {
          tier: 'prime',
          is_active: true,
          days_remaining: 365,
          expires_at: '2027-11-14T00:00:00Z',
          starts_at: now,
          boost_multiplier: 3.0,
        };
        return route.fulfill({
          status: 302,
          headers: {
            Location: '/premium?vnp_status=success&order_code=AM-SUB-TEST-1234',
          },
        });
      }
      return route.fulfill({
        status: 302,
        headers: {
          Location: '/premium?vnp_status=failed&message=' + (code || '99'),
        },
      });
    }

    return fail(404, 'NOT_FOUND');
  });

  return { requests, getCurrentSub: () => currentSubscription };
}

test('Premium displays $5 and $50 across VI/EN and Dark/Light themes', async ({ page, context }) => {
  await setupMockApi(context, null);
  await page.emulateMedia({ reducedMotion: 'reduce' });

  for (const theme of ['dark', 'light']) {
    for (const language of ['vi', 'en']) {
      await page.goto('/premium');
      await page.evaluate((p) => localStorage.setItem('aurameme-ui-preferences', JSON.stringify(p)), {
        theme,
        language,
      });
      await page.goto('/premium');

      // Verify header and kicker
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Aura Memberships');

      // Verify exact prices $5 and $50
      const content = await page.locator('.premium-selector-panel').innerText();
      expect(content).toContain('$5');
      expect(content).toContain('$50');

      // Verify no obsolete "Giá chưa công bố" or commercial clutter
      expect(content).not.toContain('Giá chưa công bố');
      expect(content).not.toContain('Pricing is not announced');
      expect(content).not.toMatch(/2 months free|Basic|Start Pro/);

      // Verify duration pills
      await expect(page.locator('.premium-plan')).toHaveCount(2);
      await expect(page.locator('.premium-plus')).toContainText(language === 'en' ? '30 days' : '30 ngày');
      await expect(page.locator('.premium-prime')).toContainText(language === 'en' ? '365 days' : '365 ngày');
    }
  }
});

test('Guest clicking CTA redirects to /login?next=%2Fpremium', async ({ page, context }) => {
  await setupMockApi(context, null);
  await page.goto('/premium');

  const cta = page.locator('.u056-cta');
  await expect(cta).toBeVisible();
  await expect(cta).toBeEnabled();
  await expect(cta).toContainText('Đăng nhập');

  await cta.click();
  await expect(page).toHaveURL(/\/login\?next=%2Fpremium$/);
});

test('Logged in user can open Sandbox modal, simulate successful payment, and see active badge', async ({ page, context }) => {
  const s = await setupMockApi(context, 0, null, false);
  await page.goto('/premium');

  // Verify initial state: no active banner
  await expect(page.locator('.premium-active-banner')).toHaveCount(0);

  // Click CTA to open sandbox dialog
  const cta = page.locator('.u056-cta');
  await expect(cta).toBeVisible();
  await expect(cta).toContainText('Mua gói Plus ($5)');
  await cta.click();

  // Verify dialog is open
  const dialog = page.locator('.premium-sandbox-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#sandbox-dialog-title')).toContainText('Xác nhận đơn hàng — Gói Aura Plus');
  await expect(dialog.locator('.sandbox-price-usd')).toContainText('$5 USD');

  // VNPAY should be disabled because pricing is not approved
  const vnpayBtn = dialog.locator('.sandbox-btn-vnpay');
  await expect(vnpayBtn).toBeDisabled();
  await expect(vnpayBtn).toContainText('Chờ duyệt giá VND');

  // Click Simulate Instant Payment (Success)
  const successBtn = dialog.locator('.sandbox-btn-success');
  await successBtn.click();

  // Verify success alert inside dialog
  const alert = dialog.locator('.sandbox-result-box.success');
  await expect(alert).toBeVisible();
  await expect(alert).toContainText('Kích hoạt thành công gói Aura Plus');

  // Close dialog
  await dialog.locator('.workspace-dialog-actions button').click();
  await expect(dialog).not.toBeVisible();

  // Verify active banner is now visible on page
  const banner = page.locator('.premium-active-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('Gói đang kích hoạt: Aura PLUS');
  await expect(banner).toContainText('30 ngày');

  // Verify CTA now shows active plan status
  await expect(cta).toContainText('Gói đang kích hoạt');

  // Verify CSRF token accompanied the mutation
  const orderReq = s.requests.find((r) => r.path === '/premium/orders' && r.method === 'POST');
  expect(orderReq).toBeDefined();
  expect(orderReq.csrf).toBe('server-csrf-test-token');
  expect(orderReq.body).toEqual({ plan_tier: 'plus', provider: 'sandbox_simulated' });
});

test('Logged in user can simulate payment failure without corrupting state', async ({ page, context }) => {
  await setupMockApi(context, 0, null, false);
  await page.goto('/premium');

  await page.locator('.u056-cta').click();
  const dialog = page.locator('.premium-sandbox-dialog');
  await expect(dialog).toBeVisible();

  // Click Simulate Failure
  const failBtn = dialog.locator('.sandbox-btn-fail');
  await failBtn.click();

  // Verify failure notice inside dialog
  const alert = dialog.locator('.sandbox-result-box.error');
  await expect(alert).toBeVisible();
  await expect(alert).toContainText('thất bại');

  // Close dialog
  await dialog.locator('.workspace-dialog-actions button').click();

  // Active banner should still not exist
  await expect(page.locator('.premium-active-banner')).toHaveCount(0);
});

test('VNPAY return callback in URL updates subscription state and displays notice', async ({ page, context }) => {
  await setupMockApi(context, 0, null, true);
  await page.goto('/premium?vnp_ResponseCode=00&vnp_TxnRef=AM-SUB-TEST-1234&vnp_SecureHash=mockhash');

  // Page should verify return and show success banner
  await expect(page.locator('.premium-notice-banner.success')).toBeVisible();
  await expect(page.locator('.premium-notice-banner.success')).toContainText('Thanh toán VNPAY thành công');

  // Active banner should display prime membership
  await expect(page.locator('.premium-active-banner')).toBeVisible();
  await expect(page.locator('.premium-active-banner')).toContainText('Aura PRIME');
  await expect(page.locator('.premium-active-banner')).toContainText('365 ngày');

  // URL query params should be cleared
  expect(new URL(page.url()).search).toBe('');
});

test('Header button, avatar indicators, and Home Aura Perks card sync with subscription state', async ({ page, context }) => {
  // Test Free user:
  await setupMockApi(context, 0, null, false);
  await page.goto('/');

  const freeHeaderBtn = page.locator('.header-premium-btn');
  await expect(freeHeaderBtn).toBeVisible();
  await expect(freeHeaderBtn).toHaveClass(/header-premium-btn--free/);
  await expect(freeHeaderBtn).toContainText('Mua Aura');
  await expect(page.locator('.aura-member-badge')).toHaveCount(0);
  await expect(page.locator('.aura-avatar--plus, .aura-avatar--prime')).toHaveCount(0);

  // Test Plus subscriber:
  const plusSub = {
    tier: 'plus',
    is_active: true,
    days_remaining: 30,
    expires_at: '2026-12-14T00:00:00Z',
    starts_at: now,
    boost_multiplier: 2.0,
  };
  await setupMockApi(context, 0, plusSub, false);
  await page.goto('/');

  const plusHeaderBtn = page.locator('.header-premium-btn');
  await expect(plusHeaderBtn).toBeVisible();
  await expect(plusHeaderBtn).toHaveClass(/header-premium-btn--plus/);
  await expect(plusHeaderBtn).toContainText('Aura Plus');
  await expect(page.locator('.account-avatar')).toHaveClass(/aura-avatar--plus/);
  await expect(page.locator('.aura-member-badge')).toBeVisible();

  // Test Prime subscriber:
  const primeSub = {
    tier: 'prime',
    is_active: true,
    days_remaining: 365,
    expires_at: '2027-11-14T00:00:00Z',
    starts_at: now,
    boost_multiplier: 3.0,
  };
  await setupMockApi(context, 0, primeSub, false);
  await page.goto('/');

  const primeHeaderBtn = page.locator('.header-premium-btn');
  await expect(primeHeaderBtn).toBeVisible();
  await expect(primeHeaderBtn).toHaveClass(/header-premium-btn--prime/);
  await expect(primeHeaderBtn).toContainText('Aura Prime');
  await expect(page.locator('.account-avatar')).toHaveClass(/aura-avatar--prime/);
  await expect(page.locator('.aura-member-badge')).toBeVisible();

  // Verify Home Aura Perks card reflects Prime
  const perksCard = page.locator('.font-headline-sm:has-text("Aura Prime")');
  await expect(perksCard).toBeVisible();
  await expect(page.getByText('365 ngày sử dụng')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Gia hạn gói' })).toBeVisible();
});

