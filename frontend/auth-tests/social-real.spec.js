import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
test.skip(!process.env.AURA_SOCIAL_E2E,'Run via guarded run_social_browser.py on isolated test/E2E');
test.setTimeout(60000);
const password='Synthetic-browser-password!';
async function login(page,name='khang_dev'){
 await page.goto('/login');await page.locator('#identifier').fill(name+'@example.com');await page.locator('#password').fill(password);
 await page.locator('#loginForm button[type=submit]').click();await expect(page).toHaveURL(/\/$/);await expect(page.locator('.account-avatar')).toBeVisible();
}
for(const [name,display,admin] of [['khang_dev','Khang Dev',true],['kien_dev','Kien Dev',true],['gigachad','Gigachad',false]]){
 test('identity '+name+': real session reload and RBAC',async({page})=>{
  await login(page,name);await expect(page.locator('.account-avatar')).toHaveAttribute('alt','Ảnh đại diện '+display);
  await page.reload();await expect(page.locator('.account-avatar')).toHaveAttribute('alt','Ảnh đại diện '+display);
  expect((await page.request.get('/api/v1/admin/users')).status()).toBe(admin?200:403);
  await page.getByRole('button',{name:'Mở menu tài khoản'}).click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
  await expect(page.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);
 });
}
test('crud text, category/search/Hot, emoji comment, reaction, edit, delete and Guest reload',async({page})=>{
 await login(page);await page.getByLabel('Nội dung bài mới').fill('Social E2E Công nghệ 🔥');
 await page.getByLabel('Danh mục bài mới').selectOption('gaming');await page.getByRole('button',{name:'Đăng bài',exact:true}).click();
 const card=page.locator('[data-post-id]').filter({hasText:'Social E2E Công nghệ'});await expect(card).toHaveCount(1);
 const id=await card.getAttribute('data-post-id');
 for(const kind of ['like','love','laugh','fire','sad','angry']){
  await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();await page.locator('[data-reaction='+kind+']').click();
  await expect(card.locator('[data-reaction-pill='+kind+']')).toContainText('1');await expect(card.locator('[data-reaction-pill]')).toHaveCount(1);
 }
 await card.locator('[data-reaction-pill=angry]').click();await expect(card.locator('[data-reaction-pill]')).toHaveCount(0);
 await card.getByRole('button',{name:'Bình luận',exact:true}).click();
 await card.getByLabel('Nội dung bình luận').fill('Social E2E Comment 🔥');await card.getByRole('button',{name:/^Gửi/}).click();
 const row=card.locator('[data-comment-id]').filter({hasText:'Social E2E Comment'});await expect(row).toHaveCount(1);
 for(const kind of ['like','love','laugh','fire','sad','angry']){
  await row.getByRole('button',{name:'Thả biểu cảm bình luận'}).click();await page.locator('[data-reaction='+kind+']').click();
  await expect(row.locator('[data-reaction-pill='+kind+']')).toContainText('1');await expect(row.locator('[data-reaction-pill]')).toHaveCount(1);
 }
 await row.locator('[data-reaction-pill=angry]').click();await expect(row.locator('[data-reaction-pill]')).toHaveCount(0);
 await page.goto('/?q=cong+nghe&category=gaming&sort=hot');await expect(page.locator('[data-post-id]')).toHaveCount(1);
 await page.reload();await expect(page.locator('[data-post-id]')).toHaveCount(1);
 const edited=page.locator('[data-post-id="'+id+'"]');await edited.getByRole('button',{name:'Tùy chọn bài viết'}).click();await page.getByRole('menuitem',{name:'Sửa bài',exact:true}).click();
 await page.getByLabel('Nội dung sửa bài').fill('Social E2E Edited');
 const saved=page.waitForResponse(response=>response.request().method()==='PATCH'&&new URL(response.url()).pathname==='/api/v1/posts/'+id);
 await page.getByRole('button',{name:'Lưu thay đổi'}).click();expect((await saved).status()).toBe(200);
 await expect(page.getByRole('form',{name:'Sửa bài viết'})).toHaveCount(0);
 await page.goto('/#post-'+id);await expect(page.locator('[data-post-id="'+id+'"]')).toContainText('Social E2E Edited');
 await page.locator('[data-post-id="'+id+'"]').getByRole('button',{name:'Tùy chọn bài viết'}).click();await page.getByRole('menuitem',{name:'Xóa bài',exact:true}).click();await page.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();
 await expect(page.locator('[data-post-id="'+id+'"]')).toHaveCount(0);
});
test('media PNG GIF WebP upload stays visible at375 light/en after reload',async({page})=>{
 await login(page,'kien_dev');await page.setViewportSize({width:375,height:900});
 for(const [name,mime] of [['fixture.png','image/png'],['fixture.jpg','image/jpeg'],['fixture.gif','image/gif'],['fixture.webp','image/webp']]){
  const buffer=fs.readFileSync(path.join(process.env.AURA_SOCIAL_FIXTURES,name));
  await page.getByLabel('Nội dung bài mới').fill('Social E2E '+name);await page.getByLabel('Danh mục bài mới').selectOption('anime');
  await page.getByLabel('Ảnh hoặc GIF bài mới').setInputFiles({name,mimeType:mime,buffer});await page.getByRole('button',{name:'Đăng bài',exact:true}).click();
  await expect(page.locator('[data-post-id]').filter({hasText:'Social E2E '+name})).toHaveCount(1);
 }
 await page.reload();await expect(page.locator('[data-post-id]').filter({hasText:'Social E2E fixture.gif'}).locator('img[src^="/api/v1/media/"]')).toBeVisible();
 await page.locator('.u267-gb').click();await page.getByRole('option',{name:'English',exact:true}).click();
 await page.locator('.u219-tg').click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test('admin hides another author post; USER cannot edit or moderate it',async({page})=>{
 await login(page,'gigachad');await page.getByLabel('Nội dung bài mới').fill('Social E2E Giga ownership');await page.getByLabel('Danh mục bài mới').selectOption('random');await page.getByRole('button',{name:'Đăng bài',exact:true}).click();
 const card=page.locator('[data-post-id]').filter({hasText:'Social E2E Giga ownership'});await expect(card).toHaveCount(1);const id=await card.getAttribute('data-post-id');
 const denied=await page.evaluate(async id=>{
  const {csrf_token}=await (await fetch('/api/v1/auth/csrf')).json();
  return (await fetch('/api/v1/admin/posts/'+id,{method:'PATCH',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf_token},body:JSON.stringify({status:'hidden'})})).status;
 },id);expect(denied).toBe(403);
 await page.getByRole('button',{name:'Mở menu tài khoản'}).click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await expect(page.locator('.account-avatar')).toHaveCount(0);await login(page,'khang_dev');
 const other=page.locator('[data-post-id="'+id+'"]');await other.getByRole('button',{name:'Tùy chọn bài viết'}).click();await expect(page.getByRole('menuitem',{name:'Sửa bài',exact:true})).toHaveCount(0);
 await page.getByRole('menuitem',{name:'Ẩn bài (Admin)'}).click();
 const confirmation=page.getByRole('alertdialog',{name:'Xác nhận ẩn bài'});await expect(confirmation).toBeVisible();
 await confirmation.getByRole('button',{name:'Xác nhận ẩn',exact:true}).click();await expect(page.locator('[data-post-id="'+id+'"]')).toHaveCount(0);
 expect((await page.request.get('/api/v1/posts/'+id)).status()).toBe(404);
});

test('pagination loads the next server page, resolves direct post links and keeps Guest read-only',async({page})=>{
 await login(page);
 const ids=await page.evaluate(async()=>{
  const csrf=(await (await fetch('/api/v1/auth/csrf')).json()).csrf_token;
  const category=(await (await fetch('/api/v1/categories')).json()).items.find(v=>v.slug==='gaming').id;
  const ids=[];
  for(let i=0;i<21;i++){
   const response=await fetch('/api/v1/posts',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({content:'Social E2E pagination '+i,category_id:category,status:'published',request_id:crypto.randomUUID()})});
   if(response.status!==201)throw Error('Synthetic pagination fixture refused '+response.status);
   ids.push((await response.json()).id);
  }return ids;
 });
 await page.goto('/?q=pagination&category=gaming');await expect(page.locator('[data-post-id]')).toHaveCount(20);
 await page.getByRole('button',{name:'Xem thêm bài viết',exact:true}).click();await expect(page.locator('[data-post-id]')).toHaveCount(21);
 await page.goto('/#post-'+ids[0]);await expect(page.locator('[data-post-id="'+ids[0]+'"]')).toBeVisible();
 await page.getByRole('button',{name:'Mở menu tài khoản'}).click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
 await expect(page.locator('.account-avatar')).toHaveCount(0);
 const card=page.locator('[data-post-id]').first();await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();await page.locator('[data-reaction=fire]').click();
 await expect(page.getByRole('alert')).toContainText('Đăng nhập');
});
