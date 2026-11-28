import {test,expect} from '@playwright/test';

const uid='00000000-0000-4000-8000-000000000001',pid='00000000-0000-4000-8000-000000000002',cid='00000000-0000-4000-8000-000000000003';
const aid='00000000-0000-4000-8000-000000000004',bid='00000000-0000-4000-8000-000000000005';
const counts=()=>({like:0,love:0,laugh:0,fire:0,sad:0,angry:0});
const asset=(id,name)=>({id,slug:'synthetic-'+id,kind:'avatar',rarity:'D',display_name:name,effect_key:null,available:true,media_url:'/api/v1/catalog/assets/'+id});
const first=asset(aid,'Mèo thử'),second=asset(bid,'Chó thử');
const user={id:uid,username:'meme_owner',display_name:'Meme Owner',email:'owner@example.com',roles:['USER'],status:'active',avatar_url:null};

async function api(context,{guest=false,failInventory=false,malformedRead=false}={}){
 const states={post:{reaction:null,meme:null},comment:{reaction:null,meme:null}},requests=[];
 const category={id:cid,slug:'gaming',name:'Gaming',post_count:1,status:'active'};
 const page=(items,n=1,total=items.length,pages=1)=>({items,pagination:{page:n,page_size:20,total,total_pages:pages}});
 const interactions=kind=>({[kind+'_id']:kind==='post'?pid:cid,reaction_counts:{...counts(),...(states[kind].reaction?{[states[kind].reaction]:1}:{})},viewer_reaction:guest?null:states[kind].reaction,
  viewer_meme_asset_id:guest?null:states[kind].meme,meme_reactions:states[kind].meme?[{asset:states[kind].meme===aid?first:second,count:1}]:[],...(kind==='post'?{comments_count:1,bookmarked:false}:{})});
 await context.route('**/api/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname.slice('/api/v1'.length),method=req.method();
  let body;try{body=req.postDataJSON()}catch{}
  requests.push({path,method,body,page:url.searchParams.get('page')});
  const send=(status,value)=>route.fulfill({status,contentType:'application/json',body:status===204?'':JSON.stringify(value)});
  const fail=(status,code)=>send(status,{error:{code,message:'Synthetic fixture'}});
  if(path.startsWith('/catalog/assets/'))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6S8AAAAASUVORK5CYII=','base64')});
  if(path==='/users/me')return guest?fail(401,'UNAUTHORIZED'):send(200,user);
  if(path==='/auth/csrf')return send(200,{csrf_token:'owned-fixture-csrf'});
  if(path==='/categories')return send(200,page([category]));
  if(path==='/posts')return send(200,page([{id:pid,author:user,category,title:'Owned Meme test',content:'Persistent Meme reactions',status:'published',created_at:'2026-11-14T00:00:00Z',updated_at:'2026-11-14T00:00:00Z',media_url:null,interactions:interactions('post')}]));
  if(path===`/posts/${pid}/comments`)return send(200,page([{id:cid,post_id:pid,author:user,body:'Synthetic comment',created_at:'2026-11-14T00:00:00Z'}]));
  const kind=path.startsWith('/comments/')?'comment':'post';
  if(path.endsWith('/interactions')){
   const value=interactions(kind);
   if(malformedRead&&states[kind].meme)value.meme_reactions=[{asset:{...first,media_url:'https://evil.example/image.png'},count:1}];
   return send(200,value);
  }
  if(path==='/inventory/me'){
   if(guest)return fail(401,'UNAUTHORIZED');
   if(failInventory)return fail(503,'NOT_READY');
   const n=Number(url.searchParams.get('page'));
   return send(200,page(n===1?[{asset:first,quantity:3,equipped:false}]:[{asset:second,quantity:7,equipped:true}],n,2,2));
  }
  if(path.endsWith('/reactions')){
   if(guest)return fail(401,'UNAUTHORIZED');
   if(method==='GET'){
    const memeItem=states[kind].meme?[{asset:states[kind].meme===aid?first:second,count:1}]:[];
    return send(200,{items:[],pagination:{page:1,page_size:20,total:0,total_pages:0},reaction_counts:{like:0,love:0,laugh:0,fire:0,sad:0,angry:0},meme_reactions:memeItem});
   }
   expect(req.headers()['x-csrf-token']).toBe('owned-fixture-csrf');
   states[kind]={reaction:method==='DELETE'||body.reaction_type==='meme'?null:body.reaction_type,meme:method==='DELETE'||body.reaction_type!=='meme'?null:body.meme_asset_id};
   return send(method==='DELETE'?204:200,{reaction_type:states[kind].meme?'meme':states[kind].reaction});
  }
  return fail(404,'NOT_FOUND');
 });
 return {states,requests};
}

for(const [width,path] of [[375,'/'],[768,'/explore'],[1440,'/']])test(`owned Meme picker paginates and persists post/comment selection at ${width}`,async({page,context},info)=>{
 const server=await api(context);await page.setViewportSize({width,height:900});await page.goto(path);
 const card=page.locator(`[data-post-id="${pid}"]`);await expect(card).toBeVisible();
 await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
 const picker=page.getByRole('dialog',{name:'Bộ chọn reaction'});
 expect(server.requests.filter(row=>row.path==='/inventory/me')).toHaveLength(0);
 await picker.getByRole('button',{name:'Meme của tôi',exact:true}).click();
 await expect(picker.getByRole('button',{name:'Thả Meme Mèo thử',exact:true})).toBeVisible();
 await picker.getByRole('button',{name:'Xem thêm Meme',exact:true}).click();
 await expect(picker.getByRole('button',{name:'Thả Meme Chó thử',exact:true})).toBeVisible();
 expect(server.requests.filter(row=>row.path==='/inventory/me').map(row=>row.page)).toEqual(['1','2']);
 expect(await picker.locator('[data-owned-meme] img').evaluateAll(images=>images.every(img=>new URL(img.src).pathname.startsWith('/api/v1/catalog/assets/')))).toBe(true);
 await page.screenshot({path:info.outputPath(`owned-picker-${width}.png`)});
 await picker.getByRole('button',{name:'Thả Meme Chó thử',exact:true}).click();
 await expect(card.locator(`[data-reaction-pill="meme-${bid}"]`)).toHaveAttribute('aria-pressed','true');
 await page.reload();await expect(card.locator(`[data-reaction-pill="meme-${bid}"]`)).toHaveAttribute('aria-pressed','true');
 await card.locator(`[data-reaction-pill="meme-${bid}"]`).click();
 await expect(page.locator('[role="dialog"][aria-label="Biểu cảm"]')).toBeVisible();
 await expect(card.locator(`[data-reaction-pill="meme-${bid}"]`)).toHaveCount(1);
 await page.keyboard.press('Escape');
 await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
 await picker.getByRole('button',{name:'Meme của tôi',exact:true}).click();
 await picker.getByRole('button',{name:'Xem thêm Meme',exact:true}).click();
 await picker.getByRole('button',{name:'Thả Meme Chó thử',exact:true}).click();
 await expect(card.locator(`[data-reaction-pill="meme-${bid}"]`)).toHaveCount(0);
 if(path==='/explore')await page.goto('/');
 await card.getByRole('button',{name:'Bình luận',exact:true}).click();
 const comment=card.locator(`[data-comment-id="${cid}"]`);await expect(comment).toBeVisible();
 const cookieDismiss=page.locator('.am-cookie-root button').first();
 if(await cookieDismiss.isVisible().catch(()=>false))await cookieDismiss.click();
 await comment.getByRole('button',{name:'Thả biểu cảm bình luận',exact:true}).click();
 await picker.getByRole('button',{name:'Meme của tôi',exact:true}).click();
 await picker.getByRole('button',{name:'Thả Meme Mèo thử',exact:true}).click();
 await expect(comment.locator(`[data-reaction-pill="meme-${aid}"]`)).toHaveAttribute('aria-pressed','true');
 const writes=server.requests.filter(row=>['PUT','DELETE'].includes(row.method));
 expect(writes.map(row=>row.body?.reaction_type||'DELETE')).toEqual(['meme','DELETE','meme']);
 expect(writes[0].body).toEqual({reaction_type:'meme',meme_asset_id:bid});
 expect(server.states.comment.meme).toBe(aid);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test('guest inventory picker never fetches or offers pretend owned Meme actions',async({page,context})=>{
 const server=await api(context,{guest:true});await page.goto('/');
 await page.locator(`[data-post-id="${pid}"]`).getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
 const picker=page.getByRole('dialog',{name:'Bộ chọn reaction'});await picker.getByRole('button',{name:'Meme của tôi'}).click();
 await expect(picker.getByRole('link',{name:'Đăng nhập',exact:true})).toBeVisible();
 expect(server.requests.filter(row=>row.path==='/inventory/me')).toHaveLength(0);
 await expect(picker.locator('[data-owned-meme]')).toHaveCount(0);
});

test('inventory failure keeps standard reaction available and reports no owned reward',async({page,context})=>{
 const server=await api(context,{failInventory:true});await page.goto('/');
 const card=page.locator(`[data-post-id="${pid}"]`);await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
 const picker=page.getByRole('dialog',{name:'Bộ chọn reaction'});await picker.getByRole('button',{name:'Meme của tôi'}).click();
 await expect(picker.getByRole('alert')).toBeVisible();await expect(picker.locator('[data-owned-meme]')).toHaveCount(0);
 await picker.getByRole('button',{name:'Biểu cảm',exact:true}).click();await picker.getByRole('button',{name:'Yêu',exact:true}).click();
 await expect(card.locator('[data-reaction-pill="love"]')).toHaveAttribute('aria-pressed','true');
 expect(server.requests.filter(row=>row.method==='PUT')[0].body).toEqual({reaction_type:'love'});
});

test('malformed Meme read after committed selection preserves the feed and reports synchronization failure',async({page,context})=>{
 await api(context,{malformedRead:true});await page.goto('/');
 const card=page.locator(`[data-post-id="${pid}"]`);await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();
 const picker=page.getByRole('dialog',{name:'Bộ chọn reaction'});await picker.getByRole('button',{name:'Meme của tôi'}).click();
 await picker.getByRole('button',{name:'Thả Meme Mèo thử',exact:true}).click();
 await expect(card).toBeVisible();await expect(page.getByRole('alert').filter({hasText:'Đã lưu thay đổi'})).toBeVisible();
 await expect(card.locator(`[data-reaction-pill="meme-${aid}"]`)).toHaveCount(0);
});

test('owned Meme picker uses English controls without changing server item names',async({page,context})=>{
 await api(context);await page.addInitScript(()=>localStorage.setItem('aurameme-ui-preferences',JSON.stringify({language:'en',theme:'light'})));await page.goto('/');
 await page.locator('[data-post-id]').getByRole('button',{name:'React',exact:true}).click();const picker=page.getByRole('dialog');await picker.getByRole('button',{name:'My memes',exact:true}).click();
 await expect(picker.getByRole('button',{name:'React with Meme Mèo thử',exact:true})).toBeVisible();await expect(picker.getByRole('button',{name:'Load more memes',exact:true})).toBeVisible();await expect(picker).toContainText('Using owned memes does not consume quantity.');
});
