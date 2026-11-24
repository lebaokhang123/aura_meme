import {AuraProgress} from './AuraProgress.jsx';
import React,{useLayoutEffect,useRef,useState,useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {usePremium} from '../PremiumContext.jsx';
import {apiMedia} from '../social-api.js';
import {useSocial} from '../SocialContext.jsx';
import {useCopy,useData,ErrorMessage,LoadState} from './account-ui.jsx';
import {EditProfile} from './profile-edit.jsx';
import {ActivityHeatmap} from './ActivityHeatmap.jsx';
import {PostCard} from './PostCard.jsx';
import {TitleBadge} from './RealmBadges.jsx';
import {icon} from './social-ui.jsx';
function inventoryImage(value){try{const url=new URL(value,location.origin);if(/^\/api\/v1\/catalog\/assets\/[0-9a-f-]{36}$/.test(url.pathname))return url.pathname;}catch{}return '/assets/brand/favicon-64.png';}
const RARITY_PRIORITY={S:5,A:4,B:3,C:2,D:1};
function topOwned(items){return [...items].sort((a,b)=>(RARITY_PRIORITY[b.asset.rarity]||0)-(RARITY_PRIORITY[a.asset.rarity]||0)||a.asset.slug.localeCompare(b.asset.slug)).slice(0,9);}
function BackgroundMini({asset}){return <div className="am-profile-background-mini" data-effect={asset.effect_key||'violet-base'}>{asset.media_url?<img src={inventoryImage(asset.media_url)} alt=""/>:<span aria-hidden="true"/>}</div>}
export function ProfilePage(){
 const t=useCopy(),user=useSyncExternalStore(auth.subscribe,auth.snapshot).user;
 const pathParts=location.pathname.split('/');
 const routeUser=(pathParts[1]==='profile'||pathParts[1]==='u')?(pathParts[2]||''):'';
 const username=routeUser||user?.username||'',valid=/^[a-z0-9_]{3,32}$/.test(username),mine=Boolean(user?.username&&user.username===username);
 const editButton=useRef(null),restoreEditFocus=useRef(false);
 const closeEdit=()=>{restoreEditFocus.current=true;setEditing(false)};
 const [editing,setEditing]=useState(false);
 const [followBusy,setFollowBusy]=useState(false);
 const handleFollowToggle=async()=>{
  if(!user){location.assign('/login?redirect='+encodeURIComponent(location.pathname));return;}
  if(followBusy||!p)return;
  setFollowBusy(true);
  try{
   const isFollowing=Boolean(p.is_following);
   const method=isFollowing?'DELETE':'POST';
   const res=await auth.write(method,`/users/${username}/follow`);
   profile.update({...p,is_following:res.is_following,follower_count:res.follower_count});
  }catch(err){console.error('Follow toggle failed',err);}
  finally{setFollowBusy(false);}
 };
 useLayoutEffect(()=>{if(!editing&&restoreEditFocus.current){editButton.current?.focus();restoreEditFocus.current=false}},[editing]);
 const {state,posts,pagination,loading,error,retry,loadMore,loadFeed}=useSocial();
 const profile=useData(valid?'/users/'+username:null),comments=useData(valid?'/users/'+username+'/comments?page=1&page_size=1':null,state.revision),activity=useData(valid?'/users/'+username+'/activity':null,state.revision),memeInventory=useData(valid?(mine?'/inventory/me?kind=avatar&page_size=9':'/users/'+username+'/inventory?kind=avatar&page_size=9'):null),backgroundInventory=useData(valid?(mine?'/inventory/me?kind=background&page_size=9':'/users/'+username+'/inventory?kind=background&page_size=9'):null);
 const { subscription } = usePremium();
 const p=profile.data,memeItems=topOwned(memeInventory.data?.items||[]),backgroundItems=topOwned(backgroundInventory.data?.items||[]);
 const profileTier = (mine && subscription?.is_active) ? (subscription.tier || 'free') : (p?.membership_tier || 'free');
 const isProfilePrime = profileTier === 'prime';
 const isProfilePlus = profileTier === 'plus';
 const hasProfileAura = isProfilePrime || isProfilePlus;
 const KHANG_DEV_ID = 'abcfa9f6-c9d2-4181-9b4b-118a4bb6c647';
 const KIEN_DEV_ID = 'c44f393b-4314-4f83-9b2e-9d1fe73ef64c';
 const isKhangDev = String(p?.id || '').toLowerCase() === KHANG_DEV_ID;
 const isKienDev = String(p?.id || '').toLowerCase() === KIEN_DEV_ID;
 const hasAuraMemeSeal = isKhangDev || isKienDev;
 React.useEffect(()=>{
  if(!valid||profile.busy||profile.error)return;
  const targetEffect=p?.equipped_background_effect||null;
  window.dispatchEvent(new CustomEvent('aurameme-profile-background-override',{detail:{active:true,effect:targetEffect,username}}));
  return()=>{
   window.dispatchEvent(new CustomEvent('aurameme-profile-background-override',{detail:{active:false,effect:null}}));
  };
 },[valid,profile.busy,profile.error,p?.equipped_background_effect,username]);
 return <main className="am-profile"><div className="am-profile-layout">{!valid?<p role="alert">{t('Không tìm thấy hồ sơ.','Profile not found.')}</p>:<LoadState state={profile}>{p&&<>
 <aside className="profile-rail am-profile-rail">
 <section className={`am-profile-identity ${isKhangDev ? 'am-profile-identity--celestial' : ''}`}>
 {isKhangDev && (
  <div className="am-celestial-canvas" aria-hidden="true">
   <div className="am-celestial-smoke" />
   <div className="am-celestial-sparkles">
    <span className="am-sparkle am-sparkle-1" />
    <span className="am-sparkle am-sparkle-2" />
    <span className="am-sparkle am-sparkle-3" />
    <span className="am-sparkle am-sparkle-4" />
    <span className="am-sparkle am-sparkle-5" />
   </div>
  </div>
 )}
 <div className={`am-profile-avatar ${hasProfileAura ? (isProfilePrime ? 'has-aura-prime' : 'has-aura-plus') : ''}`}><div className="am-profile-avatar-glow"/><div className="am-profile-avatar-frame"><img className={`${isProfilePrime ? 'aura-avatar--prime' : isProfilePlus ? 'aura-avatar--plus' : ''}`} src={apiMedia(p.avatar_url)||'/assets/identity/default-avatar.svg'} alt={t('Ảnh đại diện ','Avatar of ')+p.display_name} width="112" height="112"/></div>{hasProfileAura && <span className={`aura-member-badge ${isProfilePrime ? 'aura-member-badge--prime' : 'aura-member-badge--plus'} w-6 h-6 bottom-[6px] right-[6px]`} title={isProfilePrime ? t('Hội viên Aura Prime', 'Aura Prime Member') : t('Hội viên Aura Plus', 'Aura Plus Member')}><svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg></span>}</div>
 <div className="am-profile-name"><h1 translate="no"><span>{p.display_name}</span>{hasAuraMemeSeal && <img src="/assets/brand/favicon-64.png" alt="" width="18" height="18" className="am-profile-aurameme-seal" title={t('Dấu ấn AuraMeme', 'AuraMeme Seal')} aria-label={t('Dấu ấn AuraMeme', 'AuraMeme Seal')} />}</h1><p translate="no">@{p.username}</p>{p.level&&p.title&&<div className="mt-1.5 flex justify-center"><TitleBadge level={p.level} realm={p.realm} title={p.title} size="lg"/></div>}{hasProfileAura && <div className="mt-2 flex justify-center"><div className={`profile-premium-badge profile-premium-badge--${profileTier}`} title={isProfilePrime ? t('Hội viên Aura Prime', 'Aura Prime Member') : t('Hội viên Aura Plus', 'Aura Plus Member')}><span className="material-symbols-outlined profile-premium-badge-icon" aria-hidden="true">{isProfilePrime ? 'diamond' : 'workspace_premium'}</span><span className="profile-premium-badge-text">{isProfilePrime ? 'Aura Prime' : 'Aura Plus'}</span></div></div>}</div>
 {mine&&(editing?<EditProfile profile={p} onSaved={values=>{profile.update({...p,...values});closeEdit();loadFeed().catch(()=>{})}} onCancel={closeEdit}/>:<button ref={editButton} className="am-profile-edit" onClick={()=>setEditing(true)}>{icon('edit',16)}{t('Chỉnh sửa hồ sơ','Edit profile')}</button>)}
 <p className="am-profile-bio" translate="no">{p.bio||t('Chưa có tiểu sử.','No bio yet.')}</p>
 <dl className="am-profile-stats"><div><dd>{pagination?.total??'—'}</dd><dt>{t('Bài viết','Posts')}</dt></div><div><dd>{comments.data?.pagination.total??'—'}</dd><dt>{t('Bình luận','Comments')}</dt></div><div><dd data-testid="profile-follower-count">{Number.isSafeInteger(p.follower_count)&&p.follower_count>=0?p.follower_count:0}</dd><dt>{t('Người theo dõi','Followers')}</dt></div></dl>
 {!mine&&<div className="am-profile-follow-wrap"><button type="button" className={`am-follow-btn ${p.is_following?'am-follow-btn--active':''}`} onClick={handleFollowToggle} disabled={followBusy} data-testid="profile-follow-button" title={p.is_following?t('Bỏ theo dõi','Unfollow'):t('Theo dõi tài khoản','Follow user')}>{followBusy?<span>{t('Đang xử lý...','Processing...')}</span>:p.is_following?<><span className="material-symbols-outlined am-follow-icon" aria-hidden="true">check</span><span className="am-follow-text am-follow-text--idle">{t('Đang theo dõi','Following')}</span><span className="am-follow-text am-follow-text--hover">{t('Bỏ theo dõi','Unfollow')}</span></>:<><span className="material-symbols-outlined am-follow-icon" aria-hidden="true">person_add</span><span>{t('Theo dõi','Follow')}</span></>}</button></div>}
 <AuraProgress profileId={p.id} publicLevel={p.level} publicRealm={p.realm} publicTitle={p.title}/>
 </section>
 <section className={'am-profile-collection'+(!memeItems.length?' am-profile-collection-empty':'')}><h2>{mine?t('Meme đã sở hữu','Owned memes'):t('Bộ sưu tập Meme','Meme collection')}</h2><LoadState state={memeInventory}>{memeItems.length?<div className="am-profile-inventory">{memeItems.map(item=><div className="am-profile-item" data-rarity={item.asset.rarity} key={item.asset.id}><img src={inventoryImage(item.asset.media_url)} alt={item.asset.display_name||item.asset.slug} width="78" height="78" title={(item.asset.display_name||item.asset.slug)+' · '+item.asset.rarity}/>{mine&&item.quantity>1&&<span className="am-profile-quantity">×{item.quantity}</span>}</div>)}</div>:<p>{mine?t('Chưa có Meme trong bộ sưu tập.','No memes in your collection yet.'):t('Người dùng chưa có Meme trong bộ sưu tập.','No memes in collection yet.')}</p>}</LoadState></section>
 <section className={'am-profile-collection am-profile-backgrounds'+(!backgroundItems.length?' am-profile-collection-empty':'')}><h2>{mine?t('Background đã sở hữu','Owned backgrounds'):t('Bộ sưu tập Background','Background collection')}</h2><LoadState state={backgroundInventory}>{backgroundItems.length?<div className="am-profile-inventory">{backgroundItems.map(item=><div className="am-profile-item" data-rarity={item.asset.rarity} key={item.asset.id} title={(item.asset.display_name||item.asset.slug)+' · '+item.asset.rarity}><BackgroundMini asset={item.asset}/>{mine&&item.quantity>1&&<span className="am-profile-quantity">×{item.quantity}</span>}</div>)}</div>:<p>{mine?t('Chưa có Background trong bộ sưu tập.','No backgrounds in your collection yet.'):t('Người dùng chưa có Background trong bộ sưu tập.','No backgrounds in collection yet.')}</p>}</LoadState></section>
 </aside>
 <div className="am-profile-content"><section className="profile-activity am-profile-activity"><header><div><img src="/assets/brand/favicon-64.png" alt="" width="20" height="20"/><h2>{t('Hoạt động trên AuraMeme','Activity on AuraMeme')}</h2></div>{activity.data&&<span className="am-profile-contributions">{activity.data.total} {t('lượt đóng góp','contributions')}</span>}</header><LoadState state={activity}>{activity.data&&<ActivityHeatmap data={activity.data}/>}</LoadState></section>
 <section className="am-profile-feed" aria-label={t('Bài viết công khai','Public posts')}><ErrorMessage error={error?{message:error}:null}/>{error&&<button className="account-button" onClick={()=>retry().catch(()=>{})}>{t('Thử lại','Try again')}</button>}{posts.map(post=><PostCard key={post.id} post={post} variant="profile"/>)}{loading&&<p role="status" aria-busy="true">{t('Đang tải...','Loading...')}</p>}{!loading&&!error&&!posts.length&&<p className="am-profile-empty">{t('Chưa có bài viết công khai.','No public posts yet.')}</p>}{pagination?.page<pagination?.total_pages&&<button className="account-button am-profile-more" disabled={loading} onClick={()=>loadMore().catch(()=>{})}>{t('Xem thêm bài viết','Load more posts')}</button>}</section>
 </div></>}</LoadState>}</div></main>;
}
