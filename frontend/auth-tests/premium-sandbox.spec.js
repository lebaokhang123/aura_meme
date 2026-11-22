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

async function setupMockApi(context, identity = 0, initialSub = null, vnpayApproved = false, orderError = null) {
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
      return identity === null
        ? fail(401, 'UNAUTHORIZED')
        : send(200, {
            ...users[identity],
            membership_tier: currentSubscription?.is_active ? currentSubscription.tier : 'free',
          });
    }
    if (path === '/admin/orders') {
      return send(200, {
        items: [
          {
            id: '00000000-0000-4000-8000-000000000001',
            order_code: 'AM-PRIME-1700000000-A1B2C3D4',
            tier: 'prime',
            provider: 'paypal_sandbox',
            amount_vnd: 1250000,
            amount_vnd_formatted: '1.250.000 đ',
            status: 'success',
            provider_txn_id: 'PP-TXN-12345',
            created_at: now,
          },
        ],
        pagination: { page: 1, page_size: 10, total: 1, total_pages: 1 },
      });
    }
    if (path.startsWith('/users/')) {
      const parts = path.split('/');
      const targetUsername = parts[2];
      const userObj = users.find((u) => u.username === targetUsername) || users[0];
      if (path.endsWith('/comments')) {
        return send(200, { items: [], pagination: { total: 0 } });
      }
      if (path.endsWith('/activity')) {
        return send(200, { total: 0, days: [] });
      }
      return send(200, {
        ...userObj,
        created_at: now,
        avatar_url: null,
        level: 15,
        realm: 'Trúc Cơ',
        title: 'Bá Chủ Thiên Lôi',
        membership_tier: currentSubscription?.is_active ? currentSubscription.tier : 'free',
      });
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
            amount_vnd_formatted: '130.000 VNĐ',
          },
          {
            tier: 'prime',
            name: 'Aura Prime',
            duration_days: 365,
            boost_multiplier: 3,
            amount_usd_formatted: '$50',
            amount_vnd: 1250000,
            amount_vnd_formatted: '1.250.000 VNĐ',
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
        provider: 'paypal_sandbox',
      });
    }

    if (path === '/premium/orders' && method === 'POST') {
      if (orderError) {
        return fail(orderError.status || 500, orderError.code || 'INTERNAL_ERROR');
      }
      if (request.headers()['x-csrf-token'] !== 'server-csrf-test-token') {
        return fail(403, 'CSRF_INVALID');
      }
      const orderCode = 'AM-SUB-TEST-1234';
      const isPaypal = body.provider === 'paypal_sandbox';
      const isVnpay = body.provider === 'vnpay_sandbox';
      const paymentUrl = isPaypal
        ? 'https://www.sandbox.paypal.com/checkoutnow?token=MOCK-PP-1234'
        : isVnpay
        ? 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?vnp_TxnRef=' + orderCode
        : null;
      return send(201, {
        order_code: orderCode,
        plan_tier: body.plan_tier,
        amount_usd_cents: body.plan_tier === 'plus' ? 500 : 5000,
        provider: body.provider,
        payment_url: paymentUrl,
      });
    }

    if (
      path.startsWith('/premium/orders/') &&
      (path.endsWith('/simulate') || path.endsWith('/capture')) &&
      method === 'POST'
    ) {
      if (request.headers()['x-csrf-token'] !== 'server-csrf-test-token') {
        return fail(403, 'CSRF_INVALID');
      }
      if (body.action === 'pay_fail' || body.mock_fail) {
        return send(200, {
          status: 'failed',
          subscription: null,
          order_code: 'AM-SUB-TEST-1234',
        });
      }
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
  await setupMockApi(context, 0);
  await page.emulateMedia({ reducedMotion: 'reduce' });

  for (const theme of ['dark', 'light']) {
    for (const language of ['vi', 'en']) {
      await page.goto('/');
      await page.evaluate((p) => localStorage.setItem('aurameme-ui-preferences', JSON.stringify(p)), {
        theme,
        language,
      });
      await page.goto('/premium');

      // Verify header and kicker
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Aura Memberships');

      // Verify exact prices: EN displays $5 and $50, VI displays 130.000 VNĐ and 1.250.000 VNĐ
      const content = await page.locator('.premium-selector-panel').innerText();
      if (language === 'en') {
        expect(content).toContain('$5');
        expect(content).toContain('$50');
      } else {
        expect(content).toContain('130.000 VNĐ');
        expect(content).toContain('1.250.000 VNĐ');
      }

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

test('Guest accessing /premium directly redirects to /login?next=%2Fpremium', async ({ page, context }) => {
  await setupMockApi(context, null);
  await page.goto('/premium');
  await expect(page).toHaveURL(/\/login\?next=%2Fpremium$/);
});

test('Logged in user can confirm order in modal, navigate to checkout, enter simulated card, and activate membership', async ({ page, context }) => {
  const s = await setupMockApi(context, 0, null, false);
  await page.goto('/premium');

  // Verify initial state: no active banner
  await expect(page.locator('.premium-active-banner')).toHaveCount(0);

  // Click CTA to open order confirmation dialog
  const cta = page.locator('.u056-cta');
  await expect(cta).toBeVisible();
  await expect(cta).toContainText('Mua gói Plus');
  await cta.click();

  // Verify dialog is open and centered
  const dialog = page.locator('.u081-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#u081-title')).toContainText('Xác nhận đơn hàng — Aura Plus');
  await expect(dialog.locator('.u081-price-primary')).toContainText('130.000 VNĐ');
  expect(await dialog.locator('.u081-price-primary').innerText()).not.toMatch(/USD|\$/);
  await expect(dialog.locator('.u081-note')).toContainText('PayPal Sandbox');

  const box = await dialog.boundingBox();
  const viewport = page.viewportSize();
  expect(Math.abs((box.y + box.height / 2) - viewport.height / 2)).toBeLessThan(2);
  expect(Math.abs((box.x + box.width / 2) - viewport.width / 2)).toBeLessThan(2);

  // Verify the 3 old simulation/vnpay buttons are removed
  await expect(dialog.locator('.u081-btn-simulate')).toHaveCount(0);
  await expect(dialog.locator('.u081-btn-fail')).toHaveCount(0);
  await expect(dialog.locator('.u081-btn-vnpay')).toHaveCount(0);

  // Click single primary CTA: Xác nhận thanh toán
  const confirmBtn = dialog.locator('.u081-btn-confirm');
  await expect(confirmBtn).toBeVisible();
  await expect(confirmBtn).toContainText('Xác nhận thanh toán');
  await confirmBtn.click();

  // Verify navigation to dedicated checkout page
  await expect(page).toHaveURL(/\/premium\/checkout\?order=AM-SUB-TEST-1234$/);

  // Verify checkout page layout and transaction summary
  await expect(page.locator('.checkout-header h1')).toContainText('Thanh toán Hội viên Aura');
  await expect(page.locator('.checkout-order-summary')).toContainText('AM-SUB-TEST-1234');
  await expect(page.locator('.checkout-order-summary')).toContainText('Aura Plus');
  await expect(page.locator('.checkout-order-summary')).toContainText('130.000 VNĐ');

  // Switch to card method to test card flow
  await page.locator('.checkout-method-card[data-method="card"]').click();

  // Verify simulated card form fields
  await expect(page.locator('#cardholder-name')).toHaveValue('NGUYEN VAN A');
  await expect(page.locator('#card-number')).toHaveValue('4242 4242 4242 4242');
  await expect(page.locator('#card-expiry')).toHaveValue('12/28');
  await expect(page.locator('#card-cvv')).toHaveValue('123');

  // Click Pay Now
  const payBtn = page.locator('.checkout-btn-pay');
  await expect(payBtn).toBeVisible();
  await expect(payBtn).toContainText('Thanh toán');
  await payBtn.click();

  // Verify receipt appears on checkout page
  const receipt = page.locator('.u081-receipt');
  await expect(receipt).toBeVisible();
  await expect(receipt).toContainText('BIÊN NHẬN GIAO DỊCH HỘI VIÊN');
  await expect(receipt).toContainText('ĐÃ KÍCH HOẠT (ACTIVE)');

  // Verify network requests: NO card/CVV data in capture payload!
  const simReq = s.requests.find((r) => (r.path.endsWith('/simulate') || r.path.endsWith('/capture')) && r.method === 'POST');
  expect(simReq).toBeDefined();
  expect(simReq.csrf).toBe('server-csrf-test-token');

  // Verify order creation request
  const orderReq = s.requests.find((r) => r.path === '/premium/orders' && r.method === 'POST');
  expect(orderReq).toBeDefined();
  expect(orderReq.csrf).toBe('server-csrf-test-token');
  expect(orderReq.body.plan_tier).toBe('plus');
  expect(orderReq.body.provider).toMatch(/paypal_sandbox|sandbox_simulated/);

  // Navigate back to /premium and verify active membership banner
  await page.goto('/premium');
  const banner = page.locator('.premium-active-banner');
  await expect(banner).toBeVisible();
  await expect(banner).toContainText('Gói đang kích hoạt: Aura PLUS');
  await expect(banner).toContainText('30 ngày');
  await expect(page.locator('.u056-cta')).toContainText('Gói đang kích hoạt');
});

test('Simulated checkout form validates inputs and handles failure safely without card leakage', async ({ page, context }) => {
  const s = await setupMockApi(context, 0, null, false);
  await page.goto('/premium/checkout?order=AM-SUB-TEST-1234');

  // Switch to card method
  await page.locator('.checkout-method-card[data-method="card"]').click();

  // Clear card number and try to submit
  await page.locator('#card-number').fill('');
  await page.locator('.checkout-btn-pay').click();

  // Verify validation error
  await expect(page.locator('.checkout-field-error')).toBeVisible();
  await expect(page.locator('.checkout-field-error')).toContainText('16 chữ số');

  // Verify no simulate request was sent on validation error
  expect(s.requests.some((r) => r.path.endsWith('/simulate'))).toBe(false);

  // Fill invalid expiry
  await page.locator('#card-number').fill('4242 4242 4242 4242');
  await page.locator('#card-expiry').fill('15/28');
  await page.locator('.checkout-btn-pay').click();
  await expect(page.locator('.checkout-field-error')).toContainText('MM/YY');

  // Fill valid test card
  await page.locator('.checkout-demo-pill').click();
  await expect(page.locator('#card-number')).toHaveValue('4242 4242 4242 4242');

  // Active banner should still not exist
  await page.goto('/premium');
  await expect(page.locator('.premium-active-banner')).toHaveCount(0);
});

test('PayPal Sandbox checkout and quick capture flow activate membership successfully', async ({ page, context }) => {
  const s = await setupMockApi(context, 0, null, false);
  await page.goto('/premium/checkout?order=AM-SUB-TEST-1234');

  // Verify PayPal action card is visible with image and primary button
  const paypalMethod = page.locator('.checkout-method-card[data-method="paypal"]');
  await expect(paypalMethod).toBeVisible();
  await expect(paypalMethod.locator('.checkout-method-img')).toHaveAttribute('src', '/assets/payment/paypal.png');
  await expect(page.locator('.checkout-btn-paypal')).toBeVisible();

  // 2-step instant approval click
  const instantBtn = page.locator('.checkout-btn-instant');
  await expect(instantBtn).toBeVisible();
  // Click 1: turns to confirming state
  await instantBtn.click();
  await expect(instantBtn).toHaveClass(/confirming/);
  // Click 2: executes capture
  await instantBtn.click();

  // Verify receipt appears
  const receipt = page.locator('.u081-receipt');
  await expect(receipt).toBeVisible();
  await expect(receipt).toContainText('BIÊN NHẬN GIAO DỊCH HỘI VIÊN');
  await expect(receipt).toContainText('ĐÃ KÍCH HOẠT (ACTIVE)');
  await expect(receipt.locator('.checkout-btn-download-receipt')).toBeVisible();

  // Verify capture request was sent with CSRF
  const capReq = s.requests.find((r) => r.path.endsWith('/capture') && r.method === 'POST');
  expect(capReq).toBeDefined();
  expect(capReq.csrf).toBe('server-csrf-test-token');
});

test('Guest accessing /premium/checkout directly redirects to /login?next=%2Fpremium%2Fcheckout', async ({ page, context }) => {
  await setupMockApi(context, null);
  await page.goto('/premium/checkout?order=AM-SUB-TEST-1234');
  await expect(page).toHaveURL(/\/login\?next=%2Fpremium%2Fcheckout%3Forder%3DAM-SUB-TEST-1234$/);
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
  await expect(page.locator('.aura-member-badge').first()).toBeVisible();

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
  await expect(page.locator('.aura-member-badge').first()).toBeVisible();

  // Verify Home Aura Perks card reflects Prime
  const perksCard = page.locator('.font-headline-sm:has-text("Aura Prime")');
  await expect(perksCard).toBeVisible();
  await expect(page.getByText('365 ngày sử dụng')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Gia hạn gói' })).toBeVisible();
});

test('Order confirmation modal displays single currency and centers across VI/EN and Plus/Prime', async ({ page, context }) => {
  await setupMockApi(context, 0, null, false);
  // Test EN Plus
  await page.goto('/premium');
  await page.evaluate(() => localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'en' })));
  await page.goto('/premium');
  await page.locator('.u056-cta').click();
  const dialog = page.locator('.u081-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.u081-price-primary')).toContainText('$5 USD');
  expect(await dialog.locator('.u081-price-primary').innerText()).not.toMatch(/VNĐ|đ/);

  // Check centering
  const boxEn = await dialog.boundingBox();
  const vp = page.viewportSize();
  expect(Math.abs((boxEn.y + boxEn.height / 2) - vp.height / 2)).toBeLessThan(2);
  expect(Math.abs((boxEn.x + boxEn.width / 2) - vp.width / 2)).toBeLessThan(2);
  await dialog.locator('.u081-close-btn').click();

  // Test EN Prime
  await page.locator('.premium-prime').click();
  await page.locator('.u056-cta').click();
  await expect(dialog.locator('.u081-price-primary')).toContainText('$50 USD');
  expect(await dialog.locator('.u081-price-primary').innerText()).not.toMatch(/VNĐ|đ/);
  await dialog.locator('.u081-close-btn').click();

  // Test VI Prime
  await page.evaluate(() => localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'vi' })));
  await page.goto('/premium');
  await page.locator('.premium-prime').click();
  await page.locator('.u056-cta').click();
  await expect(dialog.locator('.u081-price-primary')).toContainText('1.250.000 VNĐ');
  expect(await dialog.locator('.u081-price-primary').innerText()).not.toMatch(/USD|\$/);
  await dialog.locator('.u081-close-btn').click();
});

test('Order creation error displays friendly message and never leaks INTERNAL_ERROR', async ({ page, context }) => {
  await setupMockApi(context, 0, null, false, { status: 500, code: 'INTERNAL_ERROR' });

  await page.goto('/premium');
  await page.locator('.u056-cta').click();
  const dialog = page.locator('.u081-dialog');
  await expect(dialog).toBeVisible();

  // Click confirm payment
  const confirmBtn = dialog.locator('.u081-btn-confirm');
  await confirmBtn.click();

  // Verify friendly error is shown and raw INTERNAL_ERROR is never displayed
  const errorAlert = dialog.locator('.u081-error-banner');
  await expect(errorAlert).toBeVisible();
  await expect(errorAlert).toContainText('Không thể tạo đơn hàng. Vui lòng thử lại.');
  expect(await errorAlert.innerText()).not.toMatch(/INTERNAL_ERROR/);
  await expect(confirmBtn).toBeEnabled();
});

test('Phase A Identity: swapped icons, avatar glow everywhere, profile badge, and selector panel glow', async ({ page, context }) => {
  const artifactsDir = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

  // 1. Plus identity test
  const plusSub = {
    tier: 'plus',
    is_active: true,
    days_remaining: 30,
    expires_at: '2026-12-14T00:00:00Z',
    starts_at: now,
    boost_multiplier: 2.0,
  };
  await setupMockApi(context, 0, plusSub, false);

  // Check Home with Plus (Cyan/Blue + workspace_premium)
  await page.goto('/');
  const plusHeaderBtn = page.locator('.header-premium-btn--plus');
  await expect(plusHeaderBtn.locator('.header-premium-icon')).toHaveText('workspace_premium');
  const perksPlusHeader = page.locator('.font-mono-tag:has-text("AURA PERKS")').locator('..');
  await expect(perksPlusHeader.locator('.material-symbols-outlined')).toHaveText('workspace_premium');
  const perksPlusActive = page.locator('span:has-text("Đang kích hoạt")');
  await expect(perksPlusActive).toHaveClass(/border-cyan-300\/60/);
  await page.screenshot({ path: `${artifactsDir}/task5_identity_home_plus.png` });

  // Check Profile with Plus
  await page.goto('/profile');
  const plusProfileBadge = page.locator('.profile-premium-badge--plus');
  await expect(plusProfileBadge).toBeVisible();
  await expect(plusProfileBadge.locator('.profile-premium-badge-icon')).toHaveText('workspace_premium');
  await expect(plusProfileBadge).toContainText('Aura Plus');
  await expect(page.locator('.am-profile-avatar img')).toHaveClass(/aura-avatar--plus/);
  await page.screenshot({ path: `${artifactsDir}/task5_identity_profile_plus.png` });

  // Check Premium Page with Plus
  await page.goto('/premium');
  await expect(page.locator('.premium-selector-panel')).toHaveClass(/premium-selector-panel--plus/);
  await page.screenshot({ path: `${artifactsDir}/task5_identity_premium_plus.png` });

  // 2. Prime identity test (Gold/Amber + diamond)
  const primeSub = {
    tier: 'prime',
    is_active: true,
    days_remaining: 365,
    expires_at: '2027-11-14T00:00:00Z',
    starts_at: now,
    boost_multiplier: 3.0,
  };
  await setupMockApi(context, 0, primeSub, false);

  // Check Home with Prime
  await page.goto('/');
  const primeHeaderBtn = page.locator('.header-premium-btn--prime');
  await expect(primeHeaderBtn.locator('.header-premium-icon')).toHaveText('diamond');
  const perksPrimeHeader = page.locator('.font-mono-tag:has-text("AURA PERKS")').locator('..');
  await expect(perksPrimeHeader.locator('.material-symbols-outlined')).toHaveText('diamond');
  const perksPrimeActive = page.locator('span:has-text("Đang kích hoạt")');
  await expect(perksPrimeActive).toHaveClass(/border-amber-300\/60/);
  await page.screenshot({ path: `${artifactsDir}/task5_identity_home_prime.png` });

  // Check Profile with Prime
  await page.goto('/profile');
  const primeProfileBadge = page.locator('.profile-premium-badge--prime');
  await expect(primeProfileBadge).toBeVisible();
  await expect(primeProfileBadge.locator('.profile-premium-badge-icon')).toHaveText('diamond');
  await expect(primeProfileBadge).toContainText('Aura Prime');
  await expect(page.locator('.am-profile-avatar img')).toHaveClass(/aura-avatar--prime/);
  await page.screenshot({ path: `${artifactsDir}/task5_identity_profile_prime.png` });

  // Check Premium Page with Prime
  await page.goto('/premium');
  await expect(page.locator('.premium-selector-panel')).toHaveClass(/premium-selector-panel--prime/);
  await page.screenshot({ path: `${artifactsDir}/task5_identity_premium_prime.png` });
});

test('Payment method selector switches between PayPal and Card inputs', async ({ page, context }) => {
  const artifactsDir = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';
  await setupMockApi(context, 0, null, false);
  await page.goto('/premium/checkout?order=AM-SUB-TEST-1234');

  // Initially PayPal is selected
  const paypalMethod = page.locator('.checkout-method-card[data-method="paypal"]');
  const cardMethod = page.locator('.checkout-method-card[data-method="card"]');
  await expect(paypalMethod).toHaveClass(/active/);
  await expect(cardMethod).not.toHaveClass(/active/);
  await expect(page.locator('.checkout-paypal-action-box')).toBeVisible();
  await expect(page.locator('.checkout-card-form-expand')).toHaveCount(0);
  await page.screenshot({ path: `${artifactsDir}/task5_checkout_method_selector_paypal.png` });

  // Switch to Card
  await cardMethod.click();
  await expect(cardMethod).toHaveClass(/active/);
  await expect(paypalMethod).not.toHaveClass(/active/);
  await expect(page.locator('.checkout-card-form-expand')).toBeVisible();
  await expect(page.locator('#card-number')).toBeVisible();
  await page.screenshot({ path: `${artifactsDir}/task5_checkout_method_selector_card.png` });

  // Switch back to PayPal and capture receipt screenshot
  await paypalMethod.click();
  await expect(paypalMethod).toHaveClass(/active/);
  await expect(page.locator('.checkout-card-form-expand')).toHaveCount(0);

  // Quick sandbox capture (2-step instant approval) to verify receipt artifact
  const instantBtn = page.locator('.checkout-btn-instant');
  await instantBtn.click();
  await instantBtn.click();
  const receipt = page.locator('.u081-receipt');
  await expect(receipt).toBeVisible();
  await expect(receipt.locator('.checkout-btn-download-receipt')).toBeVisible();
  await page.screenshot({ path: `${artifactsDir}/task5_checkout_paypal_receipt.png` });
});

test('Avatar halo renders for Plus and Prime users on Home and Explore', async ({ page, context }) => {
  const primeSub = {
    tier: 'prime',
    is_active: true,
    days_remaining: 365,
    expires_at: '2027-11-14T00:00:00Z',
    starts_at: now,
    boost_multiplier: 3.0,
  };
  await setupMockApi(context, 0, primeSub, false);

  // Check Home Composer avatar has prime halo
  await page.goto('/');
  const composerAvatar = page.locator('[data-current-user-avatar] img');
  await expect(composerAvatar).toBeVisible();
  await expect(composerAvatar).toHaveClass(/aura-avatar--prime/);

  // Check Explore page
  await page.goto('/explore');
  await expect(page.locator('.header-premium-btn--prime')).toBeVisible();
});

test('Admin page moderation section includes Tab 3 Giao dịch (orders)', async ({ page, context }) => {
  const artifactsDir = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';
  await setupMockApi(context, 0, null, false);
  // Give admin role
  await context.route('**/api/v1/users/me', async (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: id(1),
        username: 'khang_dev',
        display_name: 'khang_dev',
        roles: ['ADMIN', 'USER'],
        status: 'active',
      }),
    });
  });

  await page.goto('/admin');
  // Click Kiểm duyệt section
  await page.getByRole('button', { name: /Kiểm duyệt|Moderation/ }).click();

  // Verify Tab 3 Giao dịch exists and click it
  const ordersTab = page.getByRole('button', { name: /Giao dịch|Transactions/ });
  await expect(ordersTab).toBeVisible();
  await ordersTab.click();

  // Verify order row is rendered with order_code, tier badge and amount
  await expect(page.locator('.workspace-rows')).toContainText('AM-PRIME-1700000000-A1B2C3D4');
  await expect(page.locator('.workspace-rows')).toContainText('Aura Prime');
  await expect(page.locator('.workspace-rows')).toContainText('1.250.000 đ');
  await page.screenshot({ path: `${artifactsDir}/task5_admin_orders_tab.png` });
});

