import { test, expect } from '@playwright/test';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

async function setupAuthMocks(context) {
  let lastForgotEmail = null;
  let lastResetPayload = null;
  let resetShouldFail = false;

  await context.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname.replace(/^\/api\/v1/, '');

    if (p === '/users/me') {
      return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: 'Guest' } } });
    }
    if (p === '/auth/csrf') {
      return route.fulfill({ json: { csrf_token: 'csrf-task7-test' } });
    }
    if (p === '/auth/google/config') {
      return route.fulfill({ json: { enabled: false, client_id: null } });
    }
    if (p === '/auth/forgot-password' && req.method() === 'POST') {
      expect(req.headers()['x-csrf-token']).toBe('csrf-task7-test');
      const body = req.postDataJSON();
      lastForgotEmail = body.email;
      return route.fulfill({
        json: {
          ok: true,
          message: 'Nếu địa chỉ email tồn tại và đủ điều kiện khôi phục, chúng tôi đã gửi liên kết đặt lại mật khẩu.',
        },
      });
    }
    if (p === '/auth/reset-password' && req.method() === 'POST') {
      expect(req.headers()['x-csrf-token']).toBe('csrf-task7-test');
      lastResetPayload = req.postDataJSON();
      if (resetShouldFail) {
        return route.fulfill({
          status: 400,
          json: { error: { code: 'INVALID_RESET_TOKEN', message: 'Invalid or expired reset token.' } },
        });
      }
      return route.fulfill({ json: { ok: true, message: 'Đặt lại mật khẩu thành công.' } });
    }
    return route.fulfill({ json: {} });
  });

  return {
    getLastForgotEmail: () => lastForgotEmail,
    getLastResetPayload: () => lastResetPayload,
    setResetShouldFail: (v) => { resetShouldFail = v; },
  };
}

test('Task 7: Login shows Continue with Google + Forgot Password link and handles unconfigured Google gracefully', async ({ page, context }) => {
  await setupAuthMocks(context);
  await page.setViewportSize({ width: 1280, height: 820 });
  await page.goto('/login');

  const forgotLink = page.locator('[data-forgot-password-link]');
  await expect(forgotLink).toBeVisible();
  await expect(forgotLink).toHaveText('Quên mật khẩu?');
  await expect(forgotLink).toHaveAttribute('href', '/forgot-password');

  const googleBtn = page.locator('[data-google-auth-button]');
  await expect(googleBtn).toBeVisible();
  await expect(googleBtn).toContainText('Tiếp tục với Google');

  await page.screenshot({ path: `${ARTIFACTS_DIR}/task7_login_google_forgot.png` });

  // Clicking Google when server has no credentials shows safe notice without crashing
  await googleBtn.click();
  await expect(page.locator('#aura-demo-toast')).toContainText('chưa được cấu hình');
});

test('Task 7: Forgot Password and Reset Password flows work securely with CSRF and strip token from URL', async ({ page, context }) => {
  const state = await setupAuthMocks(context);
  await page.setViewportSize({ width: 1280, height: 820 });

  // 1. Forgot password
  await page.goto('/forgot-password');
  await page.locator('#forgot-email').fill('alice@example.com');
  await page.getByRole('button', { name: 'Gửi liên kết' }).click();
  await expect(page.getByRole('status')).toContainText('Kiểm tra email của bạn');
  expect(state.getLastForgotEmail()).toBe('alice@example.com');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/task7_forgot_reset.png` });

  // 2. Reset password strips token from URL bar immediately and submits with CSRF
  await page.goto('/reset-password?token=secure-one-time-token-1234567890');
  await expect(page.locator('#reset-password')).toBeVisible();
  await expect(page).toHaveURL(/\/reset-password$/);

  await page.locator('#reset-password').fill('NewStrongPassword123!');
  await page.locator('#reset-confirm').fill('NewStrongPassword123!');
  await page.getByRole('button', { name: 'Cập nhật mật khẩu' }).click();
  await expect(page.getByRole('status')).toContainText('Đặt lại mật khẩu thành công');
  expect(state.getLastResetPayload()).toEqual({
    token: 'secure-one-time-token-1234567890',
    new_password: 'NewStrongPassword123!',
  });

  // 3. Invalid/used token displays clean error message
  state.setResetShouldFail(true);
  await page.goto('/reset-password?token=expired-token-12345678901234');
  await page.locator('#reset-password').fill('NewStrongPassword123!');
  await page.locator('#reset-confirm').fill('NewStrongPassword123!');
  await page.getByRole('button', { name: 'Cập nhật mật khẩu' }).click();
  await expect(page.getByRole('alert')).toContainText('không hợp lệ hoặc đã hết hạn');
});
