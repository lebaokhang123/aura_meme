import React,{useLayoutEffect,useRef,useState,useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {apiMedia} from '../social-api.js';
import {useSocial} from '../SocialContext.jsx';
import {useCopy,useData,ErrorMessage,LoadState,Pagination} from './account-ui.jsx';
import {EditProfile} from './profile-edit.jsx';
import {ActivityHeatmap} from './ActivityHeatmap.jsx';
import {PostCard} from './PostCard.jsx';
import {icon} from './social-ui.jsx';
function inventoryImage(value){try{const url=new URL(value,location.origin);if(/^\/api\/v1\/catalog\/assets\/[0-9a-f-]{36}$/.test(url.pathname))return url.pathname;}catch{}return '/assets/brand/favicon-64.png';}
export function ProfilePage(){
 const t=useCopy(),user=useSyncExternalStore(auth.subscribe,auth.snapshot).user;
 const username=location.pathname.split('/')[2]||user?.username||'',valid=/^[a-z0-9_]{3,32}$/.test(username),mine=user?.username===username;
 const editButton=useRef(null),restoreEditFocus=useRef(false);
 const closeEdit=()=>{restoreEditFocus.current=true;setEditing(false)};
 const [editing,setEditing]=useState(false),[commentPage,setCommentPage]=useState(1);
 useLayoutEffect(()=>{if(!editing&&restoreEditFocus.current){editButton.current?.focus();restoreEditFocus.current=false}},[editing]);
 const {state,posts,pagination,loading,error,retry,loadMore,loadFeed}=useSocial();
 const profile=useData(valid?'/users/'+username:null),comments=useData(valid?'/users/'+username+'/comments?page='+commentPage:null,state.revision),activity=useData(valid?'/users/'+username+'/activity':null,state.revision),inventory=useData(mine?'/inventory/me?page_size=9':null);
 const p=profile.data,items=inventory.data?.items.filter(i=>i.asset.kind==='avatar')||[];
 return <main className="am-profile"><div className="am-profile-layout">{!valid?<p role="alert">{t('Không tìm thấy hồ sơ.','Profile not found.')}</p>:<LoadState state={profile}>{p&&<>
 <aside className="profile-rail am-profile-rail">
 <section className="am-profile-identity"><div className="am-profile-avatar"><div className="am-profile-avatar-glow"/><div className="am-profile-avatar-frame"><img src={apiMedia(p.avatar_url)||'/assets/brand/favicon-64.png'} alt={t('Ảnh đại diện ','Avatar of ')+p.display_name} width="112" height="112"/></div></div>
 <div className="am-profile-name"><h1 translate="no">{p.display_name}</h1><p translate="no">@{p.username}</p></div>
 {mine&&(editing?<EditProfile profile={p} onSaved={values=>{profile.update({...p,...values});closeEdit();loadFeed().catch(()=>{})}} onCancel={closeEdit}/>:<button ref={editButton} className="am-profile-edit" onClick={()=>setEditing(true)}>{icon('edit',16)}{t('Chỉnh sửa hồ sơ','Edit profile')}</button>)}
 <p className="am-profile-bio" translate="no">{p.bio||t('Chưa có tiểu sử.','No bio yet.')}</p>
 <dl className="am-profile-stats"><div><dd>{pagination?.total??'—'}</dd><dt>{t('Bài viết','Posts')}</dt></div><div><dd>{comments.data?.pagination.total??'—'}</dd><dt>{t('Bình luận','Comments')}</dt></div><div><dd>—</dd><dt>Reaction</dt></div></dl>
 <div className="am-profile-progress"><div className="am-profile-badges"><span>LVL —</span><span>{t('Chưa có dữ liệu','No data yet')}</span></div><div className="am-profile-progress-track" aria-hidden="true"/><div className="am-profile-progress-caption"><span>— XP</span><span>{t('Chuỗi: —','Streak: —')}</span></div></div>
 {mine&&<div className="am-profile-account-links"><a href="/vault">{t('Đổi Avatar trong Bảo Khố','Change avatar in Vault')} →</a>{user.roles.includes('ADMIN')&&<a href="/admin/contacts" aria-label={t('Hộp thư quản trị','Admin inbox')}>{t('Hộp thư quản trị','Admin inbox')} →</a>}</div>}</section>
 {mine&&<><section className="am-profile-collection"><h2><a href="/vault">{t('Meme đã sở hữu','Owned memes')}</a></h2><LoadState state={inventory}>{items.length?<div className="am-profile-inventory">{items.map(item=><a href="/vault" key={item.asset.id}><img src={inventoryImage(item.asset.media_url)} alt={item.asset.slug} width="78" height="78"/></a>)}</div>:<p>{t('Chưa có Meme trong bộ sưu tập.','No memes in your collection yet.')}</p>}</LoadState></section>
 <section className="am-profile-collection am-profile-backgrounds"><h2>{t('Background đã sở hữu','Owned backgrounds')}</h2><p>{t('Background đang phát triển.','Backgrounds are in development.')}</p><a className="am-profile-vault-link" href="/vault">{t('Mở Bảo Khố','Open Vault')} →</a></section></>}
 </aside>
 <div className="am-profile-content"><section className="profile-activity am-profile-activity"><header><div><img src="/assets/brand/favicon-64.png" alt="" width="20" height="20"/><h2>{t('Hoạt động trên AuraMeme','Activity on AuraMeme')}</h2></div>{activity.data&&<span className="am-profile-contributions">{activity.data.total} {t('lượt đóng góp','contributions')}</span>}</header><LoadState state={activity}>{activity.data&&<ActivityHeatmap data={activity.data}/>}</LoadState></section>
 <section className="am-profile-feed" aria-label={t('Bài viết công khai','Public posts')}><ErrorMessage error={error?{message:error}:null}/>{error&&<button className="account-button" onClick={()=>retry().catch(()=>{})}>{t('Thử lại','Try again')}</button>}{posts.map(post=><PostCard key={post.id} post={post} variant="profile"/>)}{loading&&<p role="status" aria-busy="true">{t('Đang tải...','Loading...')}</p>}{!loading&&!error&&!posts.length&&<p className="am-profile-empty">{t('Chưa có bài viết công khai.','No public posts yet.')}</p>}{pagination?.page<pagination?.total_pages&&<button className="account-button am-profile-more" disabled={loading} onClick={()=>loadMore().catch(()=>{})}>{t('Xem thêm bài viết','Load more posts')}</button>}</section>
 <section className="am-profile-comments"><h2>{t('Bình luận công khai','Public comments')}</h2><LoadState state={comments}>{comments.data?.items.length?<ul>{comments.data.items.map(comment=><li key={comment.id}><p translate="no">{comment.body}</p><a href={'/#post-'+comment.post_id}>{t('Xem bài viết','View post')} →</a></li>)}</ul>:<p>{t('Chưa có bình luận công khai.','No public comments yet.')}</p>}<Pagination data={comments.data} page={commentPage} onChange={setCommentPage}/></LoadState></section>
 </div></>}</LoadState>}</div></main>;
}
