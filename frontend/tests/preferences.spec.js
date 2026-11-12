import { test, expect } from '@playwright/test';

const choose = async (page, code) => {
  await page.locator('.u267-gb').click();
  await page.getByRole('option', { name: code === 'en' ? 'English' : 'Tiếng Việt', exact: true }).click();
};
test('dark VI keeps the approved two-line Explore heading at 375px', async ({page}) => {
  await page.setViewportSize({width:375,height:900});
  await page.goto('/explore',{waitUntil:'networkidle'});
  await page.evaluate(()=>document.fonts.ready);
  const box=await page.locator('h1').boundingBox();
  expect(box.height).toBe(96);expect(box.width).toBe(343);
});
test('language list supports keyboard, selected check and persistence without losing auth fields', async ({ page }) => {
  await page.goto('/register');
  await page.locator('#identifier').fill('Khang_dev@example.com');
  await page.locator('#password').fill('demo-password');
  await page.locator('#confirmPassword').fill('demo-password');
  const globe = page.locator('.u267-gb');
  await globe.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('option', { selected: true })).toHaveAttribute('lang','vi');
  await expect(page.getByRole('option', { selected: true })).toBeFocused();
  await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  await expect(page.getByRole('heading',{name:'Create an AuraMeme account'})).toBeVisible();
  await expect(page.locator('#identifier')).toHaveValue('Khang_dev@example.com');
  await expect(page.locator('#password')).toHaveValue('demo-password');
  await expect(page.locator('#confirmPassword')).toHaveValue('demo-password');
  expect(await page.evaluate(()=>JSON.stringify(localStorage))).not.toContain('demo-password');
  await expect(globe).toBeFocused();
  await globe.click(); await expect(page.getByRole('option',{selected:true})).toHaveAttribute('lang','en');
  await page.keyboard.press('Escape'); await expect(globe).toBeFocused();
  await page.reload(); await expect(page.locator('.u267-cd')).toHaveText('EN');
  await expect(page.getByRole('heading',{name:'Create an AuraMeme account'})).toBeVisible();
});
test('theme switches the whole page with a circle, retains input and persists on navigation', async ({ page }) => {
  await page.goto('/login');
  await page.locator('#identifier').fill('Kien_dev@example.com');
  await page.locator('#password').fill('demo-password');
  await page.locator('.u219-tg').click();
  await expect(page.locator('#root')).toHaveAttribute('data-theme','light');
  await expect.poll(()=>page.evaluate(()=>document.documentElement.classList.contains('u219-reveal'))).toBe(false);
  await expect(page.locator('#identifier')).toHaveValue('Kien_dev@example.com');
  await expect(page.locator('#password')).toHaveValue('demo-password');
  expect(await page.locator('#root').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(244, 242, 238)');
  await page.locator('.site-nav').getByRole('link',{name:'Khám phá',exact:true}).click();
  await expect(page.locator('#root')).toHaveAttribute('data-theme','light');
  await page.locator('.u219-tg').click();
  await expect(page.locator('#root')).toHaveAttribute('data-theme','dark');
});
test('reduced motion and browsers without view transitions still reach final states', async ({ page }) => {
  await page.emulateMedia({ reducedMotion:'reduce' });
  await page.addInitScript(()=>{document.startViewTransition=undefined});
  await page.setViewportSize({width:375,height:900});
  await page.goto('/');
  await page.locator('.u219-tg').click();
  await choose(page,'en');
  await expect(page.locator('#root')).toHaveAttribute('data-theme','light');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  await expect(page.getByRole('button',{name:'Log in to post',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(375);
  expect(await page.locator('.u267-sw.is-go,.u267-sw.is-in').count()).toBe(0);
  await page.getByRole('button',{name:'Log in to post',exact:true}).click();
  await expect(page).toHaveURL('/login');
});
test('Lucian motion uses the original circle timing and staggered text exit/entry', async ({ page }, testInfo) => {
  await page.setViewportSize({width:1440,height:900});
  await page.goto('/about');
  await page.locator('.u219-tg').click();
  await expect.poll(()=>page.evaluate(()=>document.getAnimations().some(a=>a.effect?.pseudoElement==='::view-transition-new(root)'))).toBe(true);
  const timing=await page.evaluate(()=>{
    const animation=document.getAnimations().find(a=>a.effect?.pseudoElement==='::view-transition-new(root)');
    animation.pause();animation.currentTime=350;
    return {duration:animation.effect.getTiming().duration,easing:animation.effect.getTiming().easing,frames:animation.effect.getKeyframes()};
  });
  expect(timing.duration).toBe(700);expect(timing.easing).toBe('cubic-bezier(0.65, 0, 0.35, 1)');
  expect(timing.frames[0].clipPath).toContain('circle(0px');
  await page.screenshot({path:testInfo.outputPath('theme-circle-midpoint.png')});
  await page.evaluate(()=>document.getAnimations().find(a=>a.effect?.pseudoElement==='::view-transition-new(root)')?.play());
  await expect(page.locator('html')).not.toHaveClass(/u219-reveal/);
  await page.evaluate(()=>{
    window.__u267Motion=[];
    document.querySelector('.site-nav a .u267-sw>span').addEventListener('animationstart',event=>window.__u267Motion.push({name:event.animationName,duration:getComputedStyle(event.target).animationDuration}));
  });
  await choose(page,'en');
  await expect(page.getByRole('heading',{name:'About AuraMeme',exact:true})).toBeVisible();
  const motion=await page.evaluate(()=>({events:window.__u267Motion,delays:[...document.querySelectorAll('.site-nav a .u267-sw')].map(el=>Number(el.dataset.swapDelay))}));
  expect(motion.events).toContainEqual({name:'u267-out',duration:'0.26s'});
  expect(motion.events).toContainEqual({name:'u267-in',duration:'0.38s'});
  expect(motion.delays[1]-motion.delays[0]).toBe(45);
  await page.screenshot({path:testInfo.outputPath('light-english-about.png')});
});
test('switching both preferences preserves filters, demo identity and native post controls', async ({ page }) => {
  await page.addInitScript(()=>localStorage.setItem('aurameme-stitch-demo-user',JSON.stringify({displayName:'Kien Dev',username:'Kien_dev'})));
  await page.goto('/?category=Gaming&q=production&sort=hot');
  await choose(page,'en');
  await page.locator('.u219-tg').click();
  await expect(page.locator('.account-avatar')).toHaveAttribute('src','/assets/demo/kien.jpg');
  await expect(page.getByRole('searchbox',{name:'Search memes, authors, tags'})).toHaveValue('production');
  await expect(page.getByRole('combobox',{name:'Filter posts by category'})).toHaveValue('Gaming');
  await expect(page.locator('article[data-post-id]:visible')).toHaveAttribute('data-post-id','khang');
  await expect(page.locator('[data-sort="hot"]')).toHaveAttribute('aria-pressed','true');
  await expect(page).toHaveURL('/?category=Gaming&q=production&sort=hot');
  await expect(page.locator('html')).not.toHaveClass(/u219-reveal/);
  await page.locator('#btn-toggle-reaction-popover').click();
  await expect(page.locator('#reaction-popover')).toBeVisible();
});
test('checked agreement remains visible in light mode and keeps user edits across languages', async ({page}) => {
  await page.goto('/register');
  const terms=page.locator('#terms');
  await expect(terms).toBeChecked();
  await page.locator('.u219-tg').click();
  await expect(page.locator('#root')).toHaveAttribute('data-theme','light');
  const colors=await terms.evaluate(el=>({background:getComputedStyle(el).backgroundColor,foreground:getComputedStyle(el).color}));
  expect(colors.background).toBe(colors.foreground);
  await expect(page.locator('html')).not.toHaveClass(/u219-reveal/);
  await terms.uncheck();await choose(page,'en');
  await expect(terms).not.toBeChecked();
});
