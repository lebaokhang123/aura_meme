import React,{useEffect,useState,useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {usePreferences} from '../PreferencesContext.jsx';
export function useCopy(){const {language}=usePreferences();return (vi,en)=>language==='en'?en:vi;}
export function useData(path,revisionKey=0){
 const [state,setState]=useState({busy:true}),[revision,retry]=useState(0);
 const identity=useSyncExternalStore(auth.subscribe,auth.snapshot).user?.id;
 useEffect(()=>{let active=true;setState({busy:true});if(!path){setState({busy:false});return;}
 auth.read(path).then(data=>{if(active)setState({data,busy:false})},error=>{if(active){setState({error,busy:false});if(error.status===401)auth.refresh().catch(()=>{});}});return()=>{active=false};},[path,revision,identity,revisionKey]);
 return {...state,retry:()=>retry(v=>v+1),update:data=>setState({data,busy:false})};
}
export function ErrorMessage({error}){const t=useCopy();if(!error)return null;return <p role="alert" className="account-error">{error.status===429?t('Quá nhiều lần thử. Vui lòng thử lại sau.','Too many attempts. Please try again later.'):error.status===401?t('Phiên đăng nhập đã hết hạn.','Your session has expired.'):error.status===403?t('Không có quyền hoặc phiên xác thực đã thay đổi. Vui lòng thử lại.','Permission denied or authentication changed. Please try again.'):error.status===404?t('Không tìm thấy nội dung công khai.','Public content not found.'):error.status===422?t('Thông tin chưa hợp lệ. Vui lòng kiểm tra các trường.','Invalid details. Please check the fields.'):t('Không kết nối hoặc lưu được dữ liệu. Vui lòng thử lại.','Unable to connect or save. Please try again.')}</p>;}
export function LoadState({state,children}){const t=useCopy();return state.busy?<p role="status" aria-busy="true">{t('Đang tải...','Loading...')}</p>:state.error?<><ErrorMessage error={state.error}/><button className="account-button" onClick={state.retry}>{t('Thử lại','Try again')}</button></>:children;}
export function Pagination({data,page,onChange}){const t=useCopy();if(!data||data.pagination.total_pages<=1)return null;return <nav className="account-pagination" aria-label={t('Phân trang','Pagination')}><button className="account-button" disabled={page<=1} onClick={()=>onChange(page-1)}>{t('Trước','Previous')}</button><span>{page} / {data.pagination.total_pages}</span><button className="account-button" disabled={page>=data.pagination.total_pages} onClick={()=>onChange(page+1)}>{t('Tiếp','Next')}</button></nav>;}
