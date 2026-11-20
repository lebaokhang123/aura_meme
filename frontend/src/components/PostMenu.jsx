import {MOCK_AUTH} from '../auth.js';
import React,{useEffect,useRef,useState} from 'react';
import {useSocial} from '../SocialContext.jsx';
import {readDemoUser} from '../demo.js';
import {useLocalized} from '../localize.jsx';
import {icon,SocialMessage} from './social-ui.jsx';
export function PostMenu({postId,onEdit}) {
  const render=useLocalized(),{posts,commit}=useSocial(),user=readDemoUser();
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const root=useRef(null),button=useRef(null),pending=useRef(false);
  const post=posts.find(post=>post.id===postId);
  const owned=!!user&&(MOCK_AUTH?(post?.author||({khang:'Khang_dev',kien:'Kien_dev',gigachad:'Gigachad'}[postId]))===user.username:post?.authorId===user.id);
  const admin=!MOCK_AUTH&&user?.roles.includes('ADMIN');
  const [confirm,setConfirm]=useState(null),dialog=useRef(null),[reason,setReason]=useState('');
  const hiding=confirm==='hide',adminDeleting=confirm==='admin-delete';
  const isModerating=hiding||adminDeleting;
  useEffect(()=>{if(confirm&&!dialog.current?.open)dialog.current?.showModal()},[confirm]);
  const close=()=>{if(busy)return;dialog.current?.close();setConfirm(null);setError('');setReason('');button.current?.focus({preventScroll:true})};
  const ask=action=>{setError('');setReason('');setOpen(false);setConfirm(action)};
  useEffect(()=>{
    if(!open)return;
    const outside=event=>{if(!root.current?.contains(event.target))setOpen(false)};
    const key=event=>{if(event.key==='Escape'){setOpen(false);button.current.focus()}};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key)};
  },[open]);
  const toggle=async()=>{
    if(pending.current)return;
    if(isModerating&&reason.trim().length<5){
      setError('Vui lòng nhập lý do tối thiểu 5 ký tự.');
      return;
    }
    pending.current=true;setBusy(true);setError('');
    try{
      if(hiding){
        await commit({type:'moderate-post',id:postId,status:'hidden',reason:reason.trim()});
      }else if(adminDeleting){
        await commit({type:'moderate-post',id:postId,status:'deleted',reason:reason.trim()});
      }else{
        await commit({type:'delete-post',id:postId});
      }
      dialog.current?.close();setConfirm(null);setOpen(false);setReason('');
    }catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  return render(<div className="relative shrink-0" ref={root}>
    <button ref={button} type="button" aria-label="Tùy chọn bài viết" aria-haspopup="menu" aria-expanded={open} className="p-1.5 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container transition-colors" onClick={()=>{setOpen(v=>!v);setError('')}}>{icon('more_horiz',18)}</button>
    {open&&<div role="menu" className="absolute right-0 top-full mt-2 z-40 w-[220px] p-2 rounded-xl bg-surface-container-high border border-outline-variant shadow-xl">
      {owned?<>{!MOCK_AUTH&&<button type="button" role="menuitem" className="w-full text-left p-2 text-secondary font-body-sm text-body-sm" onClick={()=>{setOpen(false);onEdit?.()}}>Sửa bài</button>}<button type="button" role="menuitem" disabled={busy} className="w-full flex items-center gap-2 text-error font-body-sm text-body-sm p-2 rounded-lg hover:bg-surface-container-highest" onClick={()=>ask('delete')}>{icon('delete')}Xóa bài</button></>:<p className="font-body-sm text-body-sm p-2 text-outline">Bạn chỉ được xóa bài của mình.</p>}
      {admin&&<div className="border-t border-outline-variant/60 my-1 pt-1">
        <button type="button" role="menuitem" disabled={busy} className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-surface-container-highest text-secondary font-body-sm text-body-sm" onClick={()=>ask('hide')}>{icon('visibility_off')}Ẩn bài (Admin)</button>
        <button type="button" role="menuitem" disabled={busy} className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-surface-container-highest text-error font-body-sm text-body-sm" onClick={()=>ask('admin-delete')}>{icon('delete_forever')}Xóa bài (Admin)</button>
      </div>}
      <SocialMessage error={error}/>
    </div>}
    {confirm&&<dialog ref={dialog} className="social-confirm" role="alertdialog" aria-label={hiding?'Xác nhận ẩn bài':adminDeleting?'Xác nhận xóa bài (Admin)':'Xác nhận xóa bài'} aria-describedby={`post-confirm-${postId}`} onClick={event=>event.stopPropagation()} onCancel={event=>{event.preventDefault();close()}} onClose={()=>{setConfirm(null);button.current?.focus({preventScroll:true})}}>
      <h3 className="social-confirm__title">{icon(hiding?'visibility_off':'delete_outline',22)}{hiding?'Xác nhận ẩn bài (Admin)':adminDeleting?'Xác nhận xóa bài (Admin)':'Xác nhận xóa bài'}</h3>
      <p id={`post-confirm-${postId}`} className="social-confirm__description">
        {hiding?'Ẩn bài viết này khỏi bảng tin cộng đồng?':adminDeleting?'Xóa hoàn toàn bài viết này với tư cách Quản trị viên?':MOCK_AUTH?'Xóa bài này khỏi demo?':'Xóa bài này?'}
      </p>
      {post?.title&&<p className="text-xs text-outline italic truncate px-1">"{post.title}"</p>}
      {isModerating&&<label className="block text-left text-xs font-semibold text-on-surface-variant mt-2 mb-1">
        Lý do kiểm duyệt (5-500 ký tự) *
        <textarea
          className="w-full mt-1 p-2 bg-surface-container text-on-surface border border-outline rounded-lg text-sm"
          rows={3}
          maxLength={500}
          value={reason}
          onChange={e=>setReason(e.target.value)}
          placeholder="Nhập lý do gửi thông báo tới tác giả bài viết..."
          required
          disabled={busy}
        />
        <span className="text-[11px] text-outline font-normal block mt-1">Lý do sẽ được gửi thông báo tới tác giả bài viết.</span>
      </label>}
      <div className="social-action-row"><button type="button" autoFocus disabled={busy} className="social-action-button" onClick={close}>Hủy</button><button type="button" disabled={busy} className={`social-action-button ${hiding?'social-action-button--primary':'social-action-button--danger'}`} onClick={toggle}>{icon(hiding?'visibility_off':'delete',16)}{busy?'Đang lưu...':hiding?'Xác nhận ẩn':'Xác nhận xóa'}</button></div>
      <SocialMessage error={error}/>
    </dialog>}
  </div>);
}
