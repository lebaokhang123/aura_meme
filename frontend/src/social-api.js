// DTO mapping only; all HTTP/cookies/CSRF use the existing Auth client.

const TYPES=['like','love','laugh','fire','sad','angry'];
const ICONS={gaming:'sports_esports',anime:'movie_filter','cong-nghe':'terminal','truong-hoc':'school',random:'casino'};
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const bad=()=>{throw Error('PROTOCOL_ERROR')};
export const apiId=value=>typeof value==='string'&&UUID.test(value)?value:bad();
export function apiMedia(value){if(value===null||value===undefined)return null;if(typeof value!=='string'||!/^\/api\/v1\/(?:media|catalog\/assets)\/[0-9a-f-]{36}$/.test(value))bad();return value;}
export function apiAuthor(value){
 apiId(value?.id);if(typeof value.username!=='string'||typeof value.display_name!=='string')bad();
 return {author:value.username,authorId:value.id,authorName:value.display_name,handle:'@'+value.username,
 avatar:apiMedia(value.avatar_url)||'/assets/brand/favicon-64.png',
 level:'Lvl —',nickname:'Đang phát triển'};
}
export function apiCategory(value){
 apiId(value?.id);if(typeof value.slug!=='string'||!/^[-a-z0-9]{1,80}$/.test(value.slug)||typeof value.name!=='string'||(value.post_count!==undefined&&(!Number.isSafeInteger(value.post_count)||value.post_count<0)))bad();
 return {id:value.slug,apiId:value.id,label:value.name,icon:Object.hasOwn(ICONS,value.slug)?ICONS[value.slug]:'tag',count:value.post_count??0};
}
export function apiPost(value){
 apiId(value?.id);if(typeof value.title!=='string'||typeof value.content!=='string'||!Number.isFinite(Date.parse(value.created_at)))bad();
 return {...apiAuthor(value.author),id:value.id,title:value.title,content:value.content,category:apiCategory(value.category).id,
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
 return value;
}
