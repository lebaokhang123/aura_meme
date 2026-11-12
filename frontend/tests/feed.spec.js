import { test, expect } from '@playwright/test';

const visiblePosts = page => page.locator('article[data-post-id]:visible');
const ids = page => visiblePosts(page).evaluateAll(nodes => nodes.map(n => n.dataset.postId));
for (const role of ['guest', 'user']) for (const width of [375, 768, 1440]) for (const route of ['/', '/explore']) {
  test(`${role} ${route} ${width}: combined filters, empty, reload and history`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.addInitScript(user => { if (user) localStorage.setItem('aurameme-stitch-demo-user', JSON.stringify({ displayName:'Khang Dev',username:'Khang_dev' })); }, role === 'user');
    const errors=[]; page.on('pageerror', e=>errors.push(e.message));
    await page.goto(route);
    await expect(visiblePosts(page)).toHaveCount(3);
    expect(await ids(page)).toEqual(['khang','kien','gigachad']);
    if (route === '/') {
      await expect(page.locator('[data-sort="new"]')).toHaveAttribute('aria-pressed','true');
      await expect(page.getByRole('button',{name:/^Top/})).toHaveCount(0);
      await page.locator('[data-sort="hot"]').click();
      expect(await ids(page)).toEqual(['gigachad','kien','khang']);
      await page.getByLabel('Lọc danh mục bài viết').selectOption('Gaming');
    } else await page.locator('[data-category="Gaming"]').click();
    await expect(visiblePosts(page)).toHaveCount(1);
    expect(await ids(page)).toEqual(['khang']);
    if (width === 375) await page.getByRole('button',{name:'Mở menu điều hướng',exact:true}).click();
    const search=page.getByRole('searchbox',{name:'Tìm kiếm meme, tác giả, thẻ'});
    await search.fill('production'); await search.press('Enter');
    await expect(page).toHaveURL(/q=production/);
    expect(await ids(page)).toEqual(['khang']);
    await page.reload(); await expect(visiblePosts(page)).toHaveCount(1);
    if (route === '/') await page.getByLabel('Lọc danh mục bài viết').selectOption('Anime');
    else await page.locator('[data-category="Anime"]').click();
    await expect(visiblePosts(page)).toHaveCount(0);
    await expect(page.getByRole('status').filter({hasText:'Không tìm thấy'})).toBeVisible();
    await page.goBack(); await expect(visiblePosts(page)).toHaveCount(1);
    await page.goForward(); await expect(visiblePosts(page)).toHaveCount(0);
    await page.getByRole('button',{name:'Xóa bộ lọc',exact:true}).click();
    await expect(visiblePosts(page)).toHaveCount(3);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}
test('Explore opens the corresponding Home post, preserving search/category/sort', async ({ page }) => {
  for (const [category, query, id, name] of [['Gaming','production','khang','Khang Dev'],['CongNghe','cuoc doi','kien','Kien Dev'],['Anime','nhan vat','gigachad','Gigachad']]) {
    await page.goto(`/explore?category=${category}&q=${encodeURIComponent(query)}&sort=hot`);
    await page.getByRole('link',{name:`Xem bài của ${name} trên Trang chủ`}).click();
    const url=new URL(page.url());
    expect(url.pathname).toBe('/'); expect(url.searchParams.get('category')).toBe(category); expect(url.searchParams.get('q')).toBe(query); expect(url.searchParams.get('sort')).toBe('hot'); expect(url.hash).toBe(`#post-${id}`);
    await expect(page.locator(`#post-${id}`)).toBeInViewport();
    expect(await ids(page)).toEqual([id]);
    await page.goBack(); await expect(page).toHaveURL(/\/explore\?/);
    await expect(visiblePosts(page)).toHaveCount(1);
  }
});
test('header navigation carries combined filters between Home and Explore', async ({ page }) => {
  await page.setViewportSize({width:1440,height:900});
  await page.goto('/?category=Gaming&q=production&sort=hot');
  await page.locator('.site-nav').getByRole('link',{name:'Khám phá',exact:true}).click();
  await expect(page).toHaveURL('/explore?category=Gaming&q=production&sort=hot');
  expect(await ids(page)).toEqual(['khang']);
  await page.locator('.site-nav').getByRole('link',{name:'Trang chủ',exact:true}).click();
  await expect(page).toHaveURL('/?category=Gaming&q=production&sort=hot');
  await expect(page.locator('[data-sort="hot"]')).toHaveAttribute('aria-pressed','true');
});
test('original native reaction popup still opens after filtering its post out and back', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Lọc danh mục bài viết').selectOption('Anime');
  await page.getByLabel('Lọc danh mục bài viết').selectOption('');
  await page.locator('#btn-toggle-reaction-popover').click();
  await expect(page.locator('#reaction-popover')).toBeVisible();
});
