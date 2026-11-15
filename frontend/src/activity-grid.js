const DAY=86400000;
function calendarDate(value){if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))throw Error('ACTIVITY_PROTOCOL');const time=Date.parse(value+'T00:00:00Z');if(!Number.isFinite(time)||new Date(time).toISOString().slice(0,10)!==value)throw Error('ACTIVITY_PROTOCOL');return time;}
export function activityGrid(value,language='vi'){
 const fail=()=>{throw Error('ACTIVITY_PROTOCOL')};
 if(value?.timezone!=='Asia/Ho_Chi_Minh'||!Array.isArray(value.days)||value.days.length!==371)fail();
 const start=calendarDate(value.start_date),today=calendarDate(value.end_date),todayIndex=(today-start)/DAY;
 if(new Date(start).getUTCDay()!==1||todayIndex<364||todayIndex>370||!Number.isInteger(todayIndex))fail();
 const locale=language==='en'?'en-GB':'vi-VN',months=[];
 let total=0;
 const days=value.days.map((day,index)=>{
  const time=calendarDate(day.date),future=time>today;
  if(time!==start+index*DAY||![day.posts,day.comments,day.count].every(n=>Number.isSafeInteger(n)&&n>=0)||day.count!==day.posts+day.comments||future&&day.count!==0)fail();
  total+=day.count;const date=new Date(time),week=Math.floor(index/7);
  if(!future&&(index===0||date.getUTCDate()===1)){
   const month={week,month:date.getUTCMonth()+1,label:language==='en'?new Intl.DateTimeFormat(locale,{month:'short',timeZone:'UTC'}).format(date):'Thg '+(date.getUTCMonth()+1),title:new Intl.DateTimeFormat(locale,{month:'long',year:'numeric',timeZone:'UTC'}).format(date)};
   if(months.at(-1)?.week===week)months.pop();months.push(month);
  }
  return {...day,future,level:day.count===0?0:day.count===1?1:day.count<4?2:day.count<8?3:4,label:new Intl.DateTimeFormat(locale,{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(date)+': '+day.count+(language==='en'?' activities':' hoạt động')};
 });
 if(!Number.isSafeInteger(value.total)||value.total!==total)fail();
 return {weeks:Array.from({length:53},(_,i)=>days.slice(i*7,i*7+7)),months,total,todayIndex};
}
