import {test,expect} from '@playwright/test';
import path from 'node:path';

// Only an operator-prepared isolated backend may run this test; no HTTP fixtures or DB setup.
const prefix=process.env.AURA_LEVEL_E2E_PREFIX;
test.skip(!prefix,'Set a unique AURA_LEVEL_E2E_PREFIX after the guarded Aura backend is ready.');
test.setTimeout(180000);
const password='Synthetic-browser-password!';
async function register(page,name){
 await page.goto('/register');await page.locator('#username').fill(name);await page.locator('#identifier').fill(name+'@example.com');
 await page.locator('#password').fill(password);await page.locator('#confirmPassword').fill(password);await page.locator('#terms').check();
 await page.locator('#loginForm button[type=submit]').click();await expect(page).toHaveURL(/\/login\?registered=1$/);
}
async function login(page,name){
 await page.goto('/login');await page.locator('#identifier').fill(name+'@example.com');await page.locator('#password').fill(password);
 await page.locator('#loginForm button[type=submit]').click();await expect(page).toHaveURL(/\/$/);await expect(page.locator('.account-avatar')).toBeVisible();
}
async function progress(page){
 const response=await page.request.get('/api/v1/aura/progress');expect(response.status()).toBe(200);return response.json();
}
async function checkedCard(page,language='vi'){
 const card=page.locator('[data-aura]');await expect(card).toBeVisible();await expect(card.locator('.am-profile-progress-caption>span').first()).toHaveText('15 Exp');
 await expect(card).toContainText('LVL 2');await expect(card).toContainText('Luyện Khí');await expect(card).toContainText(language==='en'?'Streak: 1':'Chuỗi: 1');
 await expect(card.getByRole('button',{name:language==='en'?'Checked in':'Đã điểm danh',exact:true})).toBeDisabled();return card;
}

test('real Aura check-in, private progress, persistence and responsive preferences',async({page,browser},testInfo)=>{
 expect(prefix).toMatch(/^[a-z0-9_]{3,26}$/);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:1440,height:960});
 await register(page,prefix);await login(page,prefix);
 const before=await progress(page);expect(before).toMatchObject({earned_xp:0,bonus_xp:0,total_xp:0,level:1,fair_level:1,level_xp:0,next_level_xp:11,xp_to_next:11,streak_days:0,checked_in:false});
 const home=page.locator('[data-aura]');await expect(home).toBeVisible();await expect(home.locator('.am-profile-progress-caption>span').first()).toHaveText('0 Exp');await expect(home).toContainText('LVL 1');
 await expect(page.getByText('TOP AURA CREATORS')).toHaveCount(0);
 const claim=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname==='/api/v1/aura/check-in');
 const button=home.getByRole('button',{name:'Điểm danh',exact:true});await button.focus();await expect(button).toBeFocused();await page.keyboard.press('Enter');
 const receipt=await claim;expect(receipt.status()).toBe(200);expect(await receipt.json()).toMatchObject({already_checked_in:false,earned_xp_delta:15,bonus_xp_delta:0,khi_van_delta:0,streak_days:1});
 await checkedCard(page);expect(await progress(page)).toMatchObject({earned_xp:15,bonus_xp:0,total_xp:15,level:2,fair_level:2,level_xp:4,next_level_xp:12,xp_to_next:8,streak_days:1,checked_in:true});
 await page.reload();await checkedCard(page);await page.goto('/profile');await checkedCard(page);await page.reload();await checkedCard(page);
 // A second UI registration supplies a real public profile without seeding or touching another account.
 const other=prefix+'_other',otherContext=await browser.newContext({baseURL:new URL(page.url()).origin,reducedMotion:'reduce'});
 try{await register(await otherContext.newPage(),other)}finally{await otherContext.close()}
 const privateReads=[];const readListener=request=>{if(new URL(request.url()).pathname==='/api/v1/aura/progress')privateReads.push(request.url())};page.on('request',readListener);
 await page.goto('/profile/'+other);await expect(page.locator('.am-profile-name h1')).toBeVisible();await expect(page.locator('[data-aura]')).toContainText('Chưa có dữ liệu');
 await expect(page.locator('[data-aura]')).not.toContainText('15 Exp');await expect(page.locator('[data-aura] button')).toHaveCount(0);expect(privateReads).toEqual([]);page.off('request',readListener);
 await page.locator('[aria-controls="site-account-menu"]').click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await expect(page.locator('.account-avatar')).toHaveCount(0);
 expect((await page.request.get('/api/v1/aura/progress')).status()).toBe(401);await login(page,prefix);await checkedCard(page);await page.goto('/profile');await checkedCard(page);
 const screenshot=async name=>page.screenshot({path:process.env.AURA_LEVEL_E2E_EVIDENCE?path.join(process.env.AURA_LEVEL_E2E_EVIDENCE,name):testInfo.outputPath(name),fullPage:true});
 const preferences=async(theme,language)=>{
  if(await page.locator('html').getAttribute('data-theme')!==theme)await page.locator('.u219-tg').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
  if((await page.locator('.u267-cd').textContent()).toLowerCase()!==language){await page.locator('.u267-gb').click();await page.getByRole('option',{name:language==='en'?'English':'Tiếng Việt',exact:true}).click();}
 };
 if(new URL(page.url()).pathname!=='/profile')await page.goto('/profile');
 for(const width of [375,768,1440])for(const theme of ['dark','light'])for(const language of ['vi','en']){
  await page.setViewportSize({width,height:960});await preferences(theme,language);
  await checkedCard(page,language);expect(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await screenshot('aura-real-profile-'+width+'-'+theme+'-'+language+'.png');
 }
 await page.setViewportSize({width:1440,height:960});await page.goto('/');
 for(const theme of ['dark','light'])for(const language of ['vi','en']){
  await preferences(theme,language);await checkedCard(page,language);await screenshot('aura-real-home-1440-'+theme+'-'+language+'.png');
 }
 expect(await progress(page)).toMatchObject({earned_xp:15,bonus_xp:0,total_xp:15,level:2,streak_days:1,checked_in:true});expect(errors).toEqual([]);
});
