import {test,expect} from '@playwright/test';
import {profileServer,profile} from './profile-fixture.js';
async function aura(context,{error=null,checked=false}={}){
 const state={error,checked,reads:0,writes:0,csrf:null};
 await context.route('**/api/v1/aura/**',async route=>{
 const req=route.request();if(req.method()==='POST'){if(state.postError){state.checked=true;return route.abort();}state.writes++;state.csrf=req.headers()['x-csrf-token'];state.checked=true;return route.fulfill({json:{effective_day:'2026-11-14',already_checked_in:false,earned_xp_delta:15,bonus_xp_delta:0,khi_van_delta:0,streak_days:4}});}
 state.reads++;if(state.delay)await new Promise(resolve=>setTimeout(resolve,state.delay));if(state.error==='network')return route.abort();if(state.error)return route.fulfill({status:state.error,json:{error:{code:state.error===503?'NOT_READY':'SERVER_ERROR'}}});
 return route.fulfill({json:{earned_xp:state.checked?140:125,bonus_xp:0,total_xp:state.checked?140:125,level:state.checked?11:10,fair_level:state.checked?11:10,realm:state.checked?'Trúc Cơ':'Luyện Khí',level_xp:state.checked?10:8,next_level_xp:state.checked?21:20,xp_to_next:state.checked?11:12,streak_days:state.checked?4:3,checked_in:state.checked,effective_day:'2026-11-14',next_reset_at:state.resetAt||new Date(Date.now()+60000).toISOString(),server_time:state.serverTime||new Date().toISOString()}});
 });return state;
}
test('Home check-in uses CSRF, refreshes server progress, survives reload; profile shares real data',async({page,context})=>{
 await profileServer(context);const s=await aura(context);await page.goto('/');const card=page.locator('[data-aura]');await expect(card).toContainText('125 Exp');await expect(card).toContainText('Luyện Khí');
 await card.getByRole('button',{name:'Điểm danh',exact:true}).click();await expect(card).toContainText('140 Exp');await expect(card).toContainText('Trúc Cơ');await expect(card).toContainText('Đã điểm danh');expect(s.csrf).toBeTruthy();expect(s.writes).toBe(1);expect(s.reads).toBeGreaterThan(1);
 await expect(page.getByText('TOP AURA CREATORS')).toHaveCount(0);await expect(page.getByText('Điểm danh (+50 Exp)')).toHaveCount(0);
 await page.reload();await expect(page.locator('[data-aura]')).toContainText('140 Exp');await page.goto('/profile');await expect(page.locator('[data-aura]')).toContainText('140 Exp');await expect(page.locator('[data-aura]')).toContainText('11');
});
for(const error of [503,'network'])test('Aura honest unavailable/error and retry '+error,async({page,context})=>{
 await profileServer(context);const s=await aura(context,{error});await page.goto('/');const card=page.locator('[data-aura]');await expect(card.getByRole('alert')).toContainText(error===503?'chưa sẵn sàng':'Không kết nối');await expect(card).not.toContainText('125 Exp');s.error=null;await card.getByRole('button',{name:'Thử lại',exact:true}).click();await expect(card).toContainText('125 Exp');
});
test('another public profile never requests viewer private Aura',async({page,context})=>{
 const viewer=await profileServer(context);viewer.viewer={...viewer.viewer,id:'00000000-0000-4000-8000-000000000999',username:'different_user'};const s=await aura(context);await page.goto('/profile/'+profile.username);await expect(page.getByRole('heading',{name:profile.display_name,exact:true})).toBeVisible();await expect(page.locator('[data-aura]')).toContainText('Chưa có dữ liệu');expect(s.reads).toBe(0);
});

test('lost check-in response does not invent Exp; retry reads receipt-backed server state',async({page,context})=>{
 await profileServer(context);const s=await aura(context);s.postError=true;await page.goto('/');const card=page.locator('[data-aura]');await expect(card).toContainText('125 Exp');await card.getByRole('button',{name:'Điểm danh',exact:true}).click();await expect(card.getByRole('alert')).toContainText('Không kết nối');await expect(card).not.toContainText('140 Exp');await card.getByRole('button',{name:'Thử lại',exact:true}).click();await expect(card).toContainText('140 Exp');await expect(card.getByRole('button',{name:'Đã điểm danh',exact:true})).toBeDisabled();
});
test('server clock offset drives countdown and refreshes at the server reset',async({page,context})=>{
 await profileServer(context);const s=await aura(context,{checked:true});s.serverTime='2026-11-14T23:59:58Z';s.resetAt='2026-11-15T00:00:00Z';await page.clock.install({time:new Date('2040-01-01T00:00:00Z')});await page.goto('/');await expect(page.locator('[data-aura]')).toContainText('140 Exp');expect(s.reads).toBe(1);s.serverTime='2026-11-15T00:00:00Z';s.resetAt='2026-11-16T00:00:00Z';s.checked=false;await page.clock.fastForward(3000);await expect(page.locator('[data-aura]')).toContainText('125 Exp');expect(s.reads).toBeGreaterThan(1);
});
test('loading hides unknown Exp and expiry removes private progress',async({page,context})=>{
 const session=await profileServer(context);const s=await aura(context);s.delay=600;await page.goto('/');const card=page.locator('[data-aura]');await expect(card.getByRole('status')).toContainText('Đang tải Aura');await expect(card).not.toContainText('125 Exp');await expect(card).toContainText('125 Exp');session.viewer=null;s.error=401;await page.goto('/profile');await expect(page.locator('[data-aura]')).toHaveCount(0);await expect(page).toHaveURL(/\/login/);
});
for(const width of [375,768,1440])test('own profile Aura accessible and no overflow at '+width,async({page,context})=>{
 await profileServer(context);const s=await aura(context);await page.setViewportSize({width,height:960});await page.goto('/profile');const card=page.locator('[data-aura]');await expect(card).toContainText('125 Exp');await expect(card.getByRole('button',{name:'Điểm danh',exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);if(width===375){await card.getByRole('button',{name:'Điểm danh',exact:true}).click();await expect(card).toContainText('140 Exp');expect(s.csrf).toBeTruthy();await page.goto('/');await expect(page.locator('[data-aura]')).toContainText('140 Exp');}
});

test('same username with a different profile ID cannot read private progress',async({page,context})=>{
 const server=await profileServer(context);server.profile.id='00000000-0000-4000-8000-000000000999';const s=await aura(context);await page.goto('/profile/'+profile.username);await expect(page.locator('[data-aura]')).toContainText('Chưa có dữ liệu');expect(s.reads).toBe(0);
});
for(const theme of ['dark','light'])test('English Aura labels and theme preserve server values '+theme,async({page,context})=>{
 await profileServer(context);await aura(context);await page.addInitScript(theme=>localStorage.setItem('aurameme-ui-preferences',JSON.stringify({theme,language:'en'})),theme);await page.goto('/profile');const card=page.locator('[data-aura]');await expect(card).toContainText('125 Exp');await expect(card).toContainText('Earned Exp: 125');await expect(card.getByRole('button',{name:'Check in',exact:true})).toBeVisible();await expect(page.locator('html')).toHaveAttribute('data-theme',theme);await page.screenshot({path:'test-results/aura-profile-'+theme+'.png',fullPage:true});
});
test('logout clears private Aura and next account reload fetches only that account',async({page,context})=>{
 const server=await profileServer(context);const s=await aura(context);await context.route('**/api/v1/auth/logout',route=>{server.viewer=null;return route.fulfill({status:204})});await page.goto('/');await expect(page.locator('[data-aura]')).toContainText('125 Exp');await page.locator('[aria-controls="site-account-menu"]').click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await expect(page.locator('[data-aura]')).toHaveCount(0);const reads=s.reads;server.viewer={...profile,id:'00000000-0000-4000-8000-000000000999',username:'other_user',roles:['USER'],status:'active'};s.checked=true;await page.reload();await expect(page.locator('[data-aura]')).toContainText('140 Exp');expect(s.reads).toBeGreaterThan(reads);
});
