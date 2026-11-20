import React,{useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {auth} from '../auth.js';
import {apiAuraProgress,apiAuraCheckIn,resetSeconds} from '../aura-api.js';
import {useCopy,ErrorMessage} from './account-ui.jsx';

export function AuraProgress({profileId,home=false,publicLevel,publicRealm}){
 const t=useCopy(),session=useSyncExternalStore(auth.subscribe,auth.snapshot),identity=session.user?.id;
 const own=session.status==='authenticated'&&(home||profileId===identity);
 const [state,setState]=useState({}),[revision,setRevision]=useState(0),[now,setNow]=useState(Date.now());
 const locked=useRef(false),mounted=useRef(false);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[]);
 useEffect(()=>{
  let active=true;locked.current=false;setState({identity,busy:own});
  if(own)auth.read('/aura/progress').then(apiAuraProgress).then(data=>{if(active)setState({identity,data,receivedAt:Date.now()})},error=>{if(active){setState({identity,error});if(error.status===401)auth.refresh().catch(()=>{});}});
  return()=>{active=false};
 },[own,identity,revision]);
 useEffect(()=>{const listener=()=>setRevision(v=>v+1);window.addEventListener('aurameme:aura:invalidate',listener);return()=>window.removeEventListener('aurameme:aura:invalidate',listener)},[]);
 const current=own&&state.identity===identity?state:{},data=current.data;
 useEffect(()=>{if(!data)return;setNow(Date.now());const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer)},[data]);
 const remaining=data?resetSeconds(data,current.receivedAt,now):null;
 useEffect(()=>{if(remaining===0)setRevision(v=>v+1)},[remaining]);
 const retry=()=>setRevision(v=>v+1);
 async function checkIn(){
  if(locked.current||!data||data.checked_in)return;locked.current=true;setState(s=>({...s,saving:true,error:null}));
  try{
   apiAuraCheckIn(await auth.write('POST','/aura/check-in'));
   if(mounted.current&&auth.snapshot().user?.id===identity)retry();
  }catch(error){
   if(mounted.current&&auth.snapshot().user?.id===identity)setState(s=>({...s,data:null,saving:false,error}));
  }finally{locked.current=false;}
 }
 const percentage=data?(data.next_level_xp===null?100:Math.min(100,100*data.level_xp/Math.max(1,data.next_level_xp))):0;
 const displayLevel=data?.level??(publicLevel!==undefined&&publicLevel!==null?publicLevel:'—');
 const displayRealm=data?.realm||publicRealm||t('Chưa có dữ liệu','No data yet');
 const titleBadge=home?(session.user?.username==='khang_dev'?'Bá Chủ Thiên Lôi':session.user?.username==='kien_dev'?'Thiên Tướng Độ Ách':displayRealm):displayRealm;
 return <div data-aura className={home?'am-profile-progress am-home-aura-progress':'am-profile-progress'} aria-busy={current.busy||current.saving||undefined}>
 <div className="am-profile-badges"><span translate="no">LVL {displayLevel}</span><span translate="no">{titleBadge}</span></div>
 <div className="am-profile-progress-track" role="progressbar" aria-label={t('Tiến độ Level','Level progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={data?Math.floor(percentage):undefined}><div style={{width:percentage+'%',height:'100%',background:'var(--am-secondary)'}}/></div>
 <div className="am-profile-progress-caption"><span>{data?data.total_xp+' Exp':'— Exp'}</span><span>{t('Chuỗi: ','Streak: ')}{data?.streak_days??'—'}</span></div>
 {data&&<><span className="block font-body-sm text-[12px] text-on-surface-variant leading-relaxed">{data.next_level_xp===null?t('Đã đạt cấp tối đa','Maximum level reached'):t('Exp cần để lên cấp: ','Exp to next level: ')+data.xp_to_next}</span><span className="block font-body-sm text-[12px] text-on-surface-variant leading-relaxed">{t('Exp gốc: ','Earned Exp: ')}{data.earned_xp} · {t('Exp thưởng: ','Bonus Exp: ')}{data.bonus_xp}</span></>}
 {current.busy&&<p role="status">{t('Đang tải Aura...','Loading Aura...')}</p>}
 {current.error&&<>{current.error.code==='NOT_READY'?<p role="alert">{t('Aura chưa sẵn sàng.','Aura is not ready yet.')}</p>:<ErrorMessage error={current.error}/>}<button className="account-button" onClick={retry}>{t('Thử lại','Try again')}</button></>}
 {data&&<div className="bg-surface-container rounded-xl p-3 flex flex-col gap-2.5 border border-amber-500/20"><button type="button" style={{color:'#17111f'}} className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-400 text-surface-container-lowest font-label-md font-bold disabled:opacity-60" disabled={data.checked_in||current.saving} onClick={checkIn}>{current.saving?t('Đang điểm danh...','Checking in...'):data.checked_in?t('Đã điểm danh','Checked in'):t('Điểm danh','Check in')}</button><span role="status">{t('Ngày mới sau: ','Next reset in: ')}{remaining===null?'—':Math.floor(remaining/3600)+':'+String(Math.floor(remaining%3600/60)).padStart(2,'0')+':'+String(remaining%60).padStart(2,'0')}</span></div>}
 </div>;
}
