import React,{useEffect,useSyncExternalStore} from 'react';
import {auth,MOCK_AUTH,startAuth} from './auth.js';
import ErrorPage from './components/ErrorPage.jsx';
export function AuthBoundary({children}){
  const state=useSyncExternalStore(auth.subscribe,auth.snapshot);
  useEffect(()=>MOCK_AUTH?undefined:startAuth(),[]);
  if(MOCK_AUTH)return children;
  if(state.status==='loading')return null;
  if(state.status==='unavailable')return <ErrorPage status={503} onRetry={()=>auth.refresh().catch(()=>{})}/>;
  return children;
}
