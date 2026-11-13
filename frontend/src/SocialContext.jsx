import React,{createContext,useContext,useEffect,useRef,useState} from 'react';
import { allPosts, emptyState } from './social-model.js';
import { loadSocial,saveSocial } from './social-storage.js';
import { readDemoUser } from './demo.js';
import {MOCK_AUTH} from './auth.js';

const SocialContext=createContext(null);
export const useSocial=()=>useContext(SocialContext);
export function SocialProvider({children}) {
  const [snapshot,setSnapshot]=useState(()=>({state:emptyState(),media:{}}));
  const [ready,setReady]=useState(false),[error,setError]=useState('');
  const urls=useRef(new Map()),channel=useRef(null),active=useRef(true),loaded=useRef(false);
  const refresh=async()=>{
    const result=await loadSocial();if(!active.current)return;
    const media={};
    for(const [id,blob] of Object.entries(result.files)){
      if(!urls.current.has(id))urls.current.set(id,URL.createObjectURL(blob));
      media[id]=urls.current.get(id);
    }
    setSnapshot(previous=>result.state.revision>=previous.state.revision?{state:result.state,media}:previous);
    loaded.current=true;
    setError('');setReady(true);
  };
  useEffect(()=>{
    active.current=true;
    refresh().catch(()=>{if(active.current){setError('Không đọc được dữ liệu demo. Dữ liệu cũ chưa bị thay đổi.');setReady(true);}});
    if(typeof BroadcastChannel!=='undefined'){
      channel.current=new BroadcastChannel('aurameme-social-demo');
      channel.current.onmessage=()=>refresh().catch(()=>setError('Không đọc được dữ liệu demo. Dữ liệu cũ chưa bị thay đổi.'));
    }
    return()=>{active.current=false;channel.current?.close();for(const url of urls.current.values())URL.revokeObjectURL(url);urls.current.clear();};
  },[]);
  useEffect(()=>{document.getElementById('root').dataset.socialReady=String(ready);},[ready]);
  const commit=async(action,file)=>{
    const user=readDemoUser();if(!user)throw Error('LOGIN_REQUIRED');
    if(!MOCK_AUTH)throw Error('AUTH_DEMO_ONLY');
    if(!ready||!loaded.current)throw Error('STORAGE_FAILED');
    const next=await saveSocial(action,user.username,file);
    if(file&&!urls.current.has(action.mediaId))urls.current.set(action.mediaId,URL.createObjectURL(file));
    if(active.current)setSnapshot(previous=>next.revision>=previous.state.revision?{state:next,media:Object.fromEntries(urls.current)}:previous);
    // Once committed, a later refresh/notification failure must not turn success into a retry that duplicates a post.
    try{channel.current?.postMessage('updated')}catch{}
    refresh().catch(()=>{if(active.current)setError('Đã lưu thay đổi, nhưng chưa đồng bộ được dữ liệu hiển thị. Vui lòng tải lại.');});
  };
  return <SocialContext.Provider value={{...snapshot,posts:allPosts(snapshot.state,snapshot.media),ready,error,commit}}>{children}</SocialContext.Provider>;
}
