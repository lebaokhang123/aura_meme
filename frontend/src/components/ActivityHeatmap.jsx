import React,{useId,useMemo,useRef,useState} from 'react';
import {activityGrid} from '../activity-grid.js';
import {usePreferences} from '../PreferencesContext.jsx';
export function ActivityHeatmap({data}){
 const {language}=usePreferences(),t=(vi,en)=>language==='en'?en:vi;
 const grid=useMemo(()=>{try{return activityGrid(data,language)}catch{return {error:true,todayIndex:0}}},[data,language]),[focused,setFocused]=useState(grid.todayIndex),[tooltip,setTooltip]=useState(null),cells=useRef([]),tip=useId();
 function move(event,index){
  let next=index;
  if(event.key==='ArrowLeft')next-=7;else if(event.key==='ArrowRight')next+=7;else if(event.key==='ArrowUp')next--;else if(event.key==='ArrowDown')next++;else if(event.key==='Home')next=event.ctrlKey?0:index-index%7;else if(event.key==='End')next=event.ctrlKey?grid.todayIndex:index-index%7+6;else if(event.key==='Escape'){setTooltip(null);return}else return;
  event.preventDefault();next=Math.max(0,Math.min(grid.todayIndex,next));setFocused(next);cells.current[next]?.focus({preventScroll:true});cells.current[next]?.scrollIntoView({block:'nearest',inline:'nearest'});
 }
 if(grid.error)return <p role="alert">{t('Dữ liệu hoạt động chưa hợp lệ. Vui lòng tải lại.','Invalid activity data. Please reload.')}</p>;
 return <div className="activity-graph"><div className="activity-scroll" tabIndex={0} role="region" aria-label={t('Lịch hoạt động 53 tuần, múi giờ Việt Nam','53-week activity calendar, Vietnam timezone')}><div className="activity-calendar">
 <div className="activity-months" aria-hidden="true">{grid.months.map(month=><span key={month.title} title={month.title} style={{left:month.week*14}}>{month.label}</span>)}</div>
 <div className="activity-weeks">{grid.weeks.map((week,column)=><div className="activity-week" key={week[0].date}>{week.map((day,row)=>{const index=column*7+row;return <button key={day.date} type="button" ref={node=>cells.current[index]=node} data-activity-day={day.date} data-activity-count={day.count} data-level={day.level} data-future={day.future||undefined} disabled={day.future} tabIndex={!day.future&&focused===index?0:-1} aria-label={day.label} aria-describedby={tooltip===index?tip:undefined} onFocus={()=>{setFocused(index);setTooltip(index)}} onBlur={()=>setTooltip(null)} onMouseEnter={()=>setTooltip(index)} onMouseLeave={()=>setTooltip(null)} onClick={()=>setTooltip(index)} onKeyDown={event=>move(event,index)}/>})}</div>)}</div>
 <div className="activity-legend"><span>{t('Ít','Less')}</span>{[0,1,2,3,4].map(level=><i data-level={level} key={level}/>)}<span>{t('Nhiều','More')}</span></div>
 </div></div>{tooltip!==null&&<div className="activity-tooltip" role="tooltip" id={tip}>{grid.weeks[Math.floor(tooltip/7)][tooltip%7].label}</div>}</div>;
}
