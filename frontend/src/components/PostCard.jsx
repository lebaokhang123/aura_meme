import React,{useState} from 'react';
import {useLocalized} from '../localize.jsx';
import {PostCategory,PostLink} from '../FeedContext.jsx';
import {OriginalBody,authorClasses} from '../generated/social-stitch.jsx';
import {ReactionBar} from './ReactionBar.jsx';
import {icon} from './social-ui.jsx';
import {CommentSection,relativeTime} from './CommentSection.jsx';
import {PostMenu} from './PostMenu.jsx';
import {ShareButton} from './ShareButton.jsx';
import {useSocial} from '../SocialContext.jsx';
import {commentsFor} from '../social-model.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {POSTS} from '../feed-data.js';

const authors={khang:'Khang_dev',kien:'Kien_dev',gigachad:'Gigachad'};
export function HallIdentity({id}) {
  const post=POSTS.find(post=>post.id===id),classes=authorClasses(authors[id]);
  return <div className="flex items-center gap-1.5 flex-wrap min-w-0 hall-identity"><span className="font-label-md text-label-md font-bold text-on-surface whitespace-nowrap">{post.authorName}</span><span className="font-mono-tag text-mono-tag text-outline whitespace-nowrap">@{authors[id]}</span><span className={`${classes.level} whitespace-nowrap`}>{post.level}</span><span className={`${classes.nickname} whitespace-nowrap`}>{post.nickname}</span></div>;
}
export function PostHeader({post,variant,menu}) {
  const render=useLocalized(),classes=authorClasses(post.author||authors[post.id]);
  return render(<div className="flex items-center justify-between">
    <div className="flex items-center gap-3 min-w-0"><img className="w-9 h-9 rounded-full object-cover shrink-0 ring-1 ring-secondary/50" src={post.avatar} alt={post.authorName}/>
      <div className="flex flex-col min-w-0"><div className="flex items-center gap-1.5 flex-wrap">
        <span className={`font-label-lg text-label-lg text-on-surface font-bold hover:underline cursor-pointer ${variant==='explore'?'flex flex-col whitespace-nowrap':''}`}>{variant==='explore'?<PostLink post={post}/>:post.authorName}{' '}<span className="text-xs text-outline font-normal">{post.handle}</span></span>
        <span className={`${classes.level} whitespace-nowrap shrink-0`}>{post.level}</span><span className={`${classes.nickname} whitespace-nowrap shrink-0`}>{post.nickname}</span>
      </div><div className="flex items-center gap-2 text-outline font-body-sm text-body-sm"><span className="font-mono-tag text-mono-tag">{post.timeLabel}</span><span>·</span><PostCategory post={post} className="text-secondary font-medium"/></div></div>
    </div>{menu||<button type="button" className="p-1.5 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container transition-colors" aria-label="Tùy chọn bài viết">{icon('more_horiz')}</button>}
  </div>);
}
export function PostCard({post,variant,hidden,onExplore}) {
  const render=useLocalized(),{state}=useSocial(),{language}=usePreferences();
  const [commentsOpen,setCommentsOpen]=useState(post.id==='khang');
  const commentCount=commentsFor(state,post.id).length;
  const displayed={...post,timeLabel:post.timeLabel||relativeTime(post.createdAt,language)};
  return render(<article id={`post-${post.id}`} data-post-id={post.id} className={variant==='explore'?'flex flex-col rounded-xl bg-surface-container-low border border-[#292932] p-5 shadow-md hover:shadow-2xl hover:border-secondary/40 transition-all group social-card social-explore':'bg-surface-container-low rounded-xl p-4 shadow-sm flex flex-col gap-3 relative social-card'} hidden={hidden} style={{...(hidden?{display:'none'}:{}),scrollMarginTop:'calc(var(--site-header-height) + 16px)'}} onClick={onExplore}>
    <PostHeader post={displayed} variant={variant} menu={<PostMenu postId={post.id}/>}/>
    {post.createdAt?<><p translate="no" className="font-body-md text-body-md text-on-surface social-user-text">{post.content}</p>{post.media&&<div className="w-full bg-surface-container-lowest rounded-lg overflow-hidden relative flex items-center justify-center min-h-[340px]"><img src={post.media} alt="Ảnh bài viết" className="w-full object-contain max-h-[460px]"/>{post.mediaType==='image/gif'&&<span className="absolute bottom-3 right-3 font-mono-tag text-mono-tag text-outline">GIF</span>}</div>}</>:<OriginalBody post={post} variant={variant}/>}
    <div className={variant==='explore'?'pt-3 border-t border-[#292932] flex flex-col gap-2.5':'flex flex-wrap items-center justify-between gap-3 pt-1'}>
      <ReactionBar id={post.id}/>
      {variant!=='explore'&&<div className="flex items-center gap-2"><button type="button" className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-secondary/40 text-secondary hover:bg-secondary/10 transition-all" aria-label="Bình luận" aria-expanded={commentsOpen} onClick={()=>setCommentsOpen(v=>!v)}>{icon('chat_bubble_outline')}<span className="font-mono-counter text-mono-counter">{commentCount||null}</span></button><ShareButton postId={post.id}/></div>}
    </div>
    {variant!=='explore'&&<div hidden={!commentsOpen} style={!commentsOpen?{display:'none'}:undefined}><CommentSection postId={post.id}/></div>}
  </article>);
}
