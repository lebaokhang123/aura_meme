import { POSTS, CATEGORIES } from './feed-data.js';
import { DEMO_USERS } from './demo.js';
import baseline from './social-baseline.json' with { type:'json' };

export const REACTIONS = [
  {id:'like',emoji:'👍',label:'Thích'},{id:'love',emoji:'❤️',label:'Yêu'},
  {id:'laugh',emoji:'😂',label:'Cười'},{id:'fire',emoji:'🔥',label:'Cháy'},
  {id:'sad',emoji:'😢',label:'Khóc'},{id:'angry',emoji:'😡',label:'Tức'},
];
export const MAX_POST_TEXT=5000, MAX_COMMENT_TEXT=2000;
const userExists = user => DEMO_USERS.some(account=>account.username===user);
export function emptyState(now=Date.now()) {
  return {version:1,revision:0,referenceTime:now,posts:[],postReactions:{},commentReactions:{},comments:[],deletedComments:[],bookmarks:{},deletedPosts:[]};
}
export function validateState(state) {
  if(!state||state.version!==1||!Number.isSafeInteger(state.revision)||state.revision<0||!Number.isFinite(state.referenceTime)||
    !['posts','comments','deletedComments'].every(k=>Array.isArray(state[k]))||!['postReactions','commentReactions','bookmarks'].every(k=>state[k]&&typeof state[k]==='object'&&!Array.isArray(state[k])))throw Error('INVALID_SAVED_DATA');
  if(state.deletedPosts!==undefined&&(!Array.isArray(state.deletedPosts)||state.deletedPosts.some(id=>typeof id!=='string')))throw Error('INVALID_SAVED_DATA');
  if(state.posts.some(p=>!p||!/^p-[\w-]{1,80}$/.test(p.id)||!userExists(p.author)||typeof p.content!=='string'||p.content.length>MAX_POST_TEXT||!CATEGORIES.some(c=>c.id===p.category)||!Number.isFinite(p.createdAt)))throw Error('INVALID_SAVED_DATA');
  if(state.comments.some(c=>!c||!/^c-[\w-]{1,80}$/.test(c.id)||!userExists(c.author)||typeof c.text!=='string'||!c.text.trim()||c.text.length>MAX_COMMENT_TEXT||!Number.isFinite(c.createdAt)))throw Error('INVALID_SAVED_DATA');
  for(const records of [state.postReactions,state.commentReactions])for(const map of Object.values(records))if(!map||typeof map!=='object'||Object.entries(map).some(([user,reaction])=>!userExists(user)||!REACTIONS.some(r=>r.id===reaction)))throw Error('INVALID_SAVED_DATA');
  return state;
}
const postAuthor=post=>post.author||({khang:'Khang_dev',kien:'Kien_dev',gigachad:'Gigachad'}[post.id]);
export function repairDemoComments(state) {
  if(state.khangCommentRepairV1)return state;
  const ids=new Set(baseline.comments.filter(c=>c.author==='Khang_dev').map(c=>c.id));
  const deletedComments=state.deletedComments.filter(id=>!ids.has(id));
  return {...state,deletedComments,khangCommentRepairV1:true,revision:state.revision+(deletedComments.length!==state.deletedComments.length?1:0)};
}
export function commentsFor(state,postId) {
  return [...baseline.comments,...state.comments].filter(comment=>comment.postId===postId&&!state.deletedComments.includes(comment.id));
}
export function reactionCounts(state,target,id) {
  const original=target==='post'?(baseline.reactions[id]||[]):(baseline.comments.find(c=>c.id===id)?.reactions||[]);
  const counts=[];
  for(const row of original){const r=row.emoji==='💀'?{...REACTIONS.find(r=>r.id==='laugh'),count:row.count}:row;const existing=counts.find(c=>c.id===r.id);if(existing)existing.count+=r.count;else counts.push({...r});}
  for(const reaction of Object.values((target==='post'?state.postReactions:state.commentReactions)[id]||{})) {
    const option=REACTIONS.find(r=>r.id===reaction);if(!option)continue;
    const entry=counts.find(r=>r.id===reaction);
    if(entry)entry.count++;else counts.push({...option,count:1});
  }
  return counts.filter(r=>r.count>0);
}
export function allPosts(state,media={},now=Date.now()) {
  const elapsed=Math.max(0,(now-state.referenceTime)/60000);
  const originals=POSTS.map(post=>({...post,ageMinutes:post.ageMinutes+elapsed,reactions:reactionCounts(state,'post',post.id).map(r=>r.count)}));
  const created=state.posts.map(post=>{
    const author=DEMO_USERS.find(user=>user.username===post.author);
    const profile=POSTS.find(p=>p.id===({Khang_dev:'khang',Kien_dev:'kien',Gigachad:'gigachad'}[post.author]));
    return {...post,title:'',authorName:author.displayName,handle:profile.handle,avatar:author.avatar,level:profile.level,nickname:profile.nickname,
      media:post.mediaId?media[post.mediaId]||null:null,ageMinutes:Math.max(0,(now-post.createdAt)/60000),reactions:reactionCounts(state,'post',post.id).map(r=>r.count)};
  });
  return [...originals,...created].filter(post=>!(state.deletedPosts||[]).includes(post.id));
}
export function reduceSocial(state,action,user,now=Date.now()) {
  if(!userExists(user))throw Error('LOGIN_REQUIRED');
  validateState(state);
  const next=structuredClone(state);
  const posts=new Set(allPosts(state).map(p=>p.id));
  if(action.type==='react') {
    if(!REACTIONS.some(r=>r.id===action.reaction))throw Error('INVALID_REACTION');
    if(action.target!=='post'&&action.target!=='comment')throw Error('INVALID_TARGET');
    const exists=action.target==='post'?posts.has(action.id):[...baseline.comments,...state.comments].some(c=>c.id===action.id&&!state.deletedComments.includes(c.id));
    if(!exists||(action.target==='comment'&&![...baseline.comments,...state.comments].some(c=>c.id===action.id&&posts.has(c.postId))))throw Error('NOT_FOUND');
    const records=action.target==='post'?next.postReactions:next.commentReactions;
    const map=records[action.id]||{};
    if(map[user]===action.reaction)delete map[user];else map[user]=action.reaction;
    records[action.id]=map;
  } else if(action.type==='delete-post') {
    const post=allPosts(state).find(p=>p.id===action.id);
    if(!post)throw Error('NOT_FOUND');
    if(postAuthor(post)!==user)throw Error('NOT_OWNER');
    next.deletedPosts=[...(next.deletedPosts||[]),action.id];
  } else if(action.type==='comment') {
    if(!posts.has(action.postId))throw Error('NOT_FOUND');
    const text=typeof action.text==='string'?action.text.trim():'';
    if(!text||text.length>MAX_COMMENT_TEXT)throw Error('INVALID_COMMENT');
    if(!/^c-[\w-]{1,80}$/.test(action.id)||[...baseline.comments,...state.comments].some(c=>c.id===action.id))throw Error('INVALID_ID');
    next.comments.push({id:action.id,postId:action.postId,author:user,text,createdAt:now});
  } else if(action.type==='delete-comment') {
    const comment=[...baseline.comments,...state.comments].find(c=>c.id===action.id&&!next.deletedComments.includes(c.id));
    if(!comment)throw Error('NOT_FOUND');
    if(comment.author!==user)throw Error('NOT_OWNER');
    next.deletedComments.push(action.id);
  } else if(action.type==='create-post') {
    const content=typeof action.content==='string'?action.content.trim():'';
    if((!content&&!action.mediaId)||content.length>MAX_POST_TEXT)throw Error('INVALID_POST');
    if(!CATEGORIES.some(c=>c.id===action.category))throw Error('INVALID_CATEGORY');
    if(!/^p-[\w-]{1,80}$/.test(action.id)||[...POSTS,...state.posts].some(p=>p.id===action.id)||action.mediaId&&action.mediaId!==action.id)throw Error('INVALID_ID');
    next.posts.push({id:action.id,author:user,content,category:action.category,createdAt:now,mediaId:action.mediaId||null,mediaType:action.mediaType||null});
  } else throw Error('INVALID_ACTION');
  next.revision++;return next;
}
