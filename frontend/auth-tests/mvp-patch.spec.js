import {test,expect} from '@playwright/test';
import {profileServer,pageOf,uid} from './profile-fixture.js';
for(const [role,width,theme,language] of [['guest',375,'dark','vi'],['user',768,'light','en'],['admin',1440,'dark','vi']])test('MVP Profile collections and privacy '+role,async({page,context})=>{
 await profileServer(context,{signed:role!=='guest',admin:role==='admin'});
 await context.route('**/inventory/me?*',route=>{const kind=new URL(route.request().url()).searchParams.get('kind');return route.fulfill({json:pageOf(Array.from({length:9},(_,i)=>({asset:{id:uid.slice(0,-3)+(301+i),slug:kind+'-'+i,display_name:kind+' '+i,kind,rarity:'DCBAS'[i%5],effect_key:'violet-base',media_url:'/api/v1/catalog/assets/'+uid},quantity:i+1,equipped:false})))});});
 await context.route('**/users/profile_owner/inventory?*',route=>{
  const kind=new URL(route.request().url()).searchParams.get('kind');
  return route.fulfill({json:pageOf([{asset:{id:uid,slug:kind,display_name:kind,kind,rarity:'D',effect_key:'violet-base',media_url:'/api/v1/catalog/assets/'+uid},equipped:true}])});
 });
 await page.addInitScript(v=>localStorage.setItem('aurameme-ui-preferences',JSON.stringify(v)),{theme,language});await page.setViewportSize({width,height:960});await page.goto('/profile/profile_owner');
 await expect(page.locator('[data-activity-day]')).toHaveCount(371);await expect(page.locator('.am-profile-comments,.am-profile-account-links')).toHaveCount(0);
 await expect(page.locator('.am-profile-collection')).toHaveCount(2);
 if(role==='guest'){
  await expect(page.locator('.am-profile-item')).toHaveCount(2);
  await expect(page.locator('.am-profile-quantity,.am-profile-edit')).toHaveCount(0);
 }
 if(role!=='guest'){for(const collection of await page.locator('.am-profile-collection').all()){await expect(collection.locator('.am-profile-item')).toHaveCount(9);expect(await collection.locator('.am-profile-inventory').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length)).toBe(3);const rarity=await collection.locator('.am-profile-item').evaluateAll(es=>es.map(e=>e.dataset.rarity));expect(rarity).toEqual(['S','A','A','B','B','C','C','D','D']);}await expect(page.locator('[data-aura]')).toContainText('0 Exp');}
 await expect(page.locator('[data-post-id]')).not.toContainText('Lvl —');await expect(page.locator('[data-post-id]')).not.toContainText('Đang phát triển');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
