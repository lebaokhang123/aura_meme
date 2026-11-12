import React,{useEffect,useRef,useState} from 'react';
import {useSocial} from '../SocialContext.jsx';
import {readDemoUser} from '../demo.js';
import {useLocalized} from '../localize.jsx';
import {icon,SocialMessage} from './social-ui.jsx';
export function PostMenu({postId}) {
  const render=useLocalized(),{posts,commit}=useSocial(),user=readDemoUser();
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const root=useRef(null),button=useRef(null),pending=useRef(false);
  const post=posts.find(post=>post.id===postId);
  const owned=!!user&&(post?.author||({khang:'Khang_dev',kien:'Kien_dev',gigachad:'Gigachad'}[postId]))===user.username;
  const [confirm,setConfirm]=useState(false);
  useEffect(()=>{
    if(!open)return;
    const outside=event=>{if(!root.current?.contains(event.target))setOpen(false)};
    const key=event=>{if(event.key==='Escape'){setOpen(false);button.current.focus()}};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key)};
  },[open]);
  const toggle=async()=>{
    if(pending.current)return;pending.current=true;setBusy(true);setError('');
    try{await commit({type:'delete-post',id:postId});setOpen(false);}catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  return render(<div className="relative shrink-0" ref={root}>
    <button ref={button} type="button" aria-label="Tùy chọn bài viết" aria-haspopup="menu" aria-expanded={open} className="p-1.5 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container transition-colors" onClick={()=>{setOpen(v=>!v);setConfirm(false);setError('')}}>{icon('more_horiz',18)}</button>
    {open&&<div role="menu" className="absolute right-0 top-full mt-2 z-40 w-[210px] p-2 rounded-xl bg-surface-container-high border border-outline-variant shadow-xl">
      {owned?<><button type="button" role="menuitem" disabled={busy} className="w-full flex items-center gap-2 text-error font-body-sm text-body-sm p-2 rounded-lg hover:bg-surface-container-highest" onClick={()=>setConfirm(true)}>{icon('delete')}Xóa bài</button>
      {confirm&&<div role="group" aria-label="Xác nhận xóa bài" className="p-2 font-body-sm text-body-sm text-on-surface"><p>Xóa bài này khỏi demo?</p><div className="flex gap-3 mt-2"><button type="button" disabled={busy} className="text-error" onClick={toggle}>Xác nhận xóa</button><button type="button" onClick={()=>setConfirm(false)}>Hủy</button></div></div>}</>:<p className="font-body-sm text-body-sm p-2 text-outline">Bạn chỉ được xóa bài của mình.</p>}
      <SocialMessage error={error}/>
    </div>}
  </div>);
}
