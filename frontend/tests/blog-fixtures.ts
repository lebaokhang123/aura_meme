import type { Page } from '@playwright/test';

export const post = { id: '11111111-1111-4111-8111-111111111111', title: 'Synthetic API post', content: 'Actual response fixture',
  status: 'published', media_url: null, created_at: '2026-11-06T00:00:00Z', updated_at: '2026-11-06T00:00:00Z',
  author: { id: '22222222-2222-4222-8222-222222222222', username: 'synthetic_owner', display_name: 'Synthetic Owner' },
  category: { id: '33333333-3333-4333-8333-333333333333', name: 'Synthetic Channel', slug: 'synthetic', status: 'active' } };


export async function mockPublicBlog(page: Page) {
  await page.route('**/api/v1/categories?*', route => route.fulfill({ json: { items: [post.category], pagination: { page: 1, page_size: 100, total: 1, total_pages: 1 } } }));
  await page.route('**/api/v1/posts?*', route => {
    const search = new URL(route.request().url()).searchParams.get('search')?.toLowerCase() ?? '';
    const items = (post.title + ' ' + post.content).toLowerCase().includes(search) ? [post] : [];
    return route.fulfill({ json: { items, pagination: { page: 1, page_size: 20, total: items.length, total_pages: items.length ? 1 : 0 } } });
  });
}
