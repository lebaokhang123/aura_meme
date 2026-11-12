import {test,expect} from '@playwright/test';
const ready=page=>page.waitForFunction(()=>document.getElementById('root')?.dataset.socialReady==='true');
const login=page=>page.addInitScript(()=>localStorage.setItem('aurameme-stitch-demo-user',JSON.stringify({username:'Khang_dev'})));
test('old deleted Khang samples are restored once without restoring another author or resetting data',async({page})=>{
 await login(page);await page.goto('/');await ready(page);
 await page.evaluate(()=>new Promise((resolve,reject)=>{const r=indexedDB.open('aurameme-social-demo-v1',1);r.onsuccess=()=>{const db=r.result,tx=db.transaction('state','readwrite'),store=tx.objectStore('state'),read=store.get('current');read.onsuccess=()=>{const state=read.result;state.deletedComments=['sample-kien-1','sample-khang-demo-2','sample-khang-0'];delete state.khangCommentRepairV1;state.revision++;store.put(state,'current')};tx.oncomplete=()=>{db.close();resolve()};tx.onabort=()=>reject(tx.error)}}));
 await page.reload();await ready(page);
 await expect(page.locator('[data-comment-id="sample-khang-0"]')).toHaveCount(0);
 await expect(page.locator('[data-comment-id="sample-khang-demo-2"]')).toBeVisible();
 const post=page.locator('#post-kien');await post.getByRole('button',{name:'Bình luận',exact:true}).click();
 const row=post.locator('[data-comment-id="sample-kien-1"]');await expect(row).toBeVisible();
 await row.getByRole('button',{name:'Tùy chọn bình luận'}).click();await row.getByRole('menuitem',{name:'Xóa bình luận'}).click();await row.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();
 // UI updates only after IndexedDB commits; do not reload while deletion is pending.
 await expect(row).toHaveCount(0);
 await page.reload();await ready(page);await expect(row).toHaveCount(0);
});
test('comment deletion is behind a right-aligned menu and explicit confirmation',async({page})=>{
 await login(page);await page.goto('/');await ready(page);
 const post=page.locator('#post-khang'),input=post.getByRole('textbox',{name:'Nội dung bình luận'});
 await input.fill('comment menu guard');await post.getByRole('button',{name:'Gửi',exact:true}).click();
 const row=post.locator('[data-comment-id]').filter({hasText:'comment menu guard'}),menu=row.getByRole('button',{name:'Tùy chọn bình luận'});
 await expect(row.getByText('Xóa bình luận',{exact:true})).toHaveCount(0);
 await menu.click();await row.getByRole('menuitem',{name:'Xóa bình luận'}).click();await row.getByRole('button',{name:'Hủy',exact:true}).click();await expect(row).toBeVisible();
 await menu.click();await row.getByRole('menuitem',{name:'Xóa bình luận'}).click();await row.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();await expect(row).toHaveCount(0);
 await page.reload();await ready(page);await expect(row).toHaveCount(0);
});
test('comment composer uses the full Stitch picker without casting a reaction',async({page})=>{
 await login(page);await page.goto('/');await ready(page);const post=page.locator('#post-khang');
 await post.getByRole('textbox',{name:'Nội dung bình luận'}).fill('Cháy ');
 await post.getByRole('button',{name:'Chèn emoji'}).click();const picker=page.getByRole('dialog',{name:'Bộ chọn reaction'});
 await expect(picker.getByText('1. Biểu cảm tiêu chuẩn (Miễn phí)',{exact:true})).toBeVisible();
 await expect(picker.getByText('2. Meme của tôi',{exact:true})).toBeVisible();
 await expect(picker.locator('.reaction-item:has(img):enabled')).toHaveCount(0);
 await picker.locator('[data-reaction="fire"]').click();await expect(post.getByRole('textbox',{name:'Nội dung bình luận'})).toHaveValue('Cháy 🔥');
 await expect(post.locator('.social-post-reactions [data-reaction-pill="fire"]')).toHaveCount(0);
});
test('Hall of Fame shows real display name, handle, level and nickname instead of drops',async({page})=>{
 await page.setViewportSize({width:1440,height:900});await page.goto('/explore');await ready(page);
 const identities=page.locator('.hall-identity');await expect(identities).toHaveCount(3);
 const first=identities.first();for(const text of ['Khang Dev','@Khang_dev','Lvl 79','Bá chủ thiên lôi'])await expect(first.getByText(text,{exact:true})).toBeVisible();
 const centers=await first.locator(':scope > span').evaluateAll(nodes=>nodes.map(el=>{const r=el.getBoundingClientRect();return r.y+r.height/2}));
 expect(Math.max(...centers)-Math.min(...centers)).toBeLessThan(1);
 await expect(page.getByText(/\d+ drops/)).toHaveCount(0);
});
for(const width of [375,768,1440])for(const route of ['/','/explore'])test(`six reaction types keep +1 before picker on one action row ${route} ${width}`,async({page})=>{
 await page.setViewportSize({width,height:900});await login(page);await page.goto(route);await ready(page);const post=page.locator('#post-kien');
 await post.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();await page.locator('[data-reaction="love"]').click();
 await expect(post.locator('.social-post-reactions [data-reaction-pill]')).toHaveCount(5);
 const more=post.getByRole('button',{name:'Xem tất cả reaction'}),trigger=post.getByRole('button',{name:'Thả biểu cảm',exact:true});
 await expect(more).toHaveText('+1');
 const [a,b]=await post.evaluate(el=>['Xem tất cả reaction','Thả biểu cảm'].map(label=>{const r=el.querySelector(`button[aria-label="${label}"]`).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}));
 expect(a.x+a.width).toBeLessThanOrEqual(b.x);expect(Math.abs(a.y+a.height/2-b.y-b.height/2)).toBeLessThan(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
});
