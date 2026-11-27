import {apiId,apiPage,apiMedia} from './social-api.js';
const bad=()=>{throw Error('PROTOCOL_ERROR')};
const text=(v,max=20000)=>typeof v==='string'&&v.length<=max&&!v.includes('\0')?v:bad();
const one=(v,choices)=>choices.includes(v)?v:bad();
const date=v=>typeof v==='string'&&Number.isFinite(Date.parse(v))?v:bad();
export const canAdmin=user=>Array.isArray(user?.roles)&&user.roles.includes('ADMIN');
export function adminPage(value,resource){
 const page=apiPage(value);
 const items=page.items.map(row=>{
  const id=apiId(row?.id);
  if(resource==='users'){if(!Array.isArray(row.roles)||row.roles.some(r=>!['ADMIN','USER'].includes(r)))bad();return {id,username:text(row.username,32),...(typeof row.email==='string'&&row.email.trim()?{email:text(row.email.trim(),254)}:{}),display_name:text(row.display_name,80),status:one(row.status,['active','locked','deleted']),roles:[...row.roles],...(row.deleted_at?{deleted_at:date(row.deleted_at)}:{})};}
  if(resource==='categories')return {id,name:text(row.name,80),slug:text(row.slug,80),status:one(row.status,['active','hidden'])};
  if(resource==='posts'||resource==='comments'){
   const author={username:text(row.author?.username,32),display_name:text(row.author?.display_name,80)};
   return {id,author,created_at:date(row.created_at),status:one(row.status,resource==='posts'?['draft','published','hidden','deleted']:['visible','hidden','deleted']),...(resource==='posts'?{title:text(row.title,160),content:text(row.content),media_url:apiMedia(row.media_url)}:{body:text(row.body,4000),post_id:apiId(row.post_id)})};
  }
  if(resource==='contacts')return {id,name:text(row.name,100),subject:text(row.subject,160),body:text(row.body,4000),status:one(row.status,['new','in_review','resolved']),created_at:date(row.created_at)};
  if(resource==='assets'){if(typeof row.active!=='boolean')bad();return {id,slug:text(row.slug,100),...(row.display_name?{display_name:text(row.display_name,100)}:{}),...(row.effect_key?{effect_key:text(row.effect_key,60)}:{}),kind:one(row.kind,['avatar','frame','icon','effect','background']),rarity:one(row.rarity,['D','C','B','A','S']),active:row.active,review_status:one(row.review_status,['pending','approved','rejected','unknown'])};}
  if(resource==='audit-logs')return {id,actor_id:apiId(row.actor_id),action:text(row.action,100),target_type:text(row.target_type,100),target_id:text(row.target_id,200),created_at:date(row.created_at)};
  if(resource==='orders')return {id,owner_username:row.owner_username?text(row.owner_username,100):null,completed_at:row.completed_at?date(row.completed_at):null,amount_usd_cents:row.amount_usd_cents??null,currency:row.currency||'USD',order_code:text(row.order_code,100),tier:one(row.tier,['plus','prime']),provider:text(row.provider,50),amount_vnd:typeof row.amount_vnd==='number'?row.amount_vnd:0,amount_vnd_formatted:row.amount_vnd_formatted?text(row.amount_vnd_formatted,50):'',status:one(row.status,['pending','success','failed','cancelled','expired']),provider_txn_id:row.provider_txn_id?text(row.provider_txn_id,100):null,created_at:date(row.created_at)};
  if(resource==='announcements')return {id,title:text(row.title,160),body:text(row.body,4000),status:one(row.status,['draft','published','withdrawn']),actor_id:apiId(row.actor_id),actor_username:row.actor_username?text(row.actor_username,32):null,recipients_count:typeof row.recipients_count==='number'?row.recipients_count:0,created_at:date(row.created_at),published_at:row.published_at?date(row.published_at):null};
  bad();
 });
 return {items,pagination:{...page.pagination}};
}
