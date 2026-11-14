// Synthetic HTTP fixtures only: never installed or seeded into a database.
import fs from 'node:fs';
export const uid='00000000-0000-4000-8000-000000000101',pid='00000000-0000-4000-8000-000000000102',cid='00000000-0000-4000-8000-000000000103';
export const profile={id:uid,username:'profile_owner',display_name:'Khang Dev',bio:'Nhà phát triển & Tín đồ sưu tầm meme độc bản tại AuraMeme.\n// git commit -m \'push and pray\'',created_at:'2026-01-01T00:00:00Z',avatar_url:'/api/v1/catalog/assets/'+uid};
export const category={id:cid,slug:'gaming',name:'Gaming',status:'active',post_count:1};
const countBase={like:284,love:119,laugh:64,fire:88,sad:42,angry:0};
export const pageOf=items=>({items,pagination:{page:1,page_size:20,total:items.length,total_pages:items.length?1:0}});
export function activity(){const start=new Date('2025-11-10T00:00:00Z');const days=Array.from({length:371},(_,i)=>{const d=new Date(+start+i*86400000).toISOString().slice(0,10);const posts=d==='2026-11-14'?1:0,comments=d==='2026-11-14'?1:0;return {date:d,posts,comments,count:posts+comments}});return {timezone:'Asia/Ho_Chi_Minh',start_date:'2025-11-10',end_date:'2026-11-14',days,total:2};}
export async function profileServer(context,{signed=true,admin=false,empty=false}={}){
 const state={viewer:signed?{...profile,email:'synthetic@example.com',roles:admin?['USER','ADMIN']:['USER'],status:'active'}:null,profile:{...profile},posts:empty?[]:[{id:pid,title:'Meme test',content:'Khi bạn vừa tự tin push code sửa được 1 bug production vào lúc 17h30 thứ 6 nhưng hệ thống phát sinh thêm 7 bug chí mạng... 😭😂',author:profile,category,created_at:'2026-11-14T04:00:00Z',updated_at:'2026-11-14T04:00:00Z',status:'published',media_url:'/api/v1/media/'+pid}],comments:empty?[]:[{id:cid,post_id:pid,author:profile,body:'Bình luận synthetic kiểm thử.',created_at:'2026-11-14T04:30:00Z'}],requests:[],counts:{...countBase},reaction:null,error:0};
 await context.route('**/api/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname.replace('/api/v1',''),method=req.method();let body;try{body=req.postDataJSON()}catch{}
  state.requests.push({p,method,body,query:Object.fromEntries(url.searchParams)});
  const send=(status,data)=>route.fulfill({status,contentType:'application/json',body:status===204?'':JSON.stringify(data)}),fail=(status,code)=>send(status,{error:{code}});
  const interactions=()=>({post_id:pid,reaction_counts:state.counts,viewer_reaction:state.viewer?state.reaction:null,comments_count:state.comments.length,bookmarked:false});
  if(p.startsWith('/catalog/assets/')&&process.env.AURA_PROFILE_FIXTURES&&p.split('/').at(-1)!==uid)return route.fulfill({status:200,contentType:'image/png',body:fs.readFileSync(process.env.AURA_PROFILE_FIXTURES+'/owned-'+(Number(p.slice(-3))-201)+'.png')});
  if(p.startsWith('/catalog/assets/'))return route.fulfill({status:200,contentType:'image/jpeg',body:fs.readFileSync(new URL('../public/assets/demo/khang.jpg',import.meta.url))});
  if(p.startsWith('/media/'))return route.fulfill({status:200,contentType:'image/png',body:fs.readFileSync(process.env.AURA_PROFILE_IMAGE||new URL('../public/assets/brand/symbol-dark-2048.png',import.meta.url))});
  if(p==='/auth/csrf')return send(200,{csrf_token:'fixture-csrf'});
  if(p==='/auth/logout'){state.viewer=null;return send(204)}
  if(p==='/users/me'&&method==='PATCH'){Object.assign(state.profile,body);Object.assign(state.viewer,body);return send(200,state.viewer)}
  if(p==='/users/me')return state.viewer?send(200,state.viewer):fail(401,'UNAUTHORIZED');
  if(p==='/users/profile_owner')return send(200,state.profile);
  if(p==='/users/profile_owner/activity'){const value=activity();if(empty){value.days.forEach(d=>d.posts=d.comments=d.count=0);value.total=0}return send(200,value)}
  if(p==='/users/profile_owner/comments')return send(200,pageOf(state.comments));
  if(p==='/categories')return send(200,pageOf([category]));
  if(p==='/inventory/me')return send(200,pageOf(empty?[]:Array.from({length:9},(_,i)=>({asset:{id:uid.slice(0,-3)+(201+i),slug:'Synthetic-owned-'+i,kind:'avatar',rarity:'D',media_url:'/api/v1/catalog/assets/'+uid.slice(0,-3)+(201+i)},quantity:1,equipped:i===0}))));
  if(p==='/posts'&&method==='GET')return send(200,pageOf(state.posts.map(post=>({...post,author:state.profile,interactions:interactions()}))));
  if(p==='/posts/'+pid+'/interactions')return send(200,interactions());
  if(p==='/posts/'+pid+'/reactions'){if(!state.viewer)return fail(401,'UNAUTHORIZED');if(state.reaction)state.counts[state.reaction]--;state.reaction=method==='DELETE'?null:body.reaction_type;if(state.reaction)state.counts[state.reaction]++;return send(200,interactions())}
  if(p==='/posts/'+pid+'/comments'&&method==='GET')return send(200,pageOf(state.comments));
  if(p==='/posts/'+pid+'/comments'&&method==='POST'){const row={id:body.request_id,post_id:pid,author:state.profile,body:body.body,created_at:'2026-11-14T05:00:00Z'};state.comments.push(row);return send(201,row)}
  if(p.startsWith('/comments/')&&p.endsWith('/interactions'))return send(200,{comment_id:p.split('/')[2],reaction_counts:Object.fromEntries(Object.keys(countBase).map(k=>[k,0])),viewer_reaction:null});
  if(p==='/posts/'+pid&&method==='PATCH'){Object.assign(state.posts[0],body);return send(200,state.posts[0])}
  if(p==='/posts/'+pid&&method==='DELETE'){state.posts=[];return send(204)}
  if(p==='/contact'){if(state.error)return fail(state.error,'RATE_LIMITED');return send(201,{id:pid,status:'new'})}
  return fail(404,'NOT_FOUND');
 });return state;
}
