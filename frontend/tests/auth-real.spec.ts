import { expect, test } from '@playwright/test';

test('real register/login/profile/password/logout and revoked second session', async ({ page, browser }) => {
  const username = process.env.AURA_E2E_PREFIX;
  if (!username) throw new Error('Use backend/tests/run_browser.py with the isolated E2E database.');
  const email = username + '@example.com', password = 'Synthetic initial password!';
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/register');
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Display name', { exact: true }).fill('Synthetic Browser Owner');
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel('Confirm password').fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Account created. Sign in');
  await expect(page.getByRole('button', { name: 'Account created', exact: true })).toBeDisabled();
  await page.goto('/settings');
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill('Synthetic incorrect password!');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('email or password');
  const signIn = async (tab: typeof page, secret: string) => {
    await tab.goto('/login');
    await tab.getByLabel('Email', { exact: true }).fill(email);
    await tab.getByLabel('Password', { exact: true }).fill(secret);
    await tab.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(tab.getByRole('heading', { name: 'Account settings' })).toBeVisible();
  };
  await signIn(page, password);
  const second = await browser.newContext();
  const other = await second.newPage();
  try {
    await signIn(other, password);
    await page.getByLabel('Display name', { exact: true }).fill('Updated Browser Owner');
    await page.getByLabel('Bio', { exact: true }).fill('Synthetic biography');
    await page.getByLabel('Address (private)').fill('Synthetic private address');
    await page.getByRole('button', { name: 'Save profile', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Profile saved');
    await page.reload();
    await expect(page.getByLabel('Display name', { exact: true })).toHaveValue('Updated Browser Owner');
    await page.screenshot({ path: test.info().outputPath('settings-1440.png'), fullPage: true });
    await page.setViewportSize({ width: 375, height: 900 });
    await page.screenshot({ path: test.info().outputPath('settings-375.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
    for (const width of [375, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await page.screenshot({ path: test.info().outputPath('settings-polish-' + width + '.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 375, height: 900 });
    await page.getByLabel('Current password', { exact: true }).fill(password);
    await page.getByLabel('New password', { exact: true }).fill('Synthetic changed password!');
    await page.getByLabel('Confirm new password', { exact: true }).fill('Synthetic changed password!');
    await page.getByRole('button', { name: 'Change password', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Password changed');
    await other.reload();
    await expect(other).toHaveURL(/\/login$/);
    await page.getByRole('button', { name: 'Toggle navigation menu' }).click();
    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    await signIn(page, 'Synthetic changed password!');
    await page.goto('/profile/' + username);
    await expect(page).toHaveTitle('Profile — AuraMeme');
    await expect(page.getByRole('heading', { name: 'Updated Browser Owner' })).toBeVisible();
    await expect(page.getByText('Synthetic biography', { exact: true })).toBeVisible();
    await expect(page.getByText('Synthetic private address', { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  } finally { await second.close(); }
});
