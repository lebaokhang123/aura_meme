import {test,expect} from '@playwright/test';

for(const width of [375,768,1440])for(const theme of ['dark','light'])for(const language of ['vi','en']){
  test(`social controls at ${width}px ${theme}/${language} for Guest and three users`,async({page},testInfo)=>{
    test.setTimeout(60000);
    await page.setViewportSize({width,height:900});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    for(const username of [null,'Khang_dev','Kien_dev','Gigachad']){
      await page.goto('/');
      await page.evaluate(({username,theme,language})=>{
        localStorage.setItem('aurameme-ui-preferences',JSON.stringify({theme,language}));
        if(username)localStorage.setItem('aurameme-stitch-demo-user',JSON.stringify({username}));
        else localStorage.removeItem('aurameme-stitch-demo-user');
      },{username,theme,language});
      for(const route of ['/','/explore']){
        await page.goto(route);
        await page.waitForFunction(()=>document.getElementById('root')?.dataset.socialReady==='true');
        await page.evaluate(()=>document.fonts.ready);
        await expect(page.locator('article[data-post-id]:visible')).toHaveCount(3);
        expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
        const trigger=page.locator('#post-khang #btn-toggle-reaction-popover');
        await trigger.click();
        const picker=page.getByRole('dialog');await expect(picker).toBeVisible();
        await expect(picker.locator('[data-reaction]')).toHaveCount(6);
        const box=await picker.boundingBox();
        expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width);
        const headerBottom=await page.locator('.site-header').evaluate(el=>el.getBoundingClientRect().bottom);
        expect(box.y).toBeGreaterThanOrEqual(headerBottom);expect(box.y+box.height).toBeLessThanOrEqual(900);
        await picker.locator('[data-reaction="love"]').focus();await page.keyboard.press('Enter');
        if(username){await expect(picker).toHaveCount(0);}
        else{
          await expect(picker.getByRole('alert')).toBeVisible();
          await page.keyboard.press('Escape');
          await expect(trigger).toBeFocused();
        }
        if(username==='Gigachad'&&route==='/'){
          await trigger.click();await page.screenshot({path:testInfo.outputPath(`picker-${width}-${theme}-${language}.png`),fullPage:false});
          await page.keyboard.press('Escape');
        }
      }
    }
    expect(errors).toEqual([]);
  });
}

test('guest cannot send a comment and sees the login route',async({page})=>{
  await page.goto('/');await page.waitForFunction(()=>document.getElementById('root')?.dataset.socialReady==='true');
  const post=page.locator('#post-khang');
  await post.getByRole('textbox',{name:'Nội dung bình luận'}).fill('guest draft');
  await post.getByRole('button',{name:'Gửi',exact:true}).click();
  await expect(post.getByRole('alert').getByRole('link')).toHaveAttribute('href','/login');
  await expect(post.locator('[data-comment-id]')).toHaveCount(2);
});
