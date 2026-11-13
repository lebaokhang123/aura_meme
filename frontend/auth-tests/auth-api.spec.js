import {test,expect} from '@playwright/test';
const password='Synthetic-test-password!';
const identities=['khang_dev','kien_dev','gigachad'].map((username,index)=>({
 id:'00000000-0000-4000-8000-00000000000'+(index+1),username,email:username+'@example.com',
 display_name:['Khang Dev','Kien Dev','Gigachad'][index],roles:index<2?['USER','ADMIN']:['USER'],status:'active'
}));
async function api(context){
 const state={user:null,offline:false,loginError:null,requests:[]};
 await context.route('**/api/v1/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname,method=request.method();
  let body=null;try{body=request.postDataJSON();}catch{}
  state.requests.push({path,method,body,csrf:request.headers()['x-csrf-token']});
  if(state.offline)return route.abort('failed');
  const send=(status,data)=>route.fulfill({status,contentType:'application/json',body:status===204?'':JSON.stringify(data)});
  const fail=(status,code)=>send(status,{error:{code,message:'safe'}});
  if(path==='/api/v1/users/me')return state.user?send(200,state.user):fail(401,'UNAUTHORIZED');
  if(path.endsWith('/csrf'))return send(200,{csrf_token:'server-csrf'});
  if(request.headers()['x-csrf-token']!=='server-csrf')return fail(403,'CSRF_INVALID');
  if(path.endsWith('/login')){
   if(state.loginError)return fail(state.loginError.status,state.loginError.code);
   const user=identities.find(row=>row.email===body.email.toLowerCase());
   if(!user||body.password!==password)return fail(401,'UNAUTHORIZED');
   state.user=user;return send(200,user);
  }
  if(path.endsWith('/register'))return send(201,{...identities[2],...body,roles:['USER']});
  if(path.endsWith('/logout')){state.user=null;return send(204);}
  return fail(404,'NOT_FOUND');
 });
 return state;
}
const submit=page=>page.locator('#loginForm button[type=submit]').click();
async function login(page,email='khang_dev@example.com',value=password){
 await page.goto('/login');await page.locator('#identifier').fill(email);await page.locator('#password').fill(value);await submit(page);
}
test('real mode ignores forged localStorage identity; wrong password stays on form; valid identity comes from me',async({page,context})=>{
 const server=await api(context);
 await page.addInitScript(()=>localStorage.setItem('aurameme-stitch-demo-user',JSON.stringify({username:'Khang_dev',roles:['ADMIN']})));
 await page.goto('/');await expect(page.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);
 await login(page,'gigachad@example.com','wrong-password');await expect(page.getByRole('alert')).toContainText('không đúng');
 await expect(page.locator('#password')).toHaveValue('wrong-password');
 await page.locator('#password').fill(password);await submit(page);
 await expect(page).toHaveURL(/\/$/);await expect(page.locator('.account-avatar')).toHaveAttribute('alt','Ảnh đại diện Gigachad');
 await page.reload();await expect(page.locator('.account-avatar')).toHaveAttribute('alt','Ảnh đại diện Gigachad');
 expect(server.user.username).toBe('gigachad');
 expect(await page.evaluate(()=>JSON.stringify({local:localStorage,session:sessionStorage}))).not.toContain(password);
 const request=server.requests.find(row=>row.path.endsWith('/login'));expect(request.csrf).toBe('server-csrf');
});
test('register uses USER-only payload, password12 policy, keeps VI/EN theme fields and redirects to login without signing in',async({page,context})=>{
 const server=await api(context);await page.setViewportSize({width:375,height:900});await page.goto('/register');
 await expect(page.locator('#password')).toHaveAttribute('minlength','12');
 await page.locator('#username').fill('New_User');await page.locator('#identifier').fill('new@example.com');
 await page.locator('#password').fill(password);await page.locator('#confirmPassword').fill(password);
 await page.locator('.u267-gb').click();await page.getByRole('option',{name:'English',exact:true}).click();
 await expect(page.locator('#password')).toHaveValue(password);await expect(page.locator('#password')).toHaveAttribute('placeholder','12–128 characters');
 await page.locator('#terms').check();await submit(page);
 await expect(page).toHaveURL(/\/login\?registered=1$/);
 await expect(page.getByRole('alert')).toContainText('Account created');
 expect(server.user).toBeNull();
 const payload=server.requests.find(row=>row.path.endsWith('/register')).body;
 expect(payload.username).toBe('new_user');expect(payload.display_name).toBe('New_User');expect(payload.roles).toBeUndefined();
});
test('logout uses bound csrf; server revocation is reflected on focus and reload',async({page,context})=>{
 const server=await api(context);await login(page);await expect(page.locator('.account-avatar')).toBeVisible();
 server.user=null;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
 await expect(page.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);
 await login(page);await expect(page.locator('.account-avatar')).toBeVisible();
 await page.getByRole('button',{name:'Mở menu tài khoản'}).click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
 await expect(page.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);expect(server.user).toBeNull();
 expect(server.requests.find(row=>row.path.endsWith('/logout')).csrf).toBe('server-csrf');
});
test('multiple tabs revalidate with server after login/logout without exchanging trusted role data',async({page,context})=>{
 await api(context);await page.goto('/');await expect(page.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);
 const other=await context.newPage();await other.goto('/');await expect(other.getByRole('link',{name:'Đăng nhập',exact:true}).first()).toBeVisible();
 await login(page,'kien_dev@example.com');await expect(page.locator('.account-avatar')).toBeVisible();await expect(other.locator('.account-avatar')).toHaveAttribute('alt','Ảnh đại diện Kien Dev');
 await page.getByRole('button',{name:'Mở menu tài khoản'}).click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();
 await expect(other.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);
});
test('network loss never restores a fake session and retry recovers',async({page,context})=>{
 const server=await api(context);server.offline=true;await page.goto('/login');
 await expect(page.getByRole('alert')).toContainText('Không kết nối được');
 server.offline=false;await page.getByRole('button',{name:'Thử lại',exact:true}).click();
 await expect(page.locator('#identifier')).toBeVisible();
});
for(const [status,code] of [[403,'CSRF_INVALID'],[409,'CONFLICT'],[422,'VALIDATION_ERROR']]){
 test('API '+status+' keeps entered fields and reports an accessible error',async({page,context})=>{
  const server=await api(context);server.loginError={status,code};await login(page);
  await expect(page.getByRole('alert')).toBeVisible();await expect(page.locator('#password')).toHaveValue(password);
  await expect(page.getByRole('button',{name:'Mở menu tài khoản'})).toHaveCount(0);
 });
}
