import { expect, test } from '@playwright/test';

test('auth failure never creates a session and settings fail closed', async ({ page }) => {
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED' } } }));
  await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'synthetic-test-token' } }));
  await page.route('**/api/v1/auth/login', route => route.fulfill({ status: 401, json: { error: { code: 'UNAUTHORIZED' } } }));
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: /Welcome Back/ })).toBeVisible();
  await page.getByLabel('Email', { exact: true }).fill('synthetic@example.com');
  await page.getByLabel('Password', { exact: true }).fill('Synthetic password!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('email or password');
  await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
});

test('network failure is visible and can retry without pretending anonymous', async ({ page }) => {
  await page.route('**/api/v1/users/me', route => route.abort());
  await page.goto('/settings');
  await expect(page.getByRole('alert')).toContainText('connection');
  await expect(page.getByRole('button', { name: 'Retry session' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Account settings' })).toHaveCount(0);
});

for (const [status, message] of [[403, 'not permitted'], [422, 'entered fields'], [429, 'Too many requests'], [500, 'connection']] as const) {
  test(`login ${status} is visible without success`, async ({ page }) => {
    await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
    await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'synthetic-test-token' } }));
    await page.route('**/api/v1/auth/login', route => route.fulfill({ status, json: { error: { code: 'SYNTHETIC_ERROR' } } }));
    await page.goto('/login');
    await page.getByLabel('Email', { exact: true }).fill('synthetic@example.com');
    await page.getByLabel('Password', { exact: true }).fill('Synthetic password!');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText(message);
    await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeEnabled();
    await expect(page).toHaveURL(/\/login$/);
  });
}

test('registration conflict does not claim an account was created', async ({ page }) => {
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
  await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'synthetic-test-token' } }));
  await page.route('**/api/v1/auth/register', route => route.fulfill({ status: 409, json: { error: { code: 'CONFLICT' } } }));
  await page.goto('/register');
  await page.getByLabel('Username', { exact: true }).fill('synthetic_owner');
  await page.getByLabel('Display name', { exact: true }).fill('Synthetic Owner');
  await page.getByLabel('Email', { exact: true }).fill('synthetic@example.com');
  await page.getByLabel('Password', { exact: true }).fill('Synthetic password!');
  await page.getByLabel('Confirm password').fill('Synthetic password!');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('conflicts');
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeEnabled();
  await expect(page.getByText('Account created. Sign in to continue.', { exact: true })).toHaveCount(0);
});
