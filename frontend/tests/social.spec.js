import {test,expect} from '@playwright/test';
import fs from 'node:fs';
const userKey='aurameme-stitch-demo-user';
const login=async(page,username='Khang_dev')=>{
  await page.addInitScript(({username,userKey})=>{if(sessionStorage.getItem('social-test-initialized'))return;sessionStorage.setItem('social-test-initialized','1');if(username)localStorage.setItem(userKey,JSON.stringify({username,displayName:username==='Khang_dev'?'Khang Dev':username==='Kien_dev'?'Kien Dev':'Gigachad'}));else localStorage.removeItem(userKey);},{username,userKey});
};
const ready=async page=>{await page.waitForFunction(()=>document.getElementById('root')?.dataset.socialReady==='true')};
const react=async(page,id,type)=>{
  await page.locator(`#post-${id}`).getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
  await page.getByRole('dialog',{name:'Bộ chọn reaction'}).locator(`[data-reaction="${type}"]`).click();
};
test('reaction is persisted, replaces/toggles exactly once and is shared with Explore',async({page})=>{
  await login(page);await page.goto('/');await ready(page);
  await react(page,'khang','love');
  await expect(page.getByRole('dialog',{name:'Bộ chọn reaction'})).toHaveCount(0);
  await page.locator('#post-khang').getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
  await expect(page.locator('[data-reaction="love"]')).toHaveAttribute('aria-pressed','true');
  await page.locator('[data-reaction="fire"]').click();
  await page.reload();await ready(page);
  await page.locator('#post-khang').getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
  await expect(page.locator('[data-reaction="fire"]')).toHaveAttribute('aria-pressed','true');
  await expect(page.locator('[data-reaction="love"]')).toHaveAttribute('aria-pressed','false');
  await page.locator('[data-reaction="fire"]').click();
  await page.goto('/explore');await ready(page);
  await page.locator('#post-khang').getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
  await expect(page.locator('[data-reaction="fire"]')).toHaveAttribute('aria-pressed','false');
  expect(await page.locator('#post-khang [data-reaction-pill]').count()).toBeLessThanOrEqual(5);
});
test('guest can inspect reactions but cannot change demo state or use unowned memes',async({page})=>{
  await login(page,null);await page.goto('/');await ready(page);
  await react(page,'khang','love');
  await expect(page.getByRole('alert')).toContainText('Đăng nhập');
  await expect(page.locator('[data-reaction="love"]')).toHaveAttribute('aria-pressed','false');
  await expect(page.getByRole('dialog').getByText('Bảo Khố chưa hỗ trợ trong demo',{exact:true})).toBeVisible();
});
test('comment text is safe, ownership is enforced across account changes',async({page})=>{
 await login(page);await page.goto('/');await ready(page);
 const post=page.locator('#post-khang');
 const payload='<img src=x onerror=alert(1)> social comment';
 await post.getByRole('textbox',{name:'Nội dung bình luận'}).fill(payload);
 await post.getByRole('button',{name:'Gửi',exact:true}).click();
 const comment=post.locator('[data-comment-id]').filter({hasText:payload});
 await expect(comment).toBeVisible();await expect(comment.locator('img')).toHaveCount(1);
 await expect(comment.getByRole('button',{name:'Tùy chọn bình luận',exact:true})).toBeVisible();
 await page.evaluate(key=>localStorage.setItem(key,JSON.stringify({username:'Kien_dev',displayName:'Kien Dev'})),userKey);
 await page.reload();await ready(page);
 await expect(comment.getByRole('button',{name:'Tùy chọn bình luận',exact:true})).toHaveCount(0);
 await comment.getByRole('button',{name:'Thả biểu cảm bình luận',exact:true}).click();
 await page.locator('[data-reaction="love"]').click();
 await expect(comment.getByRole('button',{name:'Yêu',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.evaluate(key=>localStorage.setItem(key,JSON.stringify({username:'Khang_dev',displayName:'Khang Dev'})),userKey);
 await page.reload();await ready(page);
 await comment.getByRole('button',{name:'Tùy chọn bình luận',exact:true}).click();await comment.getByRole('menuitem',{name:'Xóa bình luận',exact:true}).click();await comment.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();await expect(comment).toHaveCount(0);
});
test('share only acknowledges clipboard success and shared hashes rescue hidden posts',async({page})=>{
 await page.addInitScript(()=>{navigator.share=undefined;Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>{window.__copied=value}}})});
 await page.goto('/');await ready(page);await page.locator('#post-khang').getByRole('button',{name:'Chia sẻ',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'Đã sao chép liên kết.'})).toBeVisible();
 expect(await page.evaluate(()=>window.__copied)).toBe('http://127.0.0.1:4186/#post-khang');
 await page.goto('/?category=Anime&q=hidden#post-khang');await ready(page);
 await expect(page.locator('#post-khang')).toBeVisible();await expect(page.locator('#post-khang')).toBeInViewport();
 await expect(page).toHaveURL('/#post-khang');
});
test('composer persists a real image and safe text, and new posts participate in all feed filters',async({page})=>{
 await login(page,'Kien_dev');await page.goto('/');await ready(page);
 const composer=page.getByRole('form',{name:'Tạo bài viết'}),text='social-created <script>alert(1)</script>';
 await composer.getByRole('textbox',{name:'Nội dung bài mới'}).fill(text);
 await composer.getByRole('combobox',{name:'Danh mục bài mới'}).selectOption('Gaming');
 await composer.locator('input[type=file]').setInputFiles({name:'local-image.png',mimeType:'image/png',buffer:fs.readFileSync(new URL('../public/assets/brand/favicon-64.png',import.meta.url))});
 await expect(composer.getByAltText('Ảnh xem trước')).toBeVisible();
 await composer.getByRole('button',{name:'Xem trước',exact:true}).click();
 await expect(composer.getByRole('region',{name:'Bản xem trước bài viết'})).toContainText(text);
 await composer.getByRole('button',{name:'Đăng bài',exact:true}).click();
 const post=page.locator('article[data-post-id]').filter({hasText:text});
 await expect(post).toBeVisible();await expect(post).toContainText('Kien Dev');
 const id=await post.getAttribute('data-post-id');expect(id).toMatch(/^p-/);
 await expect(post.getByAltText('Ảnh bài viết')).toBeVisible();
 await page.reload();await ready(page);await expect(post.getByAltText('Ảnh bài viết')).toBeVisible();
 expect(await post.getByAltText('Ảnh bài viết').evaluate(img=>img.naturalWidth)).toBe(64);
 await page.getByLabel('Lọc danh mục bài viết').selectOption('Anime');await expect(post).not.toBeVisible();
 await page.getByLabel('Lọc danh mục bài viết').selectOption('Gaming');
 const search=page.getByRole('searchbox',{name:'Tìm kiếm meme, tác giả, thẻ'});await search.fill('social-created');await search.press('Enter');
 await expect(post).toBeVisible();
 await page.goto('/explore');await ready(page);await expect(post).toBeVisible();
 await expect(page.locator('article[data-post-id]:visible')).toHaveCount(3);
 expect(await page.evaluate(()=>JSON.stringify(localStorage))).not.toContain('data:image');
});
test('storage failure never reports a post saved or clears the draft',async({page})=>{
 await login(page);await page.addInitScript(()=>{indexedDB.open=()=>{throw Error('denied')}});
 await page.goto('/');await ready(page);
 const composer=page.getByRole('form',{name:'Tạo bài viết'});
 await composer.getByRole('textbox',{name:'Nội dung bài mới'}).fill('draft must survive');
 await composer.getByRole('combobox',{name:'Danh mục bài mới'}).selectOption('Gaming');
 await composer.getByRole('button',{name:'Đăng bài',exact:true}).click();
 await expect(composer.getByRole('alert')).toContainText('Không lưu được');
 await expect(composer.getByRole('textbox',{name:'Nội dung bài mới'})).toHaveValue('draft must survive');
 await expect(composer.getByText('Đã đăng bài trong demo.',{exact:true})).toHaveCount(0);
});
test('GIF bytes restore after reload, invalid images are rejected and no Aura is changed',async({page})=>{
 await login(page,'Gigachad');await page.goto('/');await ready(page);
 const composer=page.getByRole('form',{name:'Tạo bài viết'});
 await composer.locator('input[type=file]').setInputFiles({name:'bad.png',mimeType:'image/png',buffer:Buffer.from('<svg onload=alert(1)>')});
 await expect(composer.getByRole('alert')).toContainText('Chỉ hỗ trợ');
 await composer.locator('input[type=file]').setInputFiles({name:'tiny.gif',mimeType:'image/gif',buffer:Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7','base64')});
 await expect(composer.getByAltText('Ảnh xem trước')).toBeVisible();
 await composer.getByRole('combobox',{name:'Danh mục bài mới'}).selectOption('Anime');
 await composer.getByRole('button',{name:'Đăng bài',exact:true}).click();
 const post=page.locator('article[data-post-id^="p-"]');await expect(post).toBeVisible();
 await expect(post).toContainText('Lvl 67');await expect(post).toContainText('GIF');
 await page.reload();await ready(page);await expect(post.getByAltText('Ảnh bài viết')).toBeVisible();
 expect(await post.getByAltText('Ảnh bài viết').evaluate(img=>img.naturalWidth)).toBe(1);
});
test('a committed post is acknowledged even when its background refresh fails',async({page})=>{
 await login(page);
 await page.addInitScript(()=>{const original=IDBDatabase.prototype.transaction;let count=0;IDBDatabase.prototype.transaction=function(...args){if(++count>2)throw Error('read failed after commit');return original.apply(this,args)}});
 await page.goto('/');await ready(page);
 const composer=page.getByRole('form',{name:'Tạo bài viết'});
 await composer.getByRole('textbox',{name:'Nội dung bài mới'}).fill('committed once');
 await composer.getByRole('combobox',{name:'Danh mục bài mới'}).selectOption('Random');
 await composer.getByRole('button',{name:'Đăng bài',exact:true}).click();
 await expect(page.locator('article[data-post-id^="p-"]')).toHaveCount(1);
 await page.reload();await ready(page);await expect(page.locator('article[data-post-id^="p-"]')).toHaveCount(1);
});
test('share cancellation and clipboard failure never show copied success',async({page})=>{
 await page.addInitScript(()=>{navigator.share=async()=>{throw new DOMException('cancel','AbortError')};Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw Error('denied')}}})});
 await page.goto('/');await ready(page);
 await page.locator('#post-khang').getByRole('button',{name:'Chia sẻ',exact:true}).click();
 await expect(page.getByText('Đã sao chép liên kết.',{exact:true})).toHaveCount(0);
 await page.evaluate(()=>{navigator.share=undefined});
 await page.locator('#post-khang').getByRole('button',{name:'Chia sẻ',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'Liên kết bài viết'})).toHaveValue('http://127.0.0.1:4186/#post-khang');
 await expect(page.getByText('Đã sao chép liên kết.',{exact:true})).toHaveCount(0);
});
test('all three accounts have independent selections and atomic rapid actions do not duplicate counts',async({page})=>{
 await login(page);await page.goto('/');await ready(page);
 for(const [username,type] of [['Khang_dev','like'],['Kien_dev','love'],['Gigachad','fire']]){
   await page.evaluate(({username,userKey})=>localStorage.setItem(userKey,JSON.stringify({username})),{username,userKey});
   await page.reload();await ready(page);await react(page,'khang',type);
 }
 for(const [username,type] of [['Khang_dev','like'],['Kien_dev','love'],['Gigachad','fire']]){
   await page.evaluate(({username,userKey})=>localStorage.setItem(userKey,JSON.stringify({username})),{username,userKey});
   await page.reload();await ready(page);
   await page.locator('#post-khang').getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
   await expect(page.locator(`[data-reaction="${type}"]`)).toHaveAttribute('aria-pressed','true');
   await page.keyboard.press('Escape');
 }
});
test('rapid double activation persists only one pending reaction',async({page})=>{
 await login(page);await page.goto('/');await ready(page);
 await page.locator('#post-khang').getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
 await page.locator('[data-reaction="love"]').evaluate(button=>{button.click();button.click()});
 await expect(page.getByRole('dialog',{name:'Bộ chọn reaction'})).toHaveCount(0);
 const state=await page.evaluate(()=>new Promise((resolve,reject)=>{const r=indexedDB.open('aurameme-social-demo-v1',1);r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result,read=db.transaction('state').objectStore('state').get('current');read.onsuccess=()=>{resolve(read.result);db.close()};read.onerror=()=>reject(read.error)}}));
 expect(state.revision).toBe(1);expect(state.postReactions.khang.Khang_dev).toBe('love');
});
test('media write failure rolls back both post metadata and bytes and keeps the draft',async({page})=>{
 await login(page);
 await page.addInitScript(()=>{const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='media')throw new DOMException('quota','QuotaExceededError');return put.apply(this,args)}});
 await page.goto('/');await ready(page);
 const composer=page.getByRole('form',{name:'Tạo bài viết'});
 await composer.getByRole('textbox',{name:'Nội dung bài mới'}).fill('atomic draft');
 await composer.getByRole('combobox',{name:'Danh mục bài mới'}).selectOption('Gaming');
 await composer.locator('input[type=file]').setInputFiles({name:'local.png',mimeType:'image/png',buffer:fs.readFileSync(new URL('../public/assets/brand/favicon-64.png',import.meta.url))});
 await expect(composer.getByAltText('Ảnh xem trước')).toBeVisible();
 await composer.getByRole('button',{name:'Đăng bài',exact:true}).click();
 await expect(composer.getByRole('alert')).toContainText('Không lưu được');
 await expect(composer.getByRole('textbox',{name:'Nội dung bài mới'})).toHaveValue('atomic draft');
 await expect(page.locator('article[data-post-id^="p-"]')).toHaveCount(0);
 await page.reload();await ready(page);await expect(page.locator('article[data-post-id^="p-"]')).toHaveCount(0);
});
