import {test,expect} from '@playwright/test';
const owner={id:'00000000-0000-4000-8000-000000000001',username:'profile_owner',display_name:'Synthetic Owner',email:'private@example.com',phone:'private-phone',address:'private-address',roles:['USER'],status:'active',bio:'Synthetic public bio',created_at:'2026-11-01T00:00:00Z',avatar_url:null};
const pageOf=items=>({items,pagination:{page:1,page_size:20,total:items.length,total_pages:items.length?1:0}});
async function api(context,{signed=true,admin=false}={}){
 const state={user:signed?{...owner,roles:admin?['USER','ADMIN']:['USER']}:null,error:null,requests:[],contact:null,items:[],profile:{...owner}};
 await context.route('**/api/v1/**',async route=>{
  const r=route.request(),url=new URL(r.url()),p=url.pathname.replace('/api/v1',''),method=r.method();let body;try{body=r.postDataJSON()}catch{}
  state.requests.push({p,method,body,csrf:r.headers()['x-csrf-token'],query:Object.fromEntries(url.searchParams)});
  const send=(status,value)=>route.fulfill({status,contentType:'application/json',body:status===204?'':JSON.stringify(value)}),fail=(status,code)=>send(status,{error:{code}});
  if(p==='/users/me'&&method==='PATCH'){Object.assign(state.user,body);Object.assign(state.profile,body);return send(200,state.user)}
  if(p==='/inventory/equipment/avatar'){state.items.forEach(i=>i.equipped=i.asset.id===body.asset_id);return send(200,{slot_kind:'avatar',asset_id:body.asset_id})}
  if(p==='/inventory/me')return send(200,pageOf(state.items));
  if(p==='/users/me')return state.user?send(200,state.user):fail(401,'UNAUTHORIZED');
  if(p==='/auth/csrf')return send(200,{csrf_token:'bound-csrf'});
  if(p==='/auth/login'){state.user={...owner};return send(200,state.user)}
  if(p==='/auth/logout'){state.user=null;return send(204)}
  if(p==='/users/profile_owner')return send(200,{id:owner.id,username:owner.username,display_name:state.profile.display_name,bio:state.profile.bio,created_at:owner.created_at,avatar_url:null});
  if(p==='/users/profile_owner/comments')return send(200,pageOf([]));
  if(p==='/posts'||p==='/categories'||p==='/inventory/me'||p==='/admin/contacts')return send(200,pageOf([]));
  if(p==='/contact'){
   if(state.error)return fail(state.error,state.error===429?'RATE_LIMITED':'CSRF_INVALID');
   if(!state.user)return fail(401,'UNAUTHORIZED');
   state.contact=body;return send(201,{id:owner.id,status:'new'});
  }
  return fail(404,'NOT_FOUND');
 });return state;
}
const submit=page=>page.getByRole('button',{name:'Gửi tin nhắn ngay',exact:true}).click();
test('guest contact/vault require login with safe next; login returns to Contact',async({page,context})=>{
 await api(context,{signed:false});await page.goto('/contact');await expect(page).toHaveURL(/\/login\?next=%2Fcontact$/);
 await page.locator('#identifier').fill('private@example.com');await page.locator('#password').fill('Synthetic password 123!');await page.locator('#loginForm button[type=submit]').click();await expect(page).toHaveURL(/\/contact$/);
 await expect(page.getByRole('heading',{name:'Liên hệ AuraMeme'})).toBeVisible();
});
test('contact contract, validation, loading/error retry and success',async({page,context})=>{
 const s=await api(context);await page.goto('/contact');await expect(page.locator('#contact-name')).toHaveValue(owner.display_name);
 await page.locator('#contact-message').fill('Synthetic feedback');s.error=429;await submit(page);
 await expect(page.getByRole('alert')).toContainText('Quá nhiều');await expect(page.locator('#contact-message')).toHaveValue('Synthetic feedback');
 s.error=null;await submit(page);await expect(page.getByRole('status')).toContainText('Đã gửi');
 expect(s.contact).toEqual({name:owner.display_name,email:owner.email,subject:'Góp ý tính năng',body:'Synthetic feedback'});
 expect(s.requests.find(r=>r.p==='/contact').csrf).toBe('bound-csrf');
});
for(const signed of [false,true])test('public/self profile privacy '+signed,async({page,context})=>{
 const s=await api(context,{signed});await page.goto('/profile/profile_owner');await expect(page.getByRole('heading',{name:owner.display_name,exact:true})).toBeVisible();
 await expect(page.getByText(owner.email,{exact:true})).toHaveCount(0);await expect(page.getByText(owner.phone)).toHaveCount(0);await expect(page.getByText('ADMIN',{exact:true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Chỉnh sửa hồ sơ',exact:true})).toHaveCount(signed?1:0);
 await expect(page.getByRole('link',{name:'Xếp hạng',exact:true})).toHaveCount(0);
 await expect(page.locator('[data-cover],input[type=file]')).toHaveCount(0);
 if(signed){await page.getByRole('button',{name:'Chỉnh sửa hồ sơ',exact:true}).click();await expect(page.getByLabel('Tiểu sử')).toHaveValue(owner.bio);}
});
for(const role of ['guest','user','admin'])for(const width of [375,768,1440])for(const theme of ['dark','light'])test('profile/contact responsive '+role+' '+width+' '+theme,async({page,context})=>{
 await api(context,{signed:role!=='guest',admin:role==='admin'});await page.setViewportSize({width,height:960});await page.addInitScript(theme=>localStorage.setItem('aurameme-ui-preferences',JSON.stringify({theme,language:'vi'})),theme);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const route of ['/profile/profile_owner','/contact','/vault',...(role==='admin'?['/admin/contacts']:[])]){
  await page.goto(route);if(role==='guest'&&route!=='/profile/profile_owner')await expect(page).toHaveURL(new RegExp('/login\\?next='+encodeURIComponent(route)+'$'));await expect(page.locator('main')).toBeVisible();await expect(page.locator('main [aria-busy=true]')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.AURA_EVIDENCE)await page.screenshot({path:process.env.AURA_EVIDENCE+'/'+role+'-'+route.replaceAll('/','-')+'-'+width+'-'+theme+'.png',fullPage:true});
 }expect(errors).toEqual([]);
});
test('expired Contact session redirects and does not claim success',async({page,context})=>{
 const s=await api(context);await page.goto('/contact');await page.locator('#contact-message').fill('Synthetic feedback');s.user=null;await submit(page);await expect(page).toHaveURL(/\/login\?next=%2Fcontact$/);
});

test('other profile has no owner controls or private inventory reads; ADMIN sees Inbox only on self',async({page,context})=>{
 const s=await api(context,{admin:true});s.user={...s.user,username:'different_admin'};await page.goto('/profile/profile_owner');
 await expect(page.getByRole('heading',{name:owner.display_name,exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Chỉnh sửa hồ sơ',exact:true})).toHaveCount(0);
 await expect(page.getByRole('link',{name:'Hộp thư quản trị',exact:true})).toHaveCount(0);
 expect(s.requests.some(r=>r.p==='/inventory/me')).toBe(false);
 s.user={...owner,roles:['USER','ADMIN']};await page.goto('/profile');await page.getByRole('link',{name:'Hộp thư quản trị',exact:true}).click();await expect(page.getByRole('heading',{name:'Hộp thư quản trị',exact:true})).toBeVisible();
 s.user={...owner};await page.reload();await expect(page.getByRole('heading',{name:'Không có quyền truy cập'})).toBeVisible();
});
test('owner edits name/bio with CSRF; owned inventory avatar uses existing equip contract',async({page,context})=>{
 const s=await api(context);await page.goto('/profile');await page.getByRole('button',{name:'Chỉnh sửa hồ sơ',exact:true}).click();
 await page.getByLabel('Tên hiển thị',{exact:true}).fill('Updated Synthetic');await page.getByRole('textbox',{name:'Tiểu sử',exact:true}).fill('Updated public bio');await page.getByRole('button',{name:'Lưu thay đổi',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Updated Synthetic',exact:true})).toBeVisible();
 const patch=s.requests.find(r=>r.method==='PATCH');expect(patch.body).toEqual({display_name:'Updated Synthetic',bio:'Updated public bio'});expect(patch.csrf).toBe('bound-csrf');
 s.items=[{asset:{id:owner.id,kind:'avatar',slug:'synthetic-owned',media_url:'/api/v1/catalog/assets/'+owner.id},quantity:1,equipped:false}];
 await page.goto('/vault');await page.getByRole('button',{name:'Dùng làm Avatar',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'Đã cập nhật Avatar'})).toBeVisible();expect(s.requests.find(r=>r.p==='/inventory/equipment/avatar').body).toEqual({asset_id:owner.id});
 await page.getByRole('button',{name:'Dùng Avatar mặc định',exact:true}).click();await expect.poll(()=>s.requests.filter(r=>r.p==='/inventory/equipment/avatar').at(-1).body).toEqual({asset_id:null});
});
test('VI EN and keyboard preserve Contact draft, native validity prevents invalid email submits',async({page,context})=>{
 const s=await api(context);await page.goto('/contact');await page.locator('#contact-message').fill('Draft retained');
 await page.locator('.u267-gb').click();await page.getByRole('option',{name:'English',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Contact AuraMeme'})).toBeVisible();await expect(page.locator('#contact-message')).toHaveValue('Draft retained');
 await page.locator('#contact-name').focus();await page.keyboard.press('Tab');await expect(page.locator('#contact-email')).toBeFocused();
 await page.locator('#contact-email').fill('bad');await page.getByRole('button',{name:'Send message',exact:true}).click();expect(s.contact).toBeNull();
});
test('expired protected GET refreshes session before redirect',async({page,context})=>{
 const s=await api(context);await context.route('**/api/v1/inventory/me*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[],pagination:{page:1,page_size:20,total:21,total_pages:2}})}));await page.goto('/vault');await expect(page.getByRole('heading',{name:'Bảo Khố của tôi'})).toBeVisible();
 s.user=null;await context.route('**/api/v1/inventory/me*',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({error:{code:'UNAUTHORIZED'}})}));
 await page.getByRole('button',{name:'Tiếp',exact:true}).click();await expect(page).toHaveURL(/\/login\?next=%2Fvault$/);
});
