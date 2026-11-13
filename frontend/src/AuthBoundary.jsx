import React,{useEffect,useSyncExternalStore} from 'react';
import {auth,MOCK_AUTH,startAuth} from './auth.js';
import {authMessage} from './auth-client.js';
import {usePreferences} from './PreferencesContext.jsx';
export function AuthBoundary({children}){
  const state=useSyncExternalStore(auth.subscribe,auth.snapshot),{language}=usePreferences();
  useEffect(()=>MOCK_AUTH?undefined:startAuth(),[]);
  if(MOCK_AUTH)return children;
  if(state.status==='loading')return null;
  if(state.status==='unavailable')return <main role="alert" className="min-h-screen grid place-content-center gap-4 bg-background text-on-surface p-8"><p>{authMessage(state.error,language)}</p><button type="button" onClick={()=>auth.refresh().catch(()=>{})}>{language==='en'?'Try again':'Thử lại'}</button></main>;
  return children;
}
