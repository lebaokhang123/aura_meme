import {BACKGROUND_EFFECTS} from './background-effects.js';
// DTO mapping only; all HTTP/cookies/CSRF use the existing Auth client.

const TYPES=['like','love','laugh','fire','sad','angry'];
const ICONS={gaming:'sports_esports',anime:'movie_filter','cong-nghe':'terminal','truong-hoc':'school',random:'casino'};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const bad=()=>{throw Error('PROTOCOL_ERROR')};
export const apiId=value=>typeof value==='string'&&UUID.test(value)?value:bad();
export function apiMedia(value){if(value===null||value===undefined)return null;if(typeof value!=='string'||!/^\/api\/v1\/(?:media|catalog\/assets)\/[0-9a-f-]{36}$/.test(value))bad();return value;}
export function vaultAsset(value){
 apiId(value?.id);if(typeof value.slug!=='string'||typeof value.display_name!=='string'||!['avatar','background'].includes(value.kind)||!['D','C','B','A','S'].includes(value.rarity))bad();
 const available=value.available!==false;let image=null;
 if(value.media_url!==null&&value.media_url!==undefined){let url;try{url=new URL(value.media_url,'http://vault.local')}catch{bad()};if(url.pathname!=='/api/v1/catalog/assets/'+value.id||url.search||url.hash)bad();image=url.pathname;}
 if(available&&!image)bad();
 if(value.kind==='background'&&available&&!BACKGROUND_EFFECTS.includes(value.effect_key))bad();
 return {...value,available,image};
}
export function apiAuthor(value){
 apiId(value?.id);if(typeof value.username!=='string'||typeof value.display_name!=='string')bad();
 return {author:value.username,authorId:value.id,authorName:value.display_name,handle:'@'+value.username,
 avatar:apiMedia(value.avatar_url)||'/assets/identity/default-avatar.svg',
 level:'Lvl —',nickname:'Đang phát triển'};
}
export function apiCategory(value){
 apiId(value?.id);if(typeof value.slug!=='string'||!/^[-a-z0-9]{1,80}$/.test(value.slug)||typeof value.name!=='string'||(value.post_count!==undefined&&(!Number.isSafeInteger(value.post_count)||value.post_count<0)))bad();
 return {id:value.slug,apiId:value.id,label:value.name,icon:Object.hasOwn(ICONS,value.slug)?ICONS[value.slug]:'tag',count:value.post_count??0};
}
export function apiPost(value){
 apiId(value?.id);if(typeof value.title!=='string'||typeof value.content!=='string'||!Number.isFinite(Date.parse(value.created_at)))bad();
 const category=apiCategory(value.category);
 return {...apiAuthor(value.author),id:value.id,title:value.title,content:value.content,category:category.id,categoryLabel:category.label,
 reactions:Object.values(value.interactions?.reaction_counts||{}),createdAt:Date.parse(value.created_at),ageMinutes:Math.max(0,(Date.now()-Date.parse(value.created_at))/60000),media:apiMedia(value.media_url),interactions:value.interactions,api:true};
}
export function apiComment(value){
 apiId(value?.id);apiId(value?.post_id);if(typeof value.body!=='string'||!Number.isFinite(Date.parse(value.created_at)))bad();
 return {...apiAuthor(value.author),id:value.id,postId:value.post_id,text:value.body,createdAt:Date.parse(value.created_at),api:true};
}
export function apiPage(value){
 const p=value?.pagination;if(!Array.isArray(value?.items)||!p||!['page','page_size','total','total_pages'].every(k=>Number.isSafeInteger(p[k])&&p[k]>=0)||p.page<1||p.page_size<1)bad();
 return value;
}
export function apiInteractions(value,id,target){
 if(value?.[target+'_id']!==apiId(id)||!value.reaction_counts||!TYPES.every(k=>Number.isSafeInteger(value.reaction_counts[k])&&value.reaction_counts[k]>=0)
 ||(value.viewer_reaction!==null&&!TYPES.includes(value.viewer_reaction)))bad();
 if(value.viewer_meme_asset_id!=null)apiId(value.viewer_meme_asset_id);
 if(value.meme_reactions!==undefined){
  if(!Array.isArray(value.meme_reactions))bad();
  const seen=new Set(),reactions=value.meme_reactions.map(row=>{
   const asset=vaultAsset(row?.asset);if(asset.kind!=='avatar'||!asset.available||!Number.isSafeInteger(row.count)||row.count<1||seen.has(asset.id))bad();
   seen.add(asset.id);return {asset,count:row.count};
  });
  if(value.viewer_meme_asset_id!=null&&(!seen.has(value.viewer_meme_asset_id)||value.viewer_reaction!==null))bad();
  return {...value,meme_reactions:reactions};
 }
 if(value.viewer_meme_asset_id!=null)bad();
 return value;
}
export function apiOwnedMemePage(value){
 const page=apiPage(value);
 return {...page,items:page.items.flatMap(row=>{
  apiId(row?.asset?.id);if(!Number.isSafeInteger(row.quantity)||row.quantity<1||typeof row.equipped!=='boolean')bad();
  if(row.asset.kind!=='avatar')return [];
  const asset=vaultAsset(row.asset);return asset.available?[{...row,asset}]:[];
 })};
}
export function reactionMutation(action,current={}){
 if(!['post','comment'].includes(action.target)||!['meme',...TYPES].includes(action.reaction))bad();
 const path='/'+(action.target==='post'?'posts':'comments')+'/'+apiId(action.id)+'/reactions';
 const meme=action.reaction==='meme',asset=meme?apiId(action.memeAssetId):null;
 const selected=meme?current.viewer_meme_asset_id===asset:current.viewer_reaction===action.reaction;
 return {method:selected?'DELETE':'PUT',path,body:selected?undefined:{reaction_type:action.reaction,...(meme?{meme_asset_id:asset}:{})}};
}
