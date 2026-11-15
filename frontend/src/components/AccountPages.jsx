import React,{useState,useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {useCopy,useData,ErrorMessage,LoadState,Pagination} from './account-ui.jsx';
export {ContactPage} from './ContactPage.jsx';
export {ProfilePage} from './ProfilePage.jsx';
export {default as VaultPage} from './VaultPage.jsx';
export function ContactInbox(){
 const t=useCopy(),user=useSyncExternalStore(auth.subscribe,auth.snapshot).user,[page,setPage]=useState(1),admin=user?.roles.includes('ADMIN'),state=useData(admin?'/admin/contacts?page='+page:null),[error,setError]=useState(null),[busy,setBusy]=useState(false);
 if(!admin)return <main className="account-page"><h1>{t('Không có quyền truy cập','Access denied')}</h1></main>;
 return <main className="account-page inbox-page"><h1>{t('Hộp thư quản trị','Admin inbox')}</h1><ErrorMessage error={error}/><LoadState state={state}>{!state.data?.items.length&&<p>{t('Chưa có tin nhắn.','No messages yet.')}</p>}{state.data?.items.map(c=><article className="account-panel profile-post" key={c.id}><h2 translate="no">{c.subject}</h2><p translate="no">{c.name} · {c.email}</p><p translate="no">{c.body}</p><label>{t('Trạng thái','Status')}<select value={c.status} disabled={busy} onChange={async e=>{setBusy(true);setError(null);try{await auth.write('PATCH','/admin/contacts/'+c.id,{status:e.target.value});state.retry()}catch(e){setError(e)}finally{setBusy(false)}}}>{[['new',t('Mới','New')],['in_review',t('Đang xử lý','In review')],['resolved',t('Đã xử lý','Resolved')]].map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></label></article>)}<Pagination data={state.data} page={page} onChange={setPage}/></LoadState></main>;
}
