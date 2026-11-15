import React,{useState} from 'react';
import {auth} from '../auth.js';
import {useCopy,ErrorMessage} from './account-ui.jsx';
export function EditProfile({profile,onSaved,onCancel}){
 const t=useCopy(),[name,setName]=useState(profile.display_name),[bio,setBio]=useState(profile.bio||''),[busy,setBusy]=useState(false),[error,setError]=useState(null);
 return <form className="profile-edit" onSubmit={async e=>{e.preventDefault();if(busy)return;setBusy(true);setError(null);try{const response=await auth.write('PATCH','/users/me',{display_name:name.trim(),bio:bio.trim()||null});await auth.refresh();onSaved({display_name:response.display_name,bio:response.bio});}catch(e){if(e.status===401)location.replace('/login?next=%2Fprofile');else setError(e)}finally{setBusy(false)}}}><label>{t('Tên hiển thị','Display name')}<input autoFocus required maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label><label>{t('Tiểu sử','Bio')}<textarea maxLength={1000} rows={5} value={bio} onChange={e=>setBio(e.target.value)}/></label><ErrorMessage error={error}/><div className="account-actions"><button className="account-button primary" disabled={busy}>{busy?t('Đang lưu...','Saving...'):t('Lưu thay đổi','Save changes')}</button><button type="button" className="account-button" disabled={busy} onClick={onCancel}>{t('Hủy','Cancel')}</button></div></form>;
}
