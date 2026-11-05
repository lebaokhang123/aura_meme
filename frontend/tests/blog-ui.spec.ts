import { expect, test } from '@playwright/test';

import { post, mockPublicBlog } from './blog-fixtures';

test('feed uses API query/sort and opens real detail routes without sample counts', async ({ page }) => {
  const queries: URL[] = [];
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
  await page.route('**/api/v1/categories?*', route => route.fulfill({ json: { items: [post.category], pagination: { page: 1, page_size: 100, total: 1, total_pages: 1 } } }));
  await page.route('**/api/v1/posts?*', route => {
    const url = new URL(route.request().url()); queries.push(url);
    return route.fulfill({ json: { items: url.searchParams.get('search') === 'missing' ? [] : [post], pagination: { page: 1, page_size: 20, total: url.searchParams.get('search') === 'missing' ? 0 : 1, total_pages: 1 } } });
  });
  await page.setViewportSize({ width: 375, height: 900 });
  await page.goto('/explore');
  await expect(page.getByRole('link', { name: 'Synthetic API post', exact: true })).toHaveAttribute('href', '/posts/' + post.id);
  await page.getByLabel('Sort posts').selectOption('title_asc');
  await expect.poll(() => queries.at(-1)?.searchParams.get('sort')).toBe('title_asc');
  await page.getByRole('searchbox', { name: 'Search posts', exact: true }).fill('missing');
  await page.getByRole('button', { name: 'Search feed', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No posts found.', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  await expect(page.getByText('Sample creator', { exact: true })).toHaveCount(0);
});


test('feed failure shows retry and never falls back to demo posts', async ({ page }) => {
  await page.route('**/api/v1/users/me', route => route.fulfill({ status: 401, json: {} }));
  await mockPublicBlog(page);
  let calls = 0;
  await page.route('**/api/v1/posts?*', route => {
    calls++;
    return calls === 1 ? route.fulfill({ status: 500, json: {} }) : route.fulfill({ json: { items: [post], pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 } } });
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('connection');
  await expect(page.getByRole('link', { name: 'Synthetic API post', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Retry feed', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Synthetic API post', exact: true })).toBeVisible();
});
