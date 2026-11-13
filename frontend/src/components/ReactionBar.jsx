import {MOCK_AUTH} from '../auth.js';
import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {REACTIONS,reactionCounts} from '../social-model.js';
import {useSocial} from '../SocialContext.jsx';
import {readDemoUser} from '../demo.js';
import {useLocalized} from '../localize.jsx';
import {icon,pillClass,SocialMessage} from './social-ui.jsx';
import {PickerMarkup} from '../generated/social-stitch.jsx';

export function ReactionBar({target='post',id,compact=false,onPick}) {
  const render=useLocalized(),{state,commit,ready}=useSocial(),user=readDemoUser();
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const root=useRef(null),trigger=useRef(null),popup=useRef(null),pending=useRef(false);
  const [position,setPosition]=useState({left:16,top:90,width:340});
  const records=target==='post'?state.postReactions:state.commentReactions;
  const selected=onPick?undefined:state.api?(user?state.apiInteractions?.[target]?.[id]?.viewer_reaction:null):records[id]?.[user?.username];
  const counts=onPick?[]:reactionCounts(state,target,id);
  const visible=counts.length>5?[...counts].sort((a,b)=>b.count-a.count).slice(0,5):counts;
  const primary=target==='post'&&id==='khang';
  const popoverId=primary?'reaction-popover':`reaction-${target}-${id}`;
  useEffect(()=>{
    if(!open)return;
    const outside=event=>{if(!root.current?.contains(event.target)&&!popup.current?.contains(event.target))setOpen(false)};
    const key=event=>{if(event.key==='Escape'){setOpen(false);trigger.current?.focus()}};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key)};
  },[open]);
  useLayoutEffect(()=>{
    if(!open)return;
    const box=trigger.current.getBoundingClientRect(),width=Math.min(340,innerWidth-32);
    const header=Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--site-header-height'))||80;
    const height=Math.min(popup.current?.offsetHeight||500,innerHeight-header-32);
    setPosition({width,left:Math.max(16,Math.min(innerWidth-width-16,box.right-width)),top:Math.max(header+8,box.top-height-8)});
    popup.current?.querySelector('[data-reaction]')?.focus({preventScroll:true});
  },[open]);
  const react=async reaction=>{
    if(pending.current)return;pending.current=true;setBusy(true);setError('');
    try{if(onPick){if(!user)throw Error('LOGIN_REQUIRED');onPick(REACTIONS.find(r=>r.id===reaction).emoji);}else await commit({type:'react',target,id,reaction});setOpen(false);}catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  const adapt=node=>{
    if(Array.isArray(node))return node.map((n,index)=>{const result=adapt(n);return React.isValidElement(result)?React.cloneElement(result,{key:index}):result});
    if(!React.isValidElement(node))return typeof node==='string'&&node.trim()==='Đã sở hữu'?'Chưa hỗ trợ':node;
    let props={...node.props};
    if(props.id)delete props.id;
    if(node.type==='button'){
      const getText=value=>typeof value==='string'?value:Array.isArray(value)?value.map(getText).join(''):value?.props?getText(value.props.children):'';
      const text=getText(props.children).trim();
      const option=REACTIONS.find(r=>r.emoji===text);
      if(option)props={...props,'data-reaction':option.id,'aria-label':option.label,'aria-pressed':selected===option.id,disabled:busy||!ready,onClick:()=>react(option.id)};
      else if(props.className?.includes('reaction-item'))props={...props,disabled:true,title:'Bảo Khố chưa hỗ trợ trong demo',onClick:undefined};
      else if(React.Children.toArray(props.children).some(c=>c?.props?.children==='close'))props={...props,'aria-label':'Đóng bộ chọn reaction',onClick:()=>{setOpen(false);trigger.current?.focus()}};
    }
    return React.cloneElement(node,props,adapt(props.children));
  };
  const picker=adapt(PickerMarkup());
  return render(<div className="relative min-w-0" ref={root}>
    <div className={`flex items-center gap-1.5 flex-wrap ${compact?'':'social-post-reactions'}`}>
      {visible.map(reaction=><button type="button" key={reaction.id} className={compact?'flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container hover:bg-surface-container-high border border-surface-container-high hover:border-secondary/40 text-on-surface transition-all cursor-pointer active:scale-95':pillClass} aria-label={reaction.label} aria-pressed={selected===reaction.id} data-reaction-pill={reaction.id} onClick={()=>REACTIONS.some(r=>r.id===reaction.id)?react(reaction.id):setOpen(true)} disabled={busy}>
        {reaction.src?<img className="w-4 h-4 object-cover rounded-full" src={reaction.src} alt="meme"/>:<span>{reaction.emoji}</span>}<span className={compact?'font-mono-tag text-mono-tag text-on-surface':'font-mono-counter text-mono-counter text-on-surface'}>{reaction.count}</span>
      </button>)}
      <div className="relative flex items-center gap-1.5 shrink-0 social-reaction-actions">
        {counts.length>5&&<button type="button" className="text-secondary font-label-sm text-label-sm shrink-0" aria-label="Xem tất cả reaction" onClick={()=>setOpen(true)}>+{counts.length-5}</button>}
        <button ref={trigger} id={primary?'btn-toggle-reaction-popover':undefined} type="button" className={`flex items-center justify-center ${compact?'w-6 h-6':'w-8 h-8'} rounded-full bg-surface-container-high hover:bg-surface-container-highest text-secondary transition-all shadow-sm border border-secondary/30 active:scale-95`} aria-label={onPick?'Chèn emoji':compact?'Thả biểu cảm bình luận':'Thả biểu cảm'} aria-controls={popoverId} aria-expanded={open} onClick={()=>{setOpen(v=>!v);setError('')}}>{icon(onPick?'sentiment_satisfied':'add_reaction',compact?16:20)}</button>
        {open&&createPortal(render(<div ref={popup} id={popoverId} className="social-picker-position" style={position} role="dialog" aria-label="Bộ chọn reaction">
          {picker}
          <div className="bg-surface-container-high p-3 border border-outline-variant rounded-lg" aria-label="Tất cả reaction">
            <p className="font-label-sm text-label-sm text-on-surface-variant">{MOCK_AUTH?'Bảo Khố chưa hỗ trợ trong demo':'PLANNED — cần inventory sở hữu.'}</p>
            <div className="flex flex-wrap gap-2 mt-2">{counts.map(r=><span key={r.id} className="font-body-sm text-body-sm">{r.src?<img className="inline w-4 h-4 rounded-full" src={r.src} alt="meme"/>:r.emoji} {r.count}</span>)}</div>
            {selected&&<p className="text-secondary font-body-sm text-body-sm mt-2">{REACTIONS.find(r=>r.id===selected)?.emoji} Đã chọn</p>}
          </div>
          <SocialMessage error={error}/>
        </div>),document.getElementById('root'))}
      </div>
    </div>
    {!open&&<SocialMessage error={error}/>}
  </div>);
}
