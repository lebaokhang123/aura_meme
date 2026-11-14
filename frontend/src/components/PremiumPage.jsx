// Lucian UX/UI Prompt #056 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#056
import React,{useId,useLayoutEffect,useRef,useState} from 'react';
import {usePreferences} from '../PreferencesContext.jsx';
import '../workspace.css';

const plans=[{name:'Plus',days:30,boost:2,icon:'auto_awesome'},{name:'Prime',days:365,boost:3,icon:'diamond'}];
function RollingDays({days,label}){
 return <span className="u056-od" role="img" aria-label={label}>{String(days).padStart(3,' ').split('').map((digit,k)=>digit===' '?<span className="u056-blank" key={k} aria-hidden="true"/>:<span className="u056-col" key={k} aria-hidden="true" style={{'--d':Number(digit),'--k':k}}>{Array.from({length:10},(_,n)=><span key={n}>{n}</span>)}</span>)}</span>;
}
export default function PremiumPage(){
 const {language}=usePreferences(),t=(vi,en)=>language==='en'?en:vi;
 const [selected,setSelected]=useState(0),[wiggle,setWiggle]=useState(false),root=useRef(null),group=useId(),plan=plans[selected];
 useLayoutEffect(()=>{
  const element=root.current;
  const place=()=>{
   const option=element.querySelectorAll('.u056-sw button')[selected],card=element.querySelectorAll('.u056-p')[selected];
   const knob=element.querySelector('.u056-knob'),ring=element.querySelector('.u056-ring');
   knob.style.setProperty('--x',(option.offsetLeft-4)+'px');knob.style.setProperty('--w',option.offsetWidth+'px');
   ring.style.setProperty('--y',card.offsetTop+'px');ring.style.setProperty('--h',card.offsetHeight+'px');
  };
  place();const observer=new ResizeObserver(place);
  // Font loading can resize a control without resizing the fixed-width selector.
  for(const target of [element,...element.querySelectorAll('.u056-sw button,.u056-p')])observer.observe(target);
  return()=>observer.disconnect();
 },[selected,language]);
 function select(index,focus=false){setSelected(index);setWiggle(index===1);if(focus)root.current.querySelectorAll('.u056-sw button')[index].focus()}
 const features=[t(`×${plan.boost} bonus XP cho Level`,`×${plan.boost} bonus XP for Level`),t(`${plan.days} ngày quyền lợi dự kiến`,`${plan.days} days of planned benefits`),t('Hết hạn vẫn giữ XP đã nhận','Keep earned XP after expiry'),t('Không tự động gia hạn','No automatic renewal')];
 return <main className="workspace-page premium-page"><div className="workspace-content premium-layout">
  <div className="premium-intro">
   <span className="premium-coming"><span/>{t('Sắp ra mắt · Chưa mở đăng ký','Coming Soon · Registration closed')}</span>
   <div className="premium-symbol" aria-hidden="true"><span className="material-symbols-outlined">auto_awesome</span><span className="premium-symbol-orbit"/></div>
   <span className="workspace-kicker">AURA MEMBERSHIPS</span>
   <h1>Aura Plus <span>&</span><br/>Aura Prime<span className="premium-title-dot">.</span></h1>
   <p className="premium-lead">{t('Thêm động lực. Giữ trọn dấu ấn của bạn.','More momentum. The same unmistakable you.')}</p>
   <p className="premium-description">{t('Hai gói dự kiến giúp tăng bonus XP cho hành trình lên Level. Chọn một gói để khám phá quyền lợi trước khi Aura mở đăng ký.','Two planned memberships to boost bonus XP on your Level journey. Select a plan to explore its benefits before registration opens.')}</p>
   <div className="premium-principles"><div><span className="material-symbols-outlined" aria-hidden="true">trending_up</span><span>{t('Thêm XP cho Level','More Level XP')}</span></div><div><span className="material-symbols-outlined" aria-hidden="true">balance</span><span>{t('Rank vẫn tính XP gốc','Rank keeps original XP')}</span></div></div>
   <a className="premium-home" href="/"><span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>{t('Quay lại Trang chủ','Back to Home')}</a>
  </div>
  <section className="premium-selector-panel" aria-labelledby="premium-selector-title"><div className="premium-selector-heading"><span className="workspace-kicker">{t('CHỌN DẤU ẤN CỦA BẠN','FIND YOUR AURA')}</span><h2 id="premium-selector-title">{t('Khám phá hai gói Aura','Explore Aura memberships')}</h2><p>{t('Xem trước quyền lợi · Không có giao dịch','Preview benefits · No transactions')}</p></div>
   <div className="ux u056" ref={root}>
    <div className="u056-sw" role="radiogroup" aria-label={t('Thời hạn gói','Membership duration')}><span className="u056-knob" aria-hidden="true"/>{plans.map((item,i)=><button type="button" key={item.name} role="radio" aria-checked={selected===i} tabIndex={selected===i?0:-1} onClick={()=>select(i)} onKeyDown={e=>{if(['ArrowRight','ArrowLeft','ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();select(e.key==='Home'?0:e.key==='End'?1:1-selected,true)}}}>{item.days} {t('ngày','days')}</button>)}</div>
    <fieldset className="u056-plans"><legend className="workspace-sr">{t('Hai gói dự kiến','Planned memberships')}</legend><span className="u056-ring" aria-hidden="true"/>{plans.map((item,i)=><label className={'u056-p premium-plan premium-'+item.name.toLowerCase()} key={item.name}><input type="radio" name={group} aria-label={'Aura '+item.name} checked={selected===i} onChange={()=>select(i)}/><span className="u056-dot" aria-hidden="true"/><span className="u056-nm"><b>Aura {item.name}{i===1&&<em className={wiggle?'wig':''} onAnimationEnd={()=>setWiggle(false)}>×3 XP</em>}</b><small>{item.days} {t('ngày','days')} · ×{item.boost} {t('bonus XP cho Level','bonus Level XP')}</small></span><span className="material-symbols-outlined u056-plan-icon" aria-hidden="true">{item.icon}</span></label>)}</fieldset>
    <div className="u056-current"><div><span className="u056-current-label">{t('THỜI HẠN DỰ KIẾN','PLANNED DURATION')}</span><div className="u056-duration"><RollingDays days={plan.days} label={plan.days+' '+t('ngày','days')}/><span>{t('ngày','days')}</span></div></div><span className="u056-badge">{t('Sắp ra mắt','Coming Soon')}</span></div>
    <ul className="u056-feat" aria-live="polite" aria-atomic="true">{features.map((feature,i)=><li key={selected+'-'+i} style={{'--i':i}}><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 9.4l3.2 3.2L14 5.6"/></svg>{feature}</li>)}</ul>
    <button className="u056-cta" type="button" disabled><span className="material-symbols-outlined" aria-hidden="true">lock</span>Aura {plan.name} · {t('Chưa mở đăng ký','Registration closed')}</button>
    <p className="u056-price-note">{t('Giá chưa công bố. Chọn gói chỉ để xem quyền lợi dự kiến.','Pricing is not announced. Selection only previews planned benefits.')}</p>
   </div>
  </section>
  <section className="premium-details" aria-labelledby="premium-benefits"><div className="premium-details-heading"><span className="workspace-kicker">{t('QUYỀN LỢI V1 DỰ KIẾN','PLANNED V1 BENEFITS')}</span><h2 id="premium-benefits">{t('Thêm động lực, vẫn công bằng.','A boost that keeps things fair.')}</h2></div><div className="premium-policy-grid">{[['leaderboard',t('Rank theo XP gốc','Original XP for Rank'),t('Boost chỉ dành cho Level. Rank tính XP earned gốc, không nhân boost.','Boost applies to Level. Rank uses original earned XP, without the boost.')],['inventory_2',t('Bảo Khố giữ nguyên','Vault stays the same'),t('Giữ nguyên odds và cooldown Bảo Khố.','Vault odds and cooldown stay the same.')],['verified',t('XP đã nhận là của bạn','Your XP stays yours'),t('Hết hạn vẫn giữ XP đã nhận. Không tự động gia hạn.','Previously earned XP remains after expiry. No automatic renewal.')]].map(([icon,title,body])=><article key={icon}><span className="material-symbols-outlined" aria-hidden="true">{icon}</span><h3>{title}</h3><p>{body}</p></article>)}</div></section>
 </div></main>;
}
