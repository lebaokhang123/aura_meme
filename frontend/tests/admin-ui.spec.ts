import { expect, test } from '@playwright/test';

test('ordinary user cannot mount Admin data controls', async ({ page }) => {
  const requests: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/v1/admin/')) requests.push(request.url()); });
  await page.route('**/api/v1/users/me', route => route.fulfill({ json: { id: '11111111-1111-4111-8111-111111111111', username: 'synthetic', roles: ['USER'], status: 'active' } }));
  await page.route('**/api/v1/admin/**', route => route.fulfill({ json: { items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } } }));
  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Admin access required', exact: true })).toBeVisible();
  expect(requests).toEqual([]);
});

test('Guest Admin route requires a real session', async ({ page }) => {
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
  await page.goto('/admin');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: /Welcome Back/ })).toBeVisible();
});

for (const [status, message] of [[403, 'not permitted'], [429, 'Too many requests'], [500, 'connection']] as const) {
  test(`Contact ${status} never claims message received`, async ({ page }) => {
    await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
    await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'synthetic-test-token' } }));
    await page.route('**/api/v1/contact', route => route.fulfill({ status, json: { error: { code: 'SYNTHETIC_ERROR' } } }));
    await page.goto('/contact');
    await page.getByLabel('Your name').fill('Synthetic Visitor');
    await page.getByLabel('Email address').fill('synthetic@example.com');
    await page.getByLabel('Subject').selectOption('feedback');
    await page.getByLabel('Message', { exact: true }).fill('Synthetic message');
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await expect(page.getByRole('alert')).toContainText(message);
    await expect(page.getByText('Message received.', { exact: false })).toHaveCount(0);
    await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Synthetic message');
  });
}

test('Contact sends only allowed fields and shows the server receipt after 201', async ({ page }) => {
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
  await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'synthetic-test-token' } }));
  let payload: unknown;
  const id = '11111111-1111-4111-8111-111111111111';
  await page.route('**/api/v1/contact', route => { payload = route.request().postDataJSON(); return route.fulfill({ status: 201, json: { id, status: 'new' } }); });
  await page.goto('/contact');
  await page.getByLabel('Your name').fill('Synthetic Visitor');
  await page.getByLabel('Email address').fill('synthetic@example.com');
  await page.getByLabel('Subject').selectOption('feedback');
  await page.getByLabel('Message', { exact: true }).fill('Synthetic message');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Message received. Reference: ' + id);
  expect(payload).toEqual({ name: 'Synthetic Visitor', email: 'synthetic@example.com', subject: 'feedback', body: 'Synthetic message' });
  await expect(page.getByLabel('Message', { exact: true })).toHaveValue('');
});

test('Admin cannot reopen stale rows while a save is pending', async ({ page }) => {
  const actor = { id: '11111111-1111-4111-8111-111111111111', username: 'admin_fixture', roles: ['USER', 'ADMIN'], status: 'active' };
  let target = { id: '22222222-2222-4222-8222-222222222222', username: 'target', email: 'target@example.com', display_name: 'Original', roles: ['USER'], status: 'active' };
  let release!: () => void, started!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { started = resolve; });
  await page.route('**/api/v1/users/me', route => route.fulfill({ json: actor }));
  await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'synthetic-test-token' } }));
  await page.route('**/api/v1/admin/users?*', route => route.fulfill({ json: { items: [target], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } } }));
  await page.route('**/api/v1/admin/users/' + target.id, async route => { started(); await held; target = { ...target, display_name: 'Updated' }; await route.fulfill({ json: target }); });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Edit user target', exact: true }).click();
  await page.getByLabel('Account display name', { exact: true }).fill('Updated');
  const response = page.waitForResponse(value => value.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await requested;
  try {
    await expect(page.getByRole('button', { name: 'Edit user target', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Create user', exact: true })).toBeDisabled();
  } finally { release(); await response; }
  await expect(page.getByRole('button', { name: 'Edit user target', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: 'Edit user target', exact: true }).click();
  await expect(page.getByLabel('Account display name', { exact: true })).toHaveValue('Updated');
});

test('revoked Admin role is rechecked and removes the workspace', async ({ page }) => {
  let admin = true;
  await page.route('**/api/v1/users/me', route => route.fulfill({ json: { id: '11111111-1111-4111-8111-111111111111', username: 'synthetic', roles: admin ? ['USER', 'ADMIN'] : ['USER'], status: 'active' } }));
  await page.route('**/api/v1/admin/**', route => { admin = false; return route.fulfill({ status: 403, json: { error: { code: 'FORBIDDEN' } } }); });
  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Admin access required', exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Admin results', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Admin', exact: true })).toHaveCount(0);
});
