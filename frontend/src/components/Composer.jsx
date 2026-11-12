import React,{useEffect,useRef,useState} from 'react';
import {useLocalized} from '../localize.jsx';
import {readDemoUser} from '../demo.js';
import {CATEGORIES} from '../feed-data.js';
import {useFeed} from '../FeedContext.jsx';
import {useSocial} from '../SocialContext.jsx';
import {validateImage} from '../social-files.js';
import {icon,SocialMessage} from './social-ui.jsx';
const errors={FILE_SIZE:'Ảnh/GIF cần nhỏ hơn hoặc bằng 5 MB.',FILE_TYPE:'Chỉ hỗ trợ ảnh PNG, JPEG hoặc GIF hợp lệ.',FILE_DIMENSIONS:'Ảnh tối đa 8192 px mỗi chiều và 25 triệu pixel.',FILE_DECODE:'Không đọc được ảnh/GIF này.',INVALID_POST:'Nhập nội dung hoặc chọn ảnh/GIF; nội dung tối đa 5000 ký tự.',INVALID_CATEGORY:'Vui lòng chọn một danh mục.'};
const toolClass='flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface font-label-sm text-label-sm transition-all';
export function Composer() {
  const render=useLocalized(),user=readDemoUser(),{commit}=useSocial(),{update}=useFeed();
  const [text,setText]=useState(''),[category,setCategory]=useState(''),[file,setFile]=useState(null),[preview,setPreview]=useState(''),[showPreview,setShowPreview]=useState(false),[busy,setBusy]=useState(false),[validating,setValidating]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  const input=useRef(null),pending=useRef(false),generation=useRef(0);
  useEffect(()=>()=>{generation.current++},[]);
  useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview]);
  const selectFile=async event=>{
    const candidate=event.target.files?.[0],request=++generation.current;if(!candidate)return;
    setValidating(true);setError('');setMessage('');
    try{await validateImage(candidate);if(request!==generation.current)return;setFile(candidate);setPreview(URL.createObjectURL(candidate));}
    catch(e){if(request===generation.current){setError(e.message);setFile(null);setPreview('');input.current.value=''}}
    finally{if(request===generation.current)setValidating(false)}
  };
  const publish=async event=>{
    event.preventDefault();if(pending.current||validating)return;pending.current=true;setBusy(true);setError('');setMessage('');
    const id='p-'+crypto.randomUUID();
    try{
      await commit({type:'create-post',id,content:text,category,mediaId:file?id:null,mediaType:file?.type||null},file);
      setText('');setCategory('');setFile(null);setPreview('');setShowPreview(false);input.current.value='';setMessage('Đã đăng bài trong demo.');
      update({category:'',q:'',sort:'new'});
      requestAnimationFrame(()=>{location.hash='post-'+id});
    }catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  return render(<form onSubmit={publish} className="bg-surface-container-low rounded-xl p-4 shadow-sm flex flex-col gap-3" aria-label="Tạo bài viết">
    <div className="flex items-center gap-3">
      {user?<img className="w-10 h-10 rounded-full object-cover ring-1 ring-secondary/40 shrink-0" src={user.avatar} alt={user.displayName} data-current-user-avatar/>:<span className="w-10 h-10 rounded-full bg-surface-container-high border border-outline-variant flex items-center justify-center text-outline shrink-0">{icon('person')}</span>}
      <div className="flex-1 min-w-0 bg-surface-container rounded-lg px-3.5 py-2.5 flex items-center justify-between gap-2 hover:bg-surface-container-high transition-colors">
        <textarea aria-label="Nội dung bài mới" rows={1} style={{fieldSizing:'content',minHeight:0,maxHeight:180}} readOnly={!user} value={text} maxLength={5000} onChange={event=>setText(event.target.value)} className="w-full min-w-0 border-0 outline-none focus:ring-0 resize-none p-0 bg-transparent font-body-md text-body-md text-on-surface placeholder:text-outline" placeholder={user?'Bạn đang nghĩ gì thế? Chia sẻ một chiếc meme...':'Bạn đang nghĩ gì thế? Đăng nhập để chia sẻ một chiếc meme...'}/><span className="text-outline shrink-0">{icon('edit_square',18)}</span>
      </div>
    </div>
    <div className="flex flex-wrap items-center justify-between gap-2 pt-1"><div className="flex items-center gap-1.5 flex-wrap">
      <button type="button" className={toolClass} onClick={()=>user?input.current.click():location.assign('/login')} disabled={busy||validating}><span className="text-tertiary">{icon('image',16)}</span>Hình ảnh / GIF</button>
      <div className={`${toolClass} relative`}><span className="text-outline">{icon('sell',16)}</span><span>{category?'#'+category:'Thẻ danh mục'}</span><select aria-label="Danh mục bài mới" value={category} onChange={event=>setCategory(event.target.value)} className="absolute inset-0 opacity-0 cursor-pointer" disabled={!user||busy}><option value="">Chọn danh mục</option>{CATEGORIES.map(item=><option value={item.id} key={item.id}>{item.label}</option>)}</select></div>
      {user&&(text||file)&&<button type="button" className={toolClass} onClick={()=>setShowPreview(v=>!v)}>{showPreview?'Ẩn xem trước':'Xem trước'}</button>}
    </div><button type={user?'submit':'button'} disabled={busy||validating} onClick={!user?()=>location.assign('/login'):undefined} className={`px-4 py-2 rounded-lg ${user?'bg-primary-container text-on-primary-container hover:bg-primary':'bg-secondary-container hover:bg-secondary-container/80 text-on-secondary-container'} font-label-md text-label-md font-semibold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer`}>{!user&&icon('login',16)}{busy?'Đang lưu...':user?'Đăng bài':'Đăng nhập để đăng'}{user&&icon('send',16)}</button></div>
    <input ref={input} type="file" accept="image/png,image/jpeg,image/gif" aria-label="Ảnh hoặc GIF bài mới" hidden onChange={selectFile}/>
    {validating&&<p role="status" className="font-body-sm text-body-sm text-outline">Đang kiểm tra ảnh...</p>}
    {file&&<div className="flex items-center gap-2 min-w-0"><img src={preview} alt="Ảnh xem trước" className="w-16 h-16 rounded-lg object-cover"/><span className="font-body-sm text-body-sm text-on-surface-variant break-all">{file.name}</span><button type="button" className="text-secondary font-label-sm text-label-sm shrink-0" onClick={()=>{generation.current++;setFile(null);setPreview('');setValidating(false);input.current.value=''}}>Bỏ ảnh</button></div>}
    {showPreview&&<section aria-label="Bản xem trước bài viết" className="bg-surface-container rounded-xl p-4"><p translate="no" className="font-body-md text-body-md text-on-surface social-user-text">{text}</p>{file&&<img src={preview} alt="Ảnh xem trước" className="w-full rounded-lg object-contain max-h-[460px] mt-3"/>}<span className="text-secondary font-label-sm text-label-sm">#{category}</span></section>}
    {errors[error]?<p role="alert" className="font-body-sm text-body-sm text-error">{errors[error]}</p>:<SocialMessage error={error}/>}
    {message&&<p role="status" className="font-body-sm text-body-sm text-secondary">{message}</p>}
  </form>);
}
