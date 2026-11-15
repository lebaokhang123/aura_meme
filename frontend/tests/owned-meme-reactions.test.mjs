import test from 'node:test';
import assert from 'node:assert/strict';
import {apiInteractions,apiOwnedMemePage,reactionMutation} from '../src/social-api.js';

const id='00000000-0000-4000-8000-000000000001',assetId='00000000-0000-4000-8000-000000000002';
const asset={id:assetId,slug:'synthetic-meme',display_name:'Mèo thử',kind:'avatar',rarity:'D',available:true,media_url:'/api/v1/catalog/assets/'+assetId,effect_key:null};
const counts={like:0,love:0,laugh:0,fire:0,sad:0,angry:0};
const state={post_id:id,reaction_counts:counts,viewer_reaction:null,viewer_meme_asset_id:assetId,meme_reactions:[{asset,count:2}]};

test('Meme aggregates validate real catalog avatars and selection without replacing six counts',()=>{
 const value=apiInteractions(state,id,'post');
 assert.equal(value.meme_reactions[0].asset.image,asset.media_url);
 assert.deepEqual(value.reaction_counts,counts);
 for(const bad of [
  {...state,viewer_meme_asset_id:'bad'},
  {...state,meme_reactions:[{asset:{...asset,kind:'background'},count:2}]},
  {...state,meme_reactions:[{asset,count:-1}]},
  {...state,meme_reactions:[{asset:{...asset,media_url:'https://evil.example/image.png'},count:1}]},
  {...state,meme_reactions:[{asset,count:1},{asset,count:1}]},
 ])assert.throws(()=>apiInteractions(bad,id,'post'),/PROTOCOL_ERROR/);
});

test('owned picker reads paginated owned avatar inventory and never fabricates ownership',()=>{
 const page={items:[{asset,quantity:3,equipped:false},{asset:{...asset,kind:'background',effect_key:'deep-sea'},quantity:2,equipped:false}],pagination:{page:1,page_size:20,total:2,total_pages:1}};
 assert.deepEqual(apiOwnedMemePage(page).items.map(row=>[row.asset.id,row.quantity]),[[assetId,3]]);
 assert.throws(()=>apiOwnedMemePage({...page,items:[{asset,quantity:0,equipped:false}]}),/PROTOCOL_ERROR/);
 assert.throws(()=>apiOwnedMemePage({...page,items:[{asset,quantity:1,equipped:'yes'}]}),/PROTOCOL_ERROR/);
});

test('Meme toggle uses existing PUT/DELETE API; standard replaces Meme without inventory writes',()=>{
 const action={target:'post',id,reaction:'meme',memeAssetId:assetId};
 assert.deepEqual(reactionMutation(action,{}),{method:'PUT',path:'/posts/'+id+'/reactions',body:{reaction_type:'meme',meme_asset_id:assetId}});
 assert.equal(reactionMutation(action,state).method,'DELETE');
 assert.deepEqual(reactionMutation({...action,reaction:'love'},state).body,{reaction_type:'love'});
 assert.equal(reactionMutation({...action,target:'comment'},state).path,'/comments/'+id+'/reactions');
 assert.throws(()=>reactionMutation({...action,memeAssetId:'bad'},{}),/PROTOCOL_ERROR/);
 assert.throws(()=>reactionMutation({...action,target:'user'},{}),/PROTOCOL_ERROR/);
});
