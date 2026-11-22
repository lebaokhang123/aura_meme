import React,{useState} from 'react';
import {useLocalized} from '../localize.jsx';
import {PostCategory,PostLink} from '../FeedContext.jsx';
import {OriginalBody} from '../generated/social-stitch.jsx';
import {ReactionBar} from './ReactionBar.jsx';
import {icon,SocialMessage,CategorySelect} from './social-ui.jsx';
import {CommentSection,relativeTime} from './CommentSection.jsx';
import {PostMenu} from './PostMenu.jsx';
import {ShareButton} from './ShareButton.jsx';
import {useSocial} from '../SocialContext.jsx';
import {commentsFor} from '../social-model.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {usePremium} from '../PremiumContext.jsx';
import {readDemoUser} from '../demo.js';
import {POSTS} from '../feed-data.js';
import UserAvatar from './UserAvatar.jsx';
import {LevelPill,TitleBadge} from './RealmBadges.jsx';

const authors={khang:'Khang_dev',kien:'Kien_dev',gigachad:'Gigachad'};
export const apiStyleAuthor=username=>username==='kien_dev'?'Kien_dev':'Khang_dev';
export {LevelPill,TitleBadge};
export function HallIdentity({id}) {
  const post=POSTS.find(post=>post.id===id);
  return <div className="flex items-center gap-1.5 flex-wrap min-w-0 hall-identity"><span className="font-label-md text-label-md font-bold text-on-surface whitespace-nowrap">{post.authorName}</span><span className="font-mono-tag text-mono-tag text-outline whitespace-nowrap">@{authors[id]}</span><LevelPill level={post.level} size="md"/><TitleBadge level={post.level} realm={post.realm} title={post.nickname} size="md"/></div>;
}
export function PostHeader({post,variant,menu}) {
  const render=useLocalized(),{language}=usePreferences();
  const {subscription}=usePremium?.()||{};
  const currentUser=readDemoUser?.();
  const isCurrentAuthor=Boolean(currentUser&&(
    (post.authorId&&post.authorId===currentUser.id)||
    (post.author&&currentUser.username&&post.author.toLowerCase()===currentUser.username.toLowerCase())||
    (post.handle&&currentUser.username&&post.handle.toLowerCase()===`@${currentUser.username.toLowerCase()}`)
  ));
  const effectiveTier=(isCurrentAuthor&&subscription?.is_active?subscription.tier:null)||post.membershipTier||post.membership_tier||'free';
  const timeLabel=post.createdAt?relativeTime(post.createdAt,language):(post.timeLabel||'');
  const profileHref=post.api&&post.author?'/profile/'+encodeURIComponent(post.author):null;
  const stopExplore=variant==='explore'?e=>e.stopPropagation():undefined;
  return render(<div className="flex items-center justify-between social-post-header">
    <div className="flex items-center gap-3 min-w-0 social-post-identity">{profileHref?<a href={profileHref} onClick={stopExplore} aria-label={`Hồ sơ ${post.authorName}`} className="shrink-0 rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-secondary"><UserAvatar src={post.avatar} alt={post.authorName} tier={effectiveTier} size="md"/></a>:<UserAvatar src={post.avatar} alt={post.authorName} tier={effectiveTier} size="md"/>}
      <div className="flex flex-col min-w-0"><div className="flex items-center gap-1.5 flex-wrap">
        <span className={`font-label-lg text-label-lg text-on-surface font-bold hover:underline cursor-pointer ${post.api?'inline-block max-w-full break-words':variant==='explore'?'flex flex-col whitespace-nowrap':''}`}>{profileHref?<a href={profileHref} onClick={stopExplore} translate="no">{post.authorName}</a>:variant==='explore'?<PostLink post={post}/>:post.authorName}{' '}{profileHref?<a href={profileHref} onClick={stopExplore} className="text-xs text-outline font-normal">{post.handle}</a>:<span className="text-xs text-outline font-normal">{post.handle}</span>}</span>
        <LevelPill level={post.level} size="md"/>
        <TitleBadge level={post.level} realm={post.realm} title={post.nickname} size="md"/>
      </div><div className="flex items-center gap-2 text-outline font-body-sm text-body-sm">{variant==='profile'?<a href={'/#post-'+post.id} className="font-mono-tag text-mono-tag">{timeLabel}</a>:<span className="font-mono-tag text-mono-tag">{timeLabel}</span>}<span>·</span><PostCategory post={post} label={variant==='profile'?post.categoryLabel:undefined} className="text-secondary font-medium"/></div></div>
    </div>{menu||<button type="button" className="p-1.5 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container transition-colors" aria-label="Tùy chọn bài viết">{icon('more_horiz')}</button>}
  </div>);
}
export function PostCard({post,variant,hidden,onExplore}) {
  const render=useLocalized(),{state,commit,categories}=useSocial(),{language}=usePreferences();
  const [editing,setEditing]=useState(false),[text,setText]=useState(post.content),[category,setCategory]=useState(post.category),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [commentsOpen,setCommentsOpen]=useState(post.id==='khang');
  const commentCount=state.api?state.apiInteractions?.post?.[post.id]?.comments_count||0:commentsFor(state,post.id).length;
  const displayed={...post,timeLabel:post.createdAt?relativeTime(post.createdAt,language):(post.timeLabel||'')};
  return render(<article id={`post-${post.id}`} data-post-id={post.id} className={variant==='explore'?'flex flex-col rounded-xl bg-surface-container-low border border-[#292932] p-5 shadow-md hover:shadow-2xl hover:border-secondary/40 transition-all group social-card social-explore':'bg-surface-container-low rounded-xl p-4 shadow-sm flex flex-col gap-3 relative social-card'+(variant==='profile'?' social-profile-post':'')} hidden={hidden} style={{...(hidden?{display:'none'}:{}),scrollMarginTop:'calc(var(--site-header-height) + 16px)'}} onClick={onExplore}>
    <PostHeader post={displayed} variant={variant} menu={<PostMenu postId={post.id} onEdit={()=>{setText(post.content);setCategory(post.category);setEditing(true)}}/>}/>
    {editing?<form aria-label="Sửa bài viết" onSubmit={async event=>{event.preventDefault();if(busy)return;setBusy(true);try{await commit({type:'update-post',id:post.id,content:text,category});setEditing(false)}catch(e){setError(e.message)}finally{setBusy(false)}}} className="flex flex-col gap-3"><textarea aria-label="Nội dung sửa bài" className="bg-surface-container text-on-surface rounded-lg p-3 w-full" maxLength={5000} value={text} onChange={e=>setText(e.target.value)}/><CategorySelect label="Danh mục sửa bài" categories={categories} value={category} onChange={setCategory} disabled={busy} className="social-category-select--wide"/><div className="social-action-row"><button type="submit" disabled={busy} className="social-action-button social-action-button--primary">{icon('check',16)}{busy?'Đang lưu...':'Lưu thay đổi'}</button><button type="button" disabled={busy} className="social-action-button" onClick={()=>setEditing(false)}>{icon('close',16)}Hủy</button></div><SocialMessage error={error}/></form>:post.createdAt?<><p translate="no" className="font-body-md text-body-md text-on-surface social-user-text">{post.content}</p>{post.media&&<div className="w-full bg-surface-container-lowest rounded-lg overflow-hidden relative flex items-center justify-center min-h-[340px] social-post-media"><img src={post.media} alt="Ảnh bài viết" className="w-full object-contain max-h-[460px]"/>{post.mediaType==='image/gif'&&<span className="absolute bottom-3 right-3 font-mono-tag text-mono-tag text-outline">GIF</span>}</div>}</>:<OriginalBody post={post} variant={variant}/>}
    <div className={variant==='explore'?'pt-3 border-t border-[#292932] flex flex-col gap-2.5':'flex flex-wrap items-center justify-between gap-3 pt-1'}>
      <ReactionBar id={post.id}/>
      {variant!=='explore'&&<div className="flex items-center gap-2"><button type="button" className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-secondary/40 text-secondary hover:bg-secondary/10 transition-all" aria-label="Bình luận" aria-expanded={commentsOpen} onClick={()=>setCommentsOpen(v=>!v)}>{icon('chat_bubble_outline')}<span className="font-mono-counter text-mono-counter">{commentCount||null}</span></button><ShareButton postId={post.id} profile={variant==='profile'}/></div>}
    </div>
    {variant!=='explore'&&<div hidden={!commentsOpen} style={!commentsOpen?{display:'none'}:undefined}><CommentSection postId={post.id} active={commentsOpen&&!hidden}/></div>}
  </article>);
}
