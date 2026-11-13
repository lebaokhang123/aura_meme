import React,{createContext,useContext,useEffect,useRef,useState} from 'react';
import { allPosts, emptyState } from './social-model.js';
import { loadSocial,saveSocial } from './social-storage.js';
import { readDemoUser } from './demo.js';
import {auth,MOCK_AUTH} from './auth.js';
import {CATEGORIES,readFilters} from './feed-data.js';
import {apiId,apiCategory,apiPost,apiComment,apiPage,apiInteractions} from './social-api.js';

const SocialContext=createContext(null);
export const useSocial=()=>useContext(SocialContext);
export function SocialProvider({children}) {
  const [snapshot,setSnapshot]=useState(()=>({state:emptyState(),media:{}}));
  const [ready,setReady]=useState(false),[error,setError]=useState('');
  const [serverPosts,setServerPosts]=useState([]),[categories,setCategories]=useState(MOCK_AUTH?CATEGORIES:[]);
  const [pagination,setPagination]=useState(null),[loading,setLoading]=useState(!MOCK_AUTH),[commentPages,setCommentPages]=useState({});
  const query=useRef(readFilters(location.search,!MOCK_AUTH)),generation=useRef(0),page=useRef(1),uploads=useRef(new WeakMap());
  const setInteraction=(target,id,value)=>setSnapshot(v=>({...v,state:{...v.state,api:true,apiInteractions:{...v.state.apiInteractions,[target]:{...v.state.apiInteractions?.[target],[id]:apiInteractions(value,id,target)}}}}));
  const readInteraction=async(target,id)=>{
    const value=await auth.read('/'+(target==='post'?'posts':'comments')+'/'+apiId(id)+'/interactions');
    setInteraction(target,id,value);return value;
  };
  const loadCategories=async()=>{
    let next=1,result=[];
    do{
      const value=apiPage(await auth.read('/categories?page_size=100&page='+next));
      result.push(...value.items.map(apiCategory));next=value.pagination.page<value.pagination.total_pages?next+1:0;
    }while(next&&active.current);
    if(active.current)setCategories(result);
    return result;
  };
  const loadFeed=async(filters=query.current,append=false)=>{
    if(MOCK_AUTH)return;
    if(!['/','/explore'].includes(location.pathname)){setReady(true);return;}
    query.current=filters;const token=++generation.current,next=append?page.current+1:1;
    setLoading(true);setError('');
    try{
      const search=new URLSearchParams({page:String(next),page_size:location.pathname==='/explore'?'3':'20',include_interactions:'true',sort:filters.sort==='hot'?'reaction_desc':'created_desc'});
      if(filters.q)search.set('search',filters.q);if(filters.category)search.set('category',filters.category);
      const result=apiPage(await auth.read('/posts?'+search)),mapped=result.items.map(apiPost);
      const target=location.hash.match(/^#post-([0-9a-f-]{36})$/i)?.[1];
      if(!append&&target&&!mapped.some(v=>v.id===target)){
        try{mapped.unshift(apiPost(await auth.read('/posts/'+apiId(target))))}catch(e){if(e.status!==404)throw e;}
      }
      const interactions=await Promise.all(mapped.map(async post=>{
        try{return [post.id,apiInteractions(post.interactions||await auth.read('/posts/'+post.id+'/interactions'),post.id,'post')]}catch(e){if(e.status===404)return null;throw e;}
      }));
      if(!active.current||token!==generation.current)return;
      const valid=Object.fromEntries(interactions.filter(Boolean));
      setServerPosts(previous=>[...new Map([...(append?previous:[]),...mapped.filter(v=>valid[v.id])].map(v=>[v.id,v])).values()]);
      setSnapshot(v=>({...v,state:{...v.state,api:true,apiInteractions:{...v.state.apiInteractions,post:{...(append?v.state.apiInteractions?.post:{}),...valid}}}}));
      page.current=next;setPagination(result.pagination);setReady(true);
    }catch(e){if(active.current&&token===generation.current){setError(e.message);setReady(true);if(e.status===401)auth.refresh().catch(()=>{});}throw e;}
    finally{if(active.current&&token===generation.current)setLoading(false)}
  };
  const loadComments=async(postId,append=false)=>{
    if(MOCK_AUTH)return;
    apiId(postId);const next=append?(commentPages[postId]?.page||1)+1:1;
    try{
      const result=apiPage(await auth.read('/posts/'+postId+'/comments?page_size=10&page='+next));
      const mapped=result.items.map(apiComment);
      const values=await Promise.all(mapped.map(async row=>{
        try{return [row.id,apiInteractions(await auth.read('/comments/'+row.id+'/interactions'),row.id,'comment')]}catch(e){if(e.status===404)return null;throw e;}
      }));
      if(!active.current)return;
      const interactions=Object.fromEntries(values.filter(Boolean));
      setSnapshot(v=>({...v,state:{...v.state,api:true,comments:[...new Map([...v.state.comments.filter(c=>append||c.postId!==postId),...mapped.filter(c=>interactions[c.id])].map(c=>[c.id,c])).values()],
        apiInteractions:{...v.state.apiInteractions,comment:{...v.state.apiInteractions?.comment,...interactions}}}}));
      setCommentPages(v=>({...v,[postId]:result.pagination}));
    }catch(e){setError(e.message);if(e.status===401)auth.refresh().catch(()=>{});throw e;}
  };
  const apiCommit=async(action,file)=>{
    if(!readDemoUser())throw Error('LOGIN_REQUIRED');
    let result;
    if(action.type==='create-post'){
      const category=categories.find(c=>c.id===action.category);if(!category)throw Error('INVALID_CATEGORY');
      if(!action.content.trim()&&!file)throw Error('INVALID_POST');
      let media_id=null;
      if(file){
        if(!uploads.current.has(file)){const data=new FormData();data.append('file',file);const media=await auth.write('POST','/media',data);uploads.current.set(file,apiId(media.id));}
        media_id=uploads.current.get(file);
      }
      result=await auth.write('POST','/posts',{request_id:apiId(action.id),content:action.content,category_id:category.apiId,media_id,status:'published'});
    }else if(action.type==='update-post'){
      const category=categories.find(c=>c.id===action.category);if(!category)throw Error('INVALID_CATEGORY');
      result=await auth.write('PATCH','/posts/'+apiId(action.id),{content:action.content,category_id:category.apiId});
    }else if(action.type==='delete-post')await auth.write('DELETE','/posts/'+apiId(action.id));
    else if(action.type==='moderate-post')await auth.write('PATCH','/admin/posts/'+apiId(action.id),{status:'hidden'});
    else if(action.type==='comment'){
      if(!action.text.trim()||action.text.length>2000)throw Error('INVALID_COMMENT');
      result=await auth.write('POST','/posts/'+apiId(action.postId)+'/comments',{request_id:apiId(action.id),body:action.text});
    }else if(action.type==='delete-comment')await auth.write('DELETE','/comments/'+apiId(action.id));
    else if(action.type==='moderate-comment')await auth.write('PATCH','/admin/comments/'+apiId(action.id),{status:'hidden'});
    else if(action.type==='react'){
      const current=snapshot.state.apiInteractions?.[action.target]?.[action.id]?.viewer_reaction;
      await auth.write(current===action.reaction?'DELETE':'PUT','/'+(action.target==='post'?'posts':'comments')+'/'+apiId(action.id)+'/reactions',current===action.reaction?undefined:{reaction_type:action.reaction});
      try{
        await readInteraction(action.target,action.id);
        if(action.target==='post'&&query.current.sort==='hot')await loadFeed();
      }catch(e){setError('Đã lưu thay đổi, nhưng chưa đồng bộ được dữ liệu hiển thị. Vui lòng tải lại.');}
      return;
    }else throw Error('INVALID_ACTION');
    if(['delete-post','moderate-post'].includes(action.type))setServerPosts(v=>v.filter(post=>post.id!==action.id));
    if(['delete-comment','moderate-comment'].includes(action.type))setSnapshot(v=>({...v,state:{...v.state,comments:v.state.comments.filter(c=>c.id!==action.id)}}));
    // A failed read after a successful write must not report that the mutation failed.
    try{
      if(['comment','delete-comment','moderate-comment'].includes(action.type)){
        const postId=action.postId||snapshot.state.comments.find(c=>c.id===action.id)?.postId;
        if(postId){await loadComments(postId);await readInteraction('post',postId);}
      }else{await loadCategories();await loadFeed();}
    }catch{setError('Đã lưu thay đổi, nhưng chưa đồng bộ được dữ liệu hiển thị. Vui lòng tải lại.');}
    return result;
  };
  const urls=useRef(new Map()),channel=useRef(null),active=useRef(true),loaded=useRef(false);
  const refresh=async()=>{
    if(!MOCK_AUTH){if(!['/','/explore'].includes(location.pathname)){setReady(true);return;}await loadCategories();return;}
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
    refresh().catch(()=>{if(active.current){setError(MOCK_AUTH?'Không đọc được dữ liệu demo. Dữ liệu cũ chưa bị thay đổi.':'Không tải được dữ liệu máy chủ. Vui lòng thử lại.');setReady(true);}});
    if(MOCK_AUTH&&typeof BroadcastChannel!=='undefined'){
      channel.current=new BroadcastChannel('aurameme-social-demo');
      channel.current.onmessage=()=>refresh().catch(()=>setError('Không đọc được dữ liệu demo. Dữ liệu cũ chưa bị thay đổi.'));
    }
    return()=>{active.current=false;channel.current?.close();for(const url of urls.current.values())URL.revokeObjectURL(url);urls.current.clear();};
  },[]);
  useEffect(()=>{document.getElementById('root').dataset.socialReady=String(ready);},[ready]);
  const commit=async(action,file)=>{
    const user=readDemoUser();if(!user)throw Error('LOGIN_REQUIRED');
    if(!MOCK_AUTH)return apiCommit(action,file);
    if(!ready||!loaded.current)throw Error('STORAGE_FAILED');
    const next=await saveSocial(action,user.username,file);
    if(file&&!urls.current.has(action.mediaId))urls.current.set(action.mediaId,URL.createObjectURL(file));
    if(active.current)setSnapshot(previous=>next.revision>=previous.state.revision?{state:next,media:Object.fromEntries(urls.current)}:previous);
    // Once committed, a later refresh/notification failure must not turn success into a retry that duplicates a post.
    try{channel.current?.postMessage('updated')}catch{}
    refresh().catch(()=>{if(active.current)setError('Đã lưu thay đổi, nhưng chưa đồng bộ được dữ liệu hiển thị. Vui lòng tải lại.');});
  };
  return <SocialContext.Provider value={{...snapshot,posts:MOCK_AUTH?allPosts(snapshot.state,snapshot.media):serverPosts,categories,pagination,loading,commentPages,loadComments,loadFeed,loadMore:()=>loadFeed(query.current,true),retry:refresh,ready,error,commit}}>{children}</SocialContext.Provider>;
}
