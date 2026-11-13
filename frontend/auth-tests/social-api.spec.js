import {test,expect} from '@playwright/test';
const uid='00000000-0000-4000-8000-000000000001',cid='00000000-0000-4000-8000-000000000002';
const kinds=['like','love','laugh','fire','sad','angry'],counts=()=>Object.fromEntries(kinds.map(k=>[k,0]));
const user={id:uid,username:'constructor',display_name:'New Author',email:'new@example.com',roles:['USER'],status:'active',avatar_url:null};
async function server(context){
 const state={user:null,posts:[],comments:[],requests:[],dropReplyOnce:false,failFeedOnce:false};
 await context.route('**/api/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname.replace('/api/v1',''),method=req.method();
  let body;try{body=req.postDataJSON()}catch{}
  state.requests.push({p,method,body,query:Object.fromEntries(url.searchParams)});
  const send=(status,value)=>route.fulfill({status,contentType:'application/json',body:status===204?'':JSON.stringify(value)});
  const fail=(status,code)=>send(status,{error:{code,message:'safe'}});
  const interactions=post=>({post_id:post.id,reaction_counts:post.counts,viewer_reaction:state.user?post.reaction:null,comments_count:state.comments.filter(c=>c.post_id===post.id).length,bookmarked:false});
  const dto=post=>({...post,author:user,category:{id:cid,slug:'gaming',name:'Gaming'},created_at:'2026-11-13T00:00:00Z',updated_at:'2026-11-13T00:00:00Z',status:'published',media_url:null,interactions:interactions(post)});
  const page=items=>({items,pagination:{page:1,page_size:20,total:items.length,total_pages:items.length?1:0}});
  if(p==='/users/me')return state.user?send(200,state.user):fail(401,'UNAUTHORIZED');
  if(p==='/auth/csrf')return send(200,{csrf_token:'bound-csrf'});
  if(p==='/auth/login'){state.user=user;return send(200,user)}
  if(p==='/auth/logout'){state.user=null;return send(204)}
  if(p==='/categories')return send(200,page([{id:cid,slug:'gaming',name:'Gaming',status:'active',post_count:state.posts.length}]));
  if(method==='GET'&&p==='/posts'){
   if(state.failFeedOnce){state.failFeedOnce=false;return fail(503,'SERVICE_UNAVAILABLE')}
   return send(200,page(state.posts.map(dto)));
  }
  const post=state.posts.find(v=>p==='/posts/'+v.id||p.startsWith('/posts/'+v.id+'/'));
  if(method==='GET'&&p.endsWith('/interactions')&&post)return send(200,interactions(post));
  if(method==='GET'&&p.endsWith('/comments'))return send(200,page(state.comments.filter(c=>c.post_id===post?.id)));
  if(method==='GET'&&post)return send(200,dto(post));
  const comment=state.comments.find(c=>p==='/comments/'+c.id+'/interactions');
  if(comment)return send(200,{comment_id:comment.id,reaction_counts:counts(),viewer_reaction:null});
  if(method==='GET')return fail(404,'NOT_FOUND');
  if(!state.user)return fail(401,'UNAUTHORIZED');
  if(req.headers()['x-csrf-token']!=='bound-csrf')return fail(403,'CSRF_INVALID');
  if(p==='/posts'&&method==='POST'){
   let row=state.posts.find(v=>v.id===body.request_id);
   if(!row){row={id:body.request_id,title:body.content,content:body.content,counts:counts(),reaction:null};state.posts.unshift(row)}
   if(state.dropReplyOnce){state.dropReplyOnce=false;return route.abort('failed')}
   return send(201,dto(row));
  }
  if(post&&p.endsWith('/reactions')){
   post.counts=counts();post.reaction=method==='DELETE'?null:body.reaction_type;if(post.reaction)post.counts[post.reaction]=1;
   return send(method==='DELETE'?204:200,{post_id:post.id,reaction_type:post.reaction});
  }
  if(post&&p.endsWith('/comments')&&method==='POST'){
   const row={id:body.request_id,post_id:post.id,body:body.body,author:user,created_at:'2026-11-13T00:00:00Z'};
   state.comments.push(row);return send(201,row);
  }
  if(post&&method==='PATCH'){post.content=body.content;return send(200,dto(post))}
  if(post&&method==='DELETE'){state.posts=state.posts.filter(v=>v!==post);return send(204)}
  return fail(404,'NOT_FOUND');
 });
 return state;
}
async function login(page){
 await page.goto('/login');await page.locator('#identifier').fill('new@example.com');await page.locator('#password').fill('Synthetic-password!');
 await page.locator('#loginForm button[type=submit]').click();await expect(page).toHaveURL(/\/$/);
}
test('API mode renders an empty database without importing browser demo posts or identity',async({page,context})=>{
 const api=await server(context);
 await page.addInitScript(()=>localStorage.setItem('aurameme-stitch-demo-user',JSON.stringify({username:'Khang_dev',roles:['ADMIN']})));
 await page.goto('/');await expect(page.getByText('Không tìm thấy bài viết phù hợp.')).toBeVisible();
 await expect(page.locator('[data-post-id]')).toHaveCount(0);await expect(page.locator('.account-avatar')).toHaveCount(0);
 expect(api.requests.some(v=>v.p==='/posts'&&v.query.include_interactions==='true')).toBe(true);
});
test('server-owned posts/reactions/comments/edit/delete persist across reload for a non-demo author',async({page,context})=>{
 await server(context);await login(page);
 await page.getByLabel('Nội dung bài mới').fill('Real API content');await page.getByLabel('Danh mục bài mới').selectOption('gaming');await page.getByRole('button',{name:'Đăng bài',exact:true}).click();
 const card=page.locator('[data-post-id]');await expect(card).toHaveCount(1);await expect(card).toContainText('New Author');
 await card.getByRole('button',{name:'Thả biểu cảm',exact:true}).click();await page.locator('[data-reaction=love]').click();await expect(card.locator('[data-reaction-pill=love]')).toContainText('1');
 await card.getByRole('button',{name:'Bình luận',exact:true}).click();await card.getByLabel('Nội dung bình luận').fill('Hello 🔥');await card.getByRole('button',{name:/^Gửi/}).click();await expect(card.locator('[data-comment-id]')).toContainText('Hello 🔥');
 await page.reload();await expect(page.locator('[data-post-id]')).toHaveCount(1);
 await card.getByRole('button',{name:'Tùy chọn bài viết'}).click();await page.getByRole('menuitem',{name:'Sửa bài',exact:true}).click();await page.getByLabel('Nội dung sửa bài').fill('Edited API content');await page.getByRole('button',{name:'Lưu thay đổi'}).click();await expect(card).toContainText('Edited API content');
 await card.getByRole('button',{name:'Tùy chọn bài viết'}).click();await page.getByRole('menuitem',{name:'Xóa bài',exact:true}).click();await page.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();await expect(card).toHaveCount(0);
});
test('lost POST response retains draft request_id and retry does not create a second post',async({page,context})=>{
 const api=await server(context);await login(page);api.dropReplyOnce=true;
 await page.getByLabel('Nội dung bài mới').fill('Retry me');await page.getByLabel('Danh mục bài mới').selectOption('gaming');await page.getByRole('button',{name:'Đăng bài',exact:true}).click();
 await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByLabel('Nội dung bài mới')).toHaveValue('Retry me');
 await page.getByRole('button',{name:'Đăng bài',exact:true}).click();await expect(page.locator('[data-post-id]')).toHaveCount(1);
 const ids=api.requests.filter(v=>v.p==='/posts'&&v.method==='POST').map(v=>v.body.request_id);expect(ids).toHaveLength(2);expect(ids[0]).toBe(ids[1]);expect(api.posts).toHaveLength(1);
});
test('feed retry reloads posts after a temporary read failure',async({page,context})=>{
 const api=await server(context);api.failFeedOnce=true;
 api.posts.push({id:'00000000-0000-4000-8000-000000000003',title:'Recovered feed',content:'Recovered feed',counts:counts(),reaction:null});
 await page.goto('/');await expect(page.getByRole('alert')).toBeVisible();
 await page.getByRole('button',{name:'Thử lại',exact:true}).click();
 await expect(page.locator('[data-post-id]')).toContainText('Recovered feed');
 await expect(page.getByRole('alert')).toHaveCount(0);
});
