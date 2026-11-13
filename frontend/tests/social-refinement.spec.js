import {test,expect} from '@playwright/test';
const ready=page=>page.waitForFunction(()=>document.getElementById('root')?.dataset.socialReady==='true');
const login=page=>page.addInitScript(()=>localStorage.setItem('aurameme-stitch-demo-user',JSON.stringify({username:'Khang_dev'})));
test('category counts use all active posts and update after owner deletion and reload',async({page})=>{
 await page.setViewportSize({width:1440,height:900});await login(page);await page.goto('/');await ready(page);
 const count=tag=>page.getByRole('navigation',{name:'Danh mục Home'}).locator(`[data-category="${tag}"] .font-mono-counter`);
 for(const [tag,n] of [['Gaming',1],['Anime',1],['CongNghe',1],['TruongHoc',0],['Random',0]])await expect(count(tag)).toHaveText(String(n));
 await page.goto('/?category=Anime');await ready(page);await expect(count('Gaming')).toHaveText('1');
 await page.goto('/');await ready(page);const post=page.locator('#post-khang');
 await post.getByRole('button',{name:'Tùy chọn bài viết'}).click();
 await expect(page.getByText('Lưu bài',{exact:true})).toHaveCount(0);
 await page.getByRole('menuitem',{name:'Xóa bài',exact:true}).click();await page.getByRole('button',{name:'Hủy',exact:true}).click();await expect(post).toBeVisible();
 await expect(page.getByRole('alertdialog',{name:'Xác nhận xóa bài'})).toHaveCount(0);
 await expect(post.getByRole('button',{name:'Tùy chọn bài viết'})).toBeFocused();
 await post.getByRole('button',{name:'Tùy chọn bài viết'}).click();
 await page.getByRole('menuitem',{name:'Xóa bài',exact:true}).click();await page.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();
 await expect(post).toHaveCount(0);await expect(count('Gaming')).toHaveText('0');
 await page.reload();await ready(page);await expect(post).toHaveCount(0);await expect(count('Gaming')).toHaveText('0');
 await page.locator('#post-kien').getByRole('button',{name:'Tùy chọn bài viết'}).click();await expect(page.getByRole('menuitem',{name:'Xóa bài',exact:true})).toHaveCount(0);
 await page.goto('/explore');await ready(page);await expect(post).toHaveCount(0);
});
test('comment composer inserts standard emoji at the caret and persists plain text',async({page})=>{
 await login(page);await page.goto('/');await ready(page);const post=page.locator('#post-khang'),input=post.getByRole('textbox',{name:'Nội dung bình luận'});
 await input.fill('Hôm nay cháy quá ');await input.evaluate(el=>el.setSelectionRange(el.value.length,el.value.length));
 await post.getByRole('button',{name:'Chèn emoji'}).click();await page.getByRole('dialog',{name:'Bộ chọn reaction'}).getByRole('button',{name:'Cháy',exact:true}).click();
 await expect(input).toHaveValue('Hôm nay cháy quá 🔥');await expect(input).toBeFocused();
 await post.getByRole('button',{name:'Gửi',exact:true}).click();await expect(post.locator('[data-comment-id]').filter({hasText:'Hôm nay cháy quá 🔥'})).toBeVisible();
 await page.reload();await ready(page);await expect(post.locator('[data-comment-id]').filter({hasText:'Hôm nay cháy quá 🔥'})).toBeVisible();
 await expect(post.locator('[data-reaction-pill]')).not.toContainText(['💀']);
});
test('language option badges say VI and EN instead of unsupported flag letters',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Chọn ngôn ngữ'}).click();
 await expect(page.locator('.u267-op em')).toHaveText(['VI','EN']);
 await page.getByRole('option',{name:'English',exact:true}).click();await expect(page.locator('.u267-cd')).toHaveText('EN');
});
for(const width of [375,768,1440])test(`Explore badges and reaction controls stay intact at ${width}px`,async({page},info)=>{
 await page.setViewportSize({width,height:900});await page.goto('/explore');await ready(page);await page.evaluate(()=>document.fonts.ready);
 const post=page.locator('#post-khang'),level=post.getByText('Lvl 79',{exact:true}),nickname=post.getByText('Bá chủ thiên lôi',{exact:true});
 const a=await level.boundingBox(),b=await nickname.boundingBox();
 for(const badge of [level,nickname])expect(await badge.evaluate(el=>{const s=getComputedStyle(el);return el.getBoundingClientRect().height<=parseFloat(s.lineHeight)+parseFloat(s.paddingTop)+parseFloat(s.paddingBottom)+parseFloat(s.borderTopWidth)+parseFloat(s.borderBottomWidth)+.1})).toBe(true);
 if(width===1440)expect(Math.abs((a.y+a.height/2)-(b.y+b.height/2))).toBeLessThan(1);
 const pills=post.locator('[data-reaction-pill]');const boxes=await pills.evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {y:r.y,right:r.right}}));
 expect(new Set(boxes.map(r=>r.y)).size).toBe(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
 await page.screenshot({path:info.outputPath(`explore-${width}.png`),fullPage:true});
});
