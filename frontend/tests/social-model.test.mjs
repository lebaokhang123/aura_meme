import {test} from 'node:test';
import assert from 'node:assert/strict';
import {emptyState,reduceSocial,reactionCounts,allPosts,REACTIONS,repairDemoComments,commentsFor} from '../src/social-model.js';
test('comment removal preserves recoverable content and Khang demo repair runs only once',()=>{
 let state=emptyState();state.deletedComments=['sample-kien-1','sample-khang-0'];
 state=repairDemoComments(state);
 assert.equal(state.deletedComments.includes('sample-kien-1'),false);
 assert.equal(state.deletedComments.includes('sample-khang-0'),true);
 assert.equal(['khang','kien'].flatMap(id=>commentsFor(state,id)).filter(c=>c.author==='Khang_dev').length,2);
 state=reduceSocial(state,{type:'comment',id:'c-archive',postId:'khang',text:'keep exact text'},'Khang_dev');
 state=reduceSocial(state,{type:'delete-comment',id:'c-archive'},'Khang_dev');
 assert.equal(state.comments.find(c=>c.id==='c-archive').text,'keep exact text');
 assert.equal(commentsFor(state,'khang').some(c=>c.id==='c-archive'),false);
 state=reduceSocial(state,{type:'delete-comment',id:'sample-kien-1'},'Khang_dev');
 assert.equal(repairDemoComments(state).deletedComments.includes('sample-kien-1'),true);
});

test('post deletion is owner-only, persistent and preserves source plus saved legacy data',()=>{
 const original=emptyState(1000);original.bookmarks.Kien_dev=['khang'];
 assert.throws(()=>reduceSocial(original,{type:'delete-post',id:'khang'},'Kien_dev'),/NOT_OWNER/);
 const state=reduceSocial(original,{type:'delete-post',id:'khang'},'Khang_dev');
 assert.equal(allPosts(state).length,2);assert.equal(allPosts(original).length,3);
 assert.deepEqual(state.bookmarks.Kien_dev,['khang']);
 assert.throws(()=>reduceSocial(state,{type:'comment',postId:'khang',id:'c-gone',text:'no'},'Khang_dev'),/NOT_FOUND/);
 assert.equal(allPosts(JSON.parse(JSON.stringify(state))).some(p=>p.id==='khang'),false);
});
test('legacy skull reaction is replaced with a standard type without changing its count',()=>{
 const rows=reactionCounts(emptyState(),'comment','sample-khang-0');
 assert.equal(rows.some(r=>r.emoji==='💀'),false);
 assert.equal(rows.find(r=>r.id==='laugh').count,19);
});
test('immutable baseline and one reaction per user: toggle, replace, isolation and no negative counts',()=>{
 const original=emptyState(1000), act=(s,user,reaction)=>reduceSocial(s,{type:'react',target:'post',id:'khang',reaction},user,2000);
 assert.equal(REACTIONS.length,6);
 assert.equal(reactionCounts(original,'post','khang').reduce((s,r)=>s+r.count,0),732);
 let state=act(original,'Khang_dev','love');
 assert.equal(reactionCounts(state,'post','khang').reduce((s,r)=>s+r.count,0),733);
 state=act(state,'Kien_dev','fire');state=act(state,'Khang_dev','like');
 assert.equal(state.postReactions.khang.Kien_dev,'fire');assert.equal(state.postReactions.khang.Khang_dev,'like');
 assert.equal(reactionCounts(state,'post','khang').reduce((s,r)=>s+r.count,0),734);
 state=act(state,'Khang_dev','like');assert.equal(state.postReactions.khang.Khang_dev,undefined);
 assert.equal(reactionCounts(original,'post','khang').reduce((s,r)=>s+r.count,0),732);
 assert.throws(()=>act(original,null,'like'),/LOGIN_REQUIRED/);
 assert.throws(()=>act(original,'Khang_dev','unowned-meme'),/INVALID_REACTION/);
});
test('new posts keep their author/time and include reactions without changing baseline',()=>{
 let state=emptyState(1000);
 state=reduceSocial(state,{type:'create-post',id:'p-test',content:'sample text',category:'Gaming'},'Kien_dev',2000);
 const posts=allPosts(state,{},2500),post=posts.find(p=>p.id==='p-test');
 assert.equal(post.authorName,'Kien Dev');assert.equal(post.createdAt,2000);assert.equal(post.level,'Lvl 36');assert.equal(post.media,null);
 assert.equal(post.reactions.length,0);assert.equal(posts.find(p=>p.id==='khang').reactions.reduce((s,n)=>s+n,0),732);
 assert.throws(()=>reduceSocial(state,{type:'create-post',id:'p-bad',content:'',category:'Gaming'},'Khang_dev'),/INVALID_POST/);
 assert.throws(()=>reduceSocial(state,{type:'create-post',id:'p-bad',content:'text',category:'invalid'},'Khang_dev'),/INVALID_CATEGORY/);
});
test('comments use independent reactions, enforce author deletion, and deletion preserves unrelated state',()=>{
 let state=emptyState(1000);
 state=reduceSocial(state,{type:'comment',id:'c-test',postId:'khang',text:'<img src=x onerror=alert(1)>'},'Khang_dev',2000);
 assert.equal(state.comments[0].text,'<img src=x onerror=alert(1)>');
 state=reduceSocial(state,{type:'react',target:'comment',id:'c-test',reaction:'love'},'Kien_dev',2100);
 assert.equal(reactionCounts(state,'comment','c-test')[0].count,1);
 assert.equal(reactionCounts(state,'post','khang').reduce((sum,r)=>sum+r.count,0),732);
 assert.throws(()=>reduceSocial(state,{type:'delete-comment',id:'c-test'},'Kien_dev'),/NOT_OWNER/);
 state=reduceSocial(state,{type:'delete-comment',id:'c-test'},'Khang_dev');
 assert.equal(commentsFor(state,'khang').some(c=>c.id==='c-test'),false);assert.equal(state.comments[0].text,'<img src=x onerror=alert(1)>');
});
