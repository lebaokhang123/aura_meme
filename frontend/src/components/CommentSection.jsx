import {MOCK_AUTH} from '../auth.js';
import React,{useEffect,useRef,useState} from 'react';
import {commentsFor} from '../social-model.js';
import {useSocial} from '../SocialContext.jsx';
import {DEMO_USERS,readDemoUser} from '../demo.js';
import {usePreferences} from '../PreferencesContext.jsx';
import {useLocalized} from '../localize.jsx';
import {ReactionBar} from './ReactionBar.jsx';
import {icon,SocialMessage} from './social-ui.jsx';
import {authorClasses} from '../generated/social-stitch.jsx';
import {POSTS} from '../feed-data.js';
export function relativeTime(createdAt,language) {
  const minutes=Math.max(0,Math.floor((Date.now()-createdAt)/60000));
  if(minutes===0)return language==='en'?'Just now':'Vừa xong';
  return new Intl.RelativeTimeFormat(language,{numeric:'auto'}).format(-minutes,'minute');
}
function CommentRow({comment}) {
  const render=useLocalized(),{commit}=useSocial(),current=readDemoUser(),{language}=usePreferences();
  const author=comment.api?{avatar:comment.authorId===current?.id?current.avatar:comment.avatar,displayName:comment.authorId===current?.id?current.displayName:comment.authorName}:DEMO_USERS.find(user=>user.username===comment.author);
  const profile=comment.api?{handle:comment.handle,level:comment.level,nickname:comment.nickname}:POSTS.find(post=>post.id===({Khang_dev:'khang',Kien_dev:'kien',Gigachad:'gigachad'}[comment.author]));
  const classes=authorClasses(comment.api?'Khang_dev':comment.author,true);
  const isAuthor=comment.api?current?.id===comment.authorId:current?.username===comment.author;
  const isAdmin=!MOCK_AUTH&&Array.isArray(current?.roles)&&current.roles.includes('ADMIN');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[menuOpen,setMenuOpen]=useState(false),[confirm,setConfirm]=useState(null),[reason,setReason]=useState('');
  const menu=useRef(null),menuButton=useRef(null);
  useEffect(()=>{if(!menuOpen)return;const outside=e=>{if(!menu.current?.contains(e.target)){setMenuOpen(false);setConfirm(null)}};const key=e=>{if(e.key==='Escape'){setMenuOpen(false);setConfirm(null);menuButton.current?.focus()}};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key)}},[menuOpen]);
  const pending=useRef(false);
  const handleAction=async()=>{
    if(pending.current)return;
    if((confirm==='hide'||confirm==='admin-delete')&&reason.trim().length<5){
      setError('Vui lòng nhập lý do tối thiểu 5 ký tự.');
      return;
    }
    pending.current=true;setBusy(true);setError('');
    try{
      if(confirm==='author-delete'){
        await commit({type:'delete-comment',id:comment.id,postId:comment.postId});
      }else if(confirm==='hide'){
        await commit({type:'moderate-comment',id:comment.id,postId:comment.postId,status:'hidden',reason:reason.trim()});
      }else if(confirm==='admin-delete'){
        await commit({type:'moderate-comment',id:comment.id,postId:comment.postId,status:'deleted',reason:reason.trim()});
      }
      setMenuOpen(false);setConfirm(null);setReason('');
    }catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  return render(<div className="flex items-start gap-3 p-2.5 rounded-xl bg-surface-container/40 hover:bg-surface-container/70 transition-colors" data-comment-id={comment.id}>
    <img className="w-8 h-8 rounded-full object-cover shrink-0 ring-1 ring-secondary/50" src={author.avatar} alt={author.displayName}/>
    <div className="flex-1 flex flex-col gap-1 min-w-0">
      <div className="flex items-start justify-between gap-2"><div className="flex items-center gap-1.5 flex-wrap min-w-0"><span translate={comment.api?'no':undefined} className="font-label-md text-[13px] font-bold text-on-surface hover:underline cursor-pointer break-all">{author.displayName}</span><span translate={comment.api?'no':undefined} className="text-[11px] text-outline font-normal">{profile.handle}</span><span className={classes.level}>{profile.level}</span><span className={classes.nickname}>{profile.nickname}</span><time className="text-outline text-[11px] ml-auto font-mono-tag" dateTime={comment.createdAt?new Date(comment.createdAt).toISOString():undefined}>{comment.timeLabel||relativeTime(comment.createdAt,language)}</time></div>
      {(isAuthor||isAdmin)&&<div ref={menu} className="relative shrink-0"><button ref={menuButton} type="button" aria-label="Tùy chọn bình luận" aria-haspopup="menu" aria-expanded={menuOpen} className="p-1 text-outline hover:text-on-surface" onClick={()=>{setMenuOpen(v=>!v);setConfirm(null);setReason('');setError('')}}>{icon('more_horiz',18)}</button>{menuOpen&&<div role="menu" className="absolute right-0 top-full z-40 w-[240px] p-2.5 rounded-xl bg-surface-container-high border border-outline-variant shadow-lg text-left">
        {!confirm&&<>
          {isAuthor&&<button type="button" role="menuitem" className="text-error p-2 font-body-sm text-body-sm w-full text-left rounded-lg hover:bg-surface-container-highest flex items-center gap-2" onClick={()=>setConfirm('author-delete')}>{icon('delete',16)}Xóa bình luận</button>}
          {isAdmin&&<div className={isAuthor?'border-t border-outline-variant/60 my-1 pt-1':''}>
            <button type="button" role="menuitem" className="text-secondary p-2 font-body-sm text-body-sm w-full text-left rounded-lg hover:bg-surface-container-highest flex items-center gap-2" onClick={()=>setConfirm('hide')}>{icon('visibility_off',16)}Ẩn bình luận (Admin)</button>
            <button type="button" role="menuitem" className="text-error p-2 font-body-sm text-body-sm w-full text-left rounded-lg hover:bg-surface-container-highest flex items-center gap-2" onClick={()=>setConfirm('admin-delete')}>{icon('delete_forever',16)}Xóa bình luận (Admin)</button>
          </div>}
        </>}
        {confirm&&<div role="group" aria-label="Xác nhận thao tác bình luận" className="p-1 font-body-sm text-body-sm">
          <p className="font-semibold text-on-surface">{confirm==='hide'?'Ẩn bình luận (Admin)':confirm==='admin-delete'?'Xóa bình luận (Admin)':'Xóa bình luận này?'}</p>
          <p className="text-xs text-outline italic truncate my-1">"{comment.text}"</p>
          {(confirm==='hide'||confirm==='admin-delete')&&<label className="block text-left text-xs font-semibold text-on-surface-variant my-1.5">
            Lý do (5-500 ký tự) *
            <textarea
              className="w-full mt-1 p-1.5 bg-surface-container text-on-surface border border-outline rounded text-xs"
              rows={2}
              maxLength={500}
              value={reason}
              onChange={e=>setReason(e.target.value)}
              placeholder="Nhập lý do gửi thông báo..."
              required
              disabled={busy}
            />
          </label>}
          <div className="flex gap-2 mt-2 justify-end">
            <button type="button" disabled={busy} className="px-2 py-1 text-xs text-outline hover:text-on-surface" onClick={()=>{setConfirm(null);setReason('');setError('')}}>Hủy</button>
            <button type="button" disabled={busy} className={`px-2 py-1 text-xs rounded font-semibold ${confirm==='hide'?'bg-secondary-container text-on-secondary-container':'bg-error/20 text-error hover:bg-error/30'}`} onClick={handleAction}>{busy?'Đang lưu...':'Xác nhận'}</button>
          </div>
        </div>}
      </div>}</div>}
      </div>
      <p translate="no" className="font-body-sm text-[13px] text-on-surface leading-snug pt-0.5 social-user-text">{comment.text}</p>
      <div className="flex items-center gap-2 pt-1 flex-wrap"><ReactionBar target="comment" id={comment.id} compact/></div>
      <SocialMessage error={error}/>
    </div>
  </div>);
}
export function CommentSection({postId,active=true}) {
  const render=useLocalized(),{state,commit,loadComments,commentPages}=useSocial(),user=readDemoUser();
  const [text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const pending=useRef(false),draft=useRef(null);
  const input=useRef(null);
  useEffect(()=>{draft.current=null},[text]);
  useEffect(()=>{if(active&&!MOCK_AUTH)loadComments(postId).catch(e=>setError(e.message));},[postId,active]);
  const insert=emoji=>{
    const el=input.current,start=el.selectionStart,end=el.selectionEnd,next=text.slice(0,start)+emoji+text.slice(end);
    if(next.length>2000)return;
    setText(next);
    requestAnimationFrame(()=>{el.focus();el.setSelectionRange(start+emoji.length,start+emoji.length)});
  };
  const send=async event=>{
    event.preventDefault();if(pending.current)return;pending.current=true;setBusy(true);setError('');
    try{await commit({type:'comment',postId,text,id:MOCK_AUTH?'c-'+crypto.randomUUID():(draft.current??=crypto.randomUUID())});setText('')}catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  return render(<div className="flex flex-col gap-3.5 pt-3 border-t border-surface-container-high/80 mt-1">
    <form onSubmit={send} className="flex items-center gap-2.5">
      {user?<img className="w-9 h-9 rounded-full object-cover shrink-0 ring-1 ring-secondary/50 shadow-sm" src={user.avatar} alt={user.displayName}/>:<span className="w-9 h-9 rounded-full bg-surface-container flex items-center justify-center text-outline shrink-0">{icon('person')}</span>}
      <div className="flex-1 flex items-center gap-2 min-w-0 bg-surface-container rounded-xl p-2.5 border border-surface-container-high">
        <textarea ref={input} style={{fieldSizing:'content',minHeight:0,maxHeight:120}} aria-label="Nội dung bình luận" value={text} onChange={event=>setText(event.target.value)} maxLength={2000} rows={1} className="w-full p-0 bg-transparent border-0 outline-none focus:ring-0 resize-none text-on-surface font-body-sm text-body-sm min-w-0" placeholder={user?'Viết bình luận...':'Đăng nhập để bình luận'} onKeyDown={event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();event.currentTarget.form.requestSubmit()}}}/>
        <ReactionBar target="comment" id={`draft-${postId}`} compact onPick={insert}/>
        <button type="submit" disabled={busy} className="px-3 py-1.5 rounded-lg bg-secondary-container text-on-secondary-container text-label-md font-label-md flex items-center gap-1 shrink-0">Gửi {icon('send',16)}</button>
      </div>
    </form>
    <SocialMessage error={error}/>
    {commentsFor(state,postId).map(comment=><CommentRow key={comment.id} comment={comment}/>)}{!MOCK_AUTH&&commentPages[postId]?.page<commentPages[postId]?.total_pages&&<button type="button" disabled={busy} onClick={async()=>{setBusy(true);try{await loadComments(postId,true)}catch(e){setError(e.message)}finally{setBusy(false)}}}>Xem thêm bình luận</button>}
  </div>);
}
