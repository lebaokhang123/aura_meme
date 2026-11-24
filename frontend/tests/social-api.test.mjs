import test from 'node:test';
import assert from 'node:assert/strict';
import {apiAuthor,apiPost,apiComment,apiPage,apiInteractions,apiCategory} from '../src/social-api.js';
import {readFilters} from '../src/feed-data.js';
const id='123e4567-e89b-42d3-a456-426614174000';
const author={id,username:'new_author',display_name:'New Author',avatar_url:null};
test('API DTO uses real author and media, never demo identity/level',()=>{
 const post=apiPost({id,author,category:{id,slug:'new-topic',name:'New topic'},title:'Hi',content:'Text',created_at:'2026-11-13T00:00:00Z',media_url:'/api/v1/media/'+id});
 assert.equal(post.authorId,id);assert.equal(post.authorName,'New Author');assert.equal(post.level,'');assert.equal(post.nickname,'');assert.equal(post.category,'new-topic');assert.equal(post.categoryLabel,'New topic');
 assert.equal(apiAuthor(author).avatar,'/assets/identity/default-avatar.svg');
 assert.equal(apiAuthor({...author,avatar_url:'/api/v1/catalog/assets/'+id}).avatar,'/api/v1/catalog/assets/'+id);
 assert.throws(()=>apiPost({id,author,category:{id,slug:'new-topic',name:'New'},title:'Hi',content:'x',created_at:'bad'}));
 assert.throws(()=>apiAuthor({...author,avatar_url:'https://evil.example/x.png'}));
});
test('API pagination/counts reject malformed data and URL filters retain new database categories',()=>{
 assert.equal(apiCategory({id,slug:'gaming',name:'Gaming',post_count:2}).count,2);
 assert.equal(apiCategory({id,slug:'constructor',name:'Custom',post_count:0}).icon,'tag');
 assert.throws(()=>apiCategory({id,slug:'gaming',name:'Gaming',post_count:-1}));
 assert.throws(()=>apiPage({items:[],pagination:{page:1,page_size:20,total:-1,total_pages:0}}));
 const value={post_id:id,reaction_counts:{like:1,love:0,laugh:0,fire:0,sad:0,angry:0},viewer_reaction:'like'};
 assert.equal(apiInteractions(value,id,'post'),value);
 assert.throws(()=>apiInteractions({...value,viewer_reaction:'custom'},id,'post'));
 assert.equal(readFilters('?category=new-topic&sort=hot',true).category,'new-topic');
});

test('WebP dimensions are checked before decode and API limits do not weaken mock validation',async()=>{
 const {checkImageBytes}=await import('../src/social-files.js');
 const bytes=new Uint8Array(30),v=new DataView(bytes.buffer);
 bytes.set([...Buffer.from('RIFF')],0);v.setUint32(4,22,true);bytes.set([...Buffer.from('WEBPVP8X')],8);v.setUint32(16,10,true);
 bytes[24]=23;bytes[27]=23;
 assert.deepEqual(checkImageBytes(bytes,'image/webp',30,true),{width:24,height:24});
 assert.throws(()=>checkImageBytes(bytes,'image/webp',30),{message:'FILE_TYPE'});
 bytes[24]=255;bytes[25]=31;bytes[27]=255;bytes[28]=31;
 assert.throws(()=>checkImageBytes(bytes,'image/webp',30,true),{message:'FILE_DIMENSIONS'});
});

test('MVP honorifics trust backend title only and never fabricate from username or Admin role',()=>{
 assert.equal(apiAuthor({...author,username:'khang_dev'}).nickname,'');
 assert.equal(apiAuthor({...author,username:'kien_dev'}).nickname,'');
 assert.equal(apiAuthor({...author,roles:['ADMIN']}).nickname,'');
 assert.equal(apiAuthor({...author,level:11,realm:'Trúc Cơ'}).level,'LVL 11');
 assert.equal(apiAuthor({...author,level:11,realm:'Trúc Cơ'}).realm,'Trúc Cơ');
 assert.equal(apiAuthor({...author,level:11,realm:'Trúc Cơ'}).nickname,'Trúc Cơ');
 assert.equal(apiAuthor({...author,level:11,realm:'Trúc Cơ',title:'Sáng Thế Thần',username:'khang_dev'}).nickname,'Sáng Thế Thần');
 for(const level of [undefined,0,101,1.5,'99']){
  assert.equal(apiAuthor({...author,level,realm:'Trúc Cơ',title:'Sáng Thế Thần'}).level,'');
  assert.equal(apiAuthor({...author,level,realm:'Trúc Cơ',title:'Sáng Thế Thần'}).realm,'');
  assert.equal(apiAuthor({...author,level,realm:'Trúc Cơ',title:'Sáng Thế Thần'}).nickname,'');
 }
 const postWithLevel=apiPost({id,author:{...author,username:'khang_dev',level:12,realm:'Trúc Cơ',title:'Sáng Thế Thần'},category:{id,slug:'gaming',name:'Gaming'},title:'Hi',content:'Text',created_at:'2026-11-13T00:00:00Z',media_url:null});
 assert.equal(postWithLevel.level,'LVL 12');assert.equal(postWithLevel.realm,'Trúc Cơ');assert.equal(postWithLevel.nickname,'Sáng Thế Thần');
 const commentWithLevel=apiComment({id,post_id:id,author:{...author,username:'kien_dev',level:7,realm:'Luyện Khí',title:'Sáng Thế Thần'},body:'Hi',created_at:'2026-11-13T00:00:00Z'});
 assert.equal(commentWithLevel.level,'LVL 7');assert.equal(commentWithLevel.realm,'Luyện Khí');assert.equal(commentWithLevel.nickname,'Sáng Thế Thần');
 const normalUserComment=apiComment({id,post_id:id,author:{...author,username:'alice',level:1,realm:'Luyện Khí',title:'Luyện Khí'},body:'Hi',created_at:'2026-11-13T00:00:00Z'});
 assert.equal(normalUserComment.level,'LVL 1');assert.equal(normalUserComment.realm,'Luyện Khí');assert.equal(normalUserComment.nickname,'Luyện Khí');
});
