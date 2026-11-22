import { test, expect } from '@playwright/test';

const ARTIFACTS_DIR = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

async function setupAuthMocks(context) {
  let forgotCalls = 0;
  let lastForgotEmail = null;
  let loginPayload = null;

  await context.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname.replace(/^\/api\/v1/, '');

    if (p === '/users/me') {
      return route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED', message: 'Guest' } } });
    }
    if (p === '/auth/csrf') {
      return route.fulfill({ json: { csrf_token: 'csrf-lucian-test' } });
    }
    if (p === '/auth/google/config') {
      return route.fulfill({ json: { enabled: false, client_id: null } });
    }
    if (p === '/auth/login' && req.method() === 'POST') {
      loginPayload = req.postDataJSON();
      if (loginPayload.password === 'WrongPassword!') {
        return route.fulfill({
          status: 401,
          json: { error: { code: 'INVALID_CREDENTIALS', message: 'Tên đăng nhập hoặc mật khẩu không chính xác.' } },
        });
      }
      await new Promise((r) => setTimeout(r, 120));
      return route.fulfill({
        json: {
          user: { id: '00000000-0000-0000-0000-000000000001', username: 'khang_dev', display_name: 'Khang Dev' },
        },
      });
    }
    if (p === '/auth/forgot-password' && req.method() === 'POST') {
      forgotCalls++;
      lastForgotEmail = req.postDataJSON().email;
      return route.fulfill({
        json: { ok: true, message: 'Nếu địa chỉ email tồn tại và đủ điều kiện khôi phục, chúng tôi đã gửi liên kết.' },
      });
    }
    return route.fulfill({ json: {} });
  });

  return {
    getForgotCalls: () => forgotCalls,
    getLastForgotEmail: () => lastForgotEmail,
    getLoginPayload: () => loginPayload,
  };
}

test('Lucian #409: Cookie Consent compact banner, bite & crumbs, thanks pill, essential tuck, and reopen', async ({ page, context }) => {
  await setupAuthMocks(context);
  await context.addInitScript(() => {
    localStorage.removeItem('aurameme-cookie-consent-v1');
    localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'vi' }));
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/login');

  // 1. Initial compact state with golden cookie perched on top
  const banner = page.locator('[data-cookie-banner]');
  await expect(banner).toBeVisible();
  await expect(page.locator('.u409-ck svg')).toBeVisible();
  await expect(page.locator('.u409-t')).toContainText('Cho phép AuraMeme dùng Cookie?');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_cookie_initial_dark.png` });

  // 2. Click 'Đã hiểu' -> triggers bite animation + crumb drop + thanks pill
  await page.locator('[data-cookie-ok]').click();
  await expect(page.locator('.u409')).toHaveClass(/is-bite/);
  // Wait for pill transformation
  await expect(page.locator('.u409-pill')).toBeVisible({ timeout: 2000 });
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_cookie_bite_thanks.png` });

  // Wait for fly-away and check reopen button appears
  await expect(page.locator('[data-cookie-banner]')).toHaveCount(0, { timeout: 6000 });
  const reopenBtn = page.locator('[data-cookie-reopen]');
  await expect(reopenBtn).toBeVisible();
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_cookie_reopen_button.png` });

  // Reopen and test Essential only tuck
  await reopenBtn.click();
  await expect(page.locator('[data-cookie-banner]')).toBeVisible();
  await page.locator('[data-cookie-ess]').click();
  await expect(page.locator('.u409')).toHaveClass(/is-tiny/);
  await expect(page.locator('[data-cookie-banner]')).toHaveCount(0, { timeout: 5000 });
  await expect(page.locator('[data-cookie-reopen]')).toBeVisible();

  // Test Mobile 375px
  await page.setViewportSize({ width: 375, height: 812 });
  await reopenBtn.click();
  await expect(page.locator('[data-cookie-banner]')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_cookie_mobile_375.png` });
});

test('Lucian #403: Email Sign-In Form floating labels, eye toggle animation, error shake/red line, submit spinner and checkmark', async ({ page, context }) => {
  const mocks = await setupAuthMocks(context);
  await context.addInitScript(() => {
    localStorage.setItem('aurameme-cookie-consent-v1', JSON.stringify({ version: 1, essential: true, optional: false, updatedAt: new Date().toISOString() }));
    localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'vi' }));
  });

  await page.setViewportSize({ width: 1280, height: 850 });
  await page.goto('/login');

  const idField = page.locator('#identifier');
  const pwField = page.locator('#password');
  const submitBtn = page.locator('#submitBtn');
  const eyeBtn = page.locator('.u403-eye');

  // 1. Initial idle state
  await expect(idField).toBeVisible();
  await expect(pwField).toBeVisible();
  await expect(submitBtn).toBeVisible();
  await expect(page.locator('.u403-f').first()).not.toHaveClass(/is-up/);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_login_idle_dark.png` });

  // 2. Focus identifier -> floating label moves up
  await idField.focus();
  await expect(page.locator('.u403-f').first()).toHaveClass(/is-f/);
  await expect(page.locator('.u403-f').first()).toHaveClass(/is-up/);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_login_focus_floating_label.png` });

  // 3. Eye toggle: password reveal with animated eyelid
  await pwField.fill('MySecretPassword123');
  await expect(pwField).toHaveAttribute('type', 'password');
  await eyeBtn.click();
  await expect(pwField).toHaveAttribute('type', 'text');
  await expect(eyeBtn).toHaveAttribute('aria-pressed', 'true');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_login_eye_open.png` });

  await eyeBtn.click();
  await expect(pwField).toHaveAttribute('type', 'password');
  await expect(eyeBtn).toHaveAttribute('aria-pressed', 'false');

  // 4. Test wrong password -> shake animation, red underline, error message
  await idField.fill('khang_dev');
  await pwField.fill('WrongPassword!');
  await submitBtn.click();

  const pwContainer = page.locator('.u403-f.u403-pw');
  await expect(pwContainer).toHaveClass(/is-err/);
  await expect(page.locator('.u403-msg')).toHaveClass(/is-on/);
  await expect(page.locator('.u403-msg')).toContainText('không đúng');
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_login_error_shake.png` });

  // Typing in password clears error
  await pwField.press('Backspace');
  await expect(pwContainer).not.toHaveClass(/is-err/);
  await expect(page.locator('.u403-msg')).not.toHaveClass(/is-on/);

  // 5. Test valid login -> submit button shrinks into 48px circle with spinner, then checkmark
  await pwField.fill('CorrectPassword123!');
  await submitBtn.click();
  // While processing, submit button has is-busy or is-ok
  await expect(submitBtn).toHaveClass(/is-busy|is-ok/);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_login_success_action.png` });

  // 6. Test Light mode
  await page.evaluate(() => {
    localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'light', language: 'vi' }));
    document.querySelector('.u219')?.setAttribute('data-theme', 'light');
  });
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_login_light.png` });
});

test('Lucian #405: Password Reset with paper plane flight, letter entering envelope, and resend countdown ring', async ({ page, context }) => {
  const mocks = await setupAuthMocks(context);
  await context.addInitScript(() => {
    localStorage.setItem('aurameme-cookie-consent-v1', JSON.stringify({ version: 1, essential: true, optional: false, updatedAt: new Date().toISOString() }));
    localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'vi' }));
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/forgot-password');

  const emailInp = page.locator('#forgot-email');
  const sendBtn = page.locator('.u405-send');

  // 1. Initial State A: email field with floating label
  await expect(page.locator('.u405-title')).toHaveText('Quên mật khẩu?');
  await expect(emailInp).toBeVisible();
  await emailInp.focus();
  await expect(page.locator('.u405-f')).toHaveClass(/is-f/);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_forgot_initial_dark.png` });

  // 2. Submit valid email -> paper plane launches, transitions to State B
  await emailInp.fill('sammy@example.com');
  await sendBtn.click();

  // State B becomes active with letter sliding into envelope
  await expect(page.locator('.u405')).toHaveClass(/is-sent/);
  await expect(page.locator('.u405-b b')).toHaveText('Kiểm tra email của bạn');
  await expect(page.locator('.u405-em')).toHaveText('sammy@example.com');
  await expect(page.locator('.u405-re')).toBeDisabled(); // countdown active
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_forgot_envelope_sent.png` });

  // 3. Test 'Đổi' (Change email) button -> returns to State A with input focused
  await page.locator('.u405-chg').click();
  await expect(page.locator('.u405')).not.toHaveClass(/is-sent/);
  await expect(emailInp).toBeFocused();
  await page.screenshot({ path: `${ARTIFACTS_DIR}/lucian_forgot_change_email.png` });
});
