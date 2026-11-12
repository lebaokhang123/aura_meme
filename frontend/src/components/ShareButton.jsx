import React,{useRef,useState} from 'react';
import {useLocalized} from '../localize.jsx';
import {icon} from './social-ui.jsx';
export function ShareButton({postId}) {
  const render=useLocalized();
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[manual,setManual]=useState('');
  const pending=useRef(false);
  const share=async()=>{
    if(pending.current)return;pending.current=true;setBusy(true);setMessage('');setManual('');
    const url=new URL('/',location.origin);url.hash='post-'+postId;
    try{
      if(navigator.share&&(!navigator.canShare||navigator.canShare({url:url.href}))){
        try{await navigator.share({title:'AuraMeme',url:url.href});setMessage('Đã mở chia sẻ.');return;}
        catch(error){if(error.name==='AbortError')return;}
      }
      if(!navigator.clipboard?.writeText)throw Error('CLIPBOARD_UNAVAILABLE');
      await navigator.clipboard.writeText(url.href);setMessage('Đã sao chép liên kết.');
    }catch{setMessage('Không sao chép được. Bạn có thể chọn liên kết để sao chép thủ công.');setManual(url.href)}finally{pending.current=false;setBusy(false)}
  };
  return render(<div className="relative"><button type="button" disabled={busy} aria-label="Chia sẻ" className="p-1.5 text-outline hover:text-secondary transition-colors" onClick={share}>{icon('share')}</button>
    {message&&<div role="status" className="absolute right-0 top-full z-30 w-[240px] max-w-[70vw] p-3 rounded-xl bg-surface-container-high border border-outline-variant text-on-surface font-body-sm text-body-sm shadow-lg">{message}{manual&&<input aria-label="Liên kết bài viết" className="w-full min-w-0 mt-2 bg-surface-container text-on-surface p-2 rounded" readOnly value={manual} onFocus={event=>event.target.select()}/>}<button type="button" aria-label="Đóng thông báo chia sẻ" onClick={()=>{setMessage('');setManual('')}} className="ml-2 text-secondary">×</button></div>}
  </div>);
}
