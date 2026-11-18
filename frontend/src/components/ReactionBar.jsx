import {MOCK_AUTH} from '../auth.js';
import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {REACTIONS,reactionCounts} from '../social-model.js';
import {useSocial} from '../SocialContext.jsx';
import {readDemoUser} from '../demo.js';
import {useCopy} from './account-ui.jsx';
import {useLocalized} from '../localize.jsx';
import {icon,pillClass,SocialMessage} from './social-ui.jsx';
import {PickerMarkup} from '../generated/social-stitch.jsx';

export function ReactionBar({target='post',id,compact=false,onPick}) {
  const t=useCopy(),render=useLocalized(),{state,commit,ready,loadOwnedMemes}=useSocial(),user=readDemoUser();
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const root=useRef(null),trigger=useRef(null),popup=useRef(null),pending=useRef(false);
  const [position,setPosition]=useState({left:16,top:90,width:340});
  const [ownedTab,setOwnedTab]=useState(false),[owned,setOwned]=useState([]),[ownedPage,setOwnedPage]=useState(null),[ownedLoading,setOwnedLoading]=useState(false),[ownedError,setOwnedError]=useState('');
  const ownedGeneration=useRef(0),ownedPending=useRef(false);
  const records=target==='post'?state.postReactions:state.commentReactions;
  const interaction=state.apiInteractions?.[target]?.[id];
  const selected=onPick?undefined:state.api?(user?(interaction?.viewer_meme_asset_id?'meme-'+interaction.viewer_meme_asset_id:interaction?.viewer_reaction):null):records[id]?.[user?.username];
  const counts=onPick?[]:[...reactionCounts(state,target,id),...(state.api?interaction?.meme_reactions||[]:[]).map(({asset,count})=>({id:'meme-'+asset.id,assetId:asset.id,label:asset.display_name,src:asset.image,count}))];
  const visible=counts.length>5?[...counts].sort((a,b)=>b.count-a.count).slice(0,5):counts;
  const primary=target==='post'&&id==='khang';
  const popoverId=primary?'reaction-popover':`reaction-${target}-${id}`;
  const loadOwned=async(next=1)=>{
    if(ownedPending.current)return;ownedPending.current=true;
    const token=ownedGeneration.current;setOwnedLoading(true);setOwnedError('');
    try{
      const result=await loadOwnedMemes(next);
      if(token!==ownedGeneration.current)return;
      setOwned(previous=>[...new Map([...(next===1?[]:previous),...result.items].map(row=>[row.asset.id,row])).values()]);setOwnedPage(result.pagination);
    }catch(e){if(token===ownedGeneration.current)setOwnedError(e.message)}
    finally{if(token===ownedGeneration.current){ownedPending.current=false;setOwnedLoading(false)}}
  };
  useEffect(()=>{
    ownedGeneration.current++;ownedPending.current=false;
    if(open&&ownedTab&&!MOCK_AUTH&&!onPick&&user){setOwned([]);setOwnedPage(null);loadOwned(1);}
    return()=>{ownedGeneration.current++;ownedPending.current=false;};
  },[open,ownedTab,user?.id]);
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
  },[open,ownedTab,owned.length,ownedLoading]);
  const react=async(reaction,memeAssetId)=>{
    if(pending.current)return;pending.current=true;setBusy(true);setError('');
    try{if(onPick){if(!user)throw Error('LOGIN_REQUIRED');onPick(REACTIONS.find(r=>r.id===reaction).emoji);}else await commit({type:'react',target,id,reaction,...(memeAssetId?{memeAssetId}:{})});setOpen(false);}catch(e){setError(e.message)}finally{pending.current=false;setBusy(false)}
  };
  const pickPill=reaction=>{
    if(reaction.assetId){
      if(selected===reaction.id)return react('meme',reaction.assetId);
      setOwnedTab(true);setOpen(true);
    }else if(REACTIONS.some(r=>r.id===reaction.id))react(reaction.id);
    else setOpen(true);
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
  const picker=MOCK_AUTH?adapt(PickerMarkup()):<div className="bg-surface-container border border-outline-variant rounded-xl p-3 shadow-xl">
    <div className="flex items-center justify-between gap-2 mb-3"><p className="font-label-sm text-label-sm">{onPick?'Chèn emoji':'Thả biểu cảm'}</p><button type="button" aria-label="Đóng bộ chọn reaction" onClick={()=>{setOpen(false);trigger.current?.focus()}}>{icon('close',18)}</button></div>
    {!onPick&&<div className="flex gap-2 mb-3" role="group" aria-label={t("Loại biểu cảm","Reaction type")}><button type="button" className={pillClass} aria-pressed={!ownedTab} onClick={()=>setOwnedTab(false)}>Biểu cảm</button><button type="button" className={pillClass} aria-pressed={ownedTab} onClick={()=>setOwnedTab(true)}>{t("Meme của tôi","My memes")}</button></div>}
    {(!ownedTab||onPick)?<div className="flex justify-between gap-1">{REACTIONS.map(option=><button key={option.id} type="button" className="p-2 rounded-lg hover:bg-surface-container-high text-xl" data-reaction={option.id} aria-label={option.label} aria-pressed={selected===option.id} disabled={busy||!ready} onClick={()=>react(option.id)}>{option.emoji}</button>)}</div>:<div aria-label={t("Meme đã sở hữu","Owned memes")} aria-busy={ownedLoading}>
      {!user?<p className="font-body-sm text-body-sm"><a href="/login" className="text-secondary underline">{t("Đăng nhập","Sign in")}</a>{t(" để chọn Meme đã sở hữu."," to choose owned memes.")}</p>:<>
        <p className="font-body-sm text-body-sm text-on-surface-variant mb-2">{t("Dùng Meme trong kho, không tiêu hao số lượng.","Using owned memes does not consume quantity.")}</p>
        <div className="grid grid-cols-3 gap-2">{owned.map(({asset,quantity})=><button key={asset.id} type="button" className="min-w-0 p-2 rounded-lg bg-surface-container-high border border-outline-variant hover:border-secondary" data-owned-meme={asset.id} aria-label={t('Thả Meme ','React with Meme ')+asset.display_name} aria-pressed={selected==='meme-'+asset.id} disabled={busy||!ready} onClick={()=>react('meme',asset.id)}><img className="w-full h-16 object-contain rounded" src={asset.image} alt="" loading="lazy"/><span className="block text-xs break-words mt-1">{asset.display_name}</span><span className="block text-xs text-on-surface-variant">×{quantity}</span></button>)}</div>
        {ownedLoading&&<p role="status" className="font-body-sm text-body-sm mt-2">{t("Đang tải kho Meme…","Loading owned memes…")}</p>}
        {!ownedLoading&&!ownedError&&ownedPage&&!owned.length&&<p className="font-body-sm text-body-sm mt-2">{ownedPage.total_pages<=1?t("Bạn chưa sở hữu Meme nào.","You do not own any memes yet."):t("Trang này chưa có Meme phù hợp. Xem tiếp kho của bạn.","No matching memes on this page. Continue browsing your inventory.")}</p>}
        {ownedPage&&ownedPage.page<ownedPage.total_pages&&<button type="button" className="text-secondary underline font-body-sm text-body-sm mt-3" disabled={ownedLoading||busy} onClick={()=>loadOwned(ownedPage.page+1)}>{t("Xem thêm Meme","Load more memes")}</button>}
        {ownedError&&<><SocialMessage error={ownedError} read/><button type="button" className="text-secondary underline mt-2" disabled={ownedLoading} onClick={()=>loadOwned(ownedPage?ownedPage.page+1:1)}>{t("Thử tải kho lại","Retry inventory")}</button></>}
      </>}
    </div>}
  </div>;
  return render(<div className="relative min-w-0" ref={root}>
    <div className={`flex items-center gap-1.5 flex-wrap ${compact?'':'social-post-reactions'}`}>
      {visible.map(reaction=><button type="button" key={reaction.id} className={compact?'flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-container hover:bg-surface-container-high border border-surface-container-high hover:border-secondary/40 text-on-surface transition-all cursor-pointer active:scale-95':pillClass} aria-label={reaction.label} aria-pressed={selected===reaction.id} data-reaction-pill={reaction.id} onClick={()=>pickPill(reaction)} disabled={busy}>
        {reaction.src?<img className="w-4 h-4 object-cover rounded-full" src={reaction.src} alt=""/>:<span>{reaction.emoji}</span>}<span className={compact?'font-mono-tag text-mono-tag text-on-surface':'font-mono-counter text-mono-counter text-on-surface'}>{reaction.count}</span>
      </button>)}
      <div className="relative flex items-center gap-1.5 shrink-0 social-reaction-actions">
        {counts.length>5&&<button type="button" className="text-secondary font-label-sm text-label-sm shrink-0" aria-label="Xem tất cả reaction" onClick={()=>setOpen(true)}>+{counts.length-5}</button>}
        <button ref={trigger} id={primary?'btn-toggle-reaction-popover':undefined} type="button" className={`flex items-center justify-center ${compact?'w-6 h-6':'w-8 h-8'} rounded-full bg-surface-container-high hover:bg-surface-container-highest text-secondary transition-all shadow-sm border border-secondary/30 active:scale-95`} aria-label={onPick?'Chèn emoji':compact?'Thả biểu cảm bình luận':'Thả biểu cảm'} aria-controls={popoverId} aria-expanded={open} onClick={()=>{setOpen(v=>!v);setError('')}}>{icon(onPick?'sentiment_satisfied':'add_reaction',compact?16:20)}</button>
        {open&&createPortal(render(<div ref={popup} id={popoverId} className="social-picker-position" style={position} role="dialog" aria-label="Bộ chọn reaction">
          {picker}
          {(MOCK_AUTH||counts.length>0||selected)&&<div className="bg-surface-container-high p-3 border border-outline-variant rounded-lg" aria-label="Tất cả reaction">
            {MOCK_AUTH&&<p className="font-label-sm text-label-sm text-on-surface-variant">Bảo Khố chưa hỗ trợ trong demo</p>}
            <div className="flex flex-wrap gap-2 mt-2">{counts.map(r=><span key={r.id} className="font-body-sm text-body-sm">{r.src?<img className="inline w-4 h-4 rounded-full" src={r.src} alt="meme"/>:r.emoji} {r.count}</span>)}</div>
            {selected&&<p className="text-secondary font-body-sm text-body-sm mt-2">{REACTIONS.find(r=>r.id===selected)?.emoji||counts.find(r=>r.id===selected)?.label} Đã chọn</p>}
          </div>}
          <SocialMessage error={error}/>
        </div>),document.getElementById('root'))}
      </div>
    </div>
    {!open&&<SocialMessage error={error}/>}
  </div>);
}
