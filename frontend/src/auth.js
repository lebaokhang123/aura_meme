import { createAuthClient } from './auth-client.js';
// Only a separately built mock bundle may use localStorage demo identity.
export const MOCK_AUTH=import.meta.env?.MODE==='mock';
let channel=null;
export const auth=createAuthClient({notify:()=>channel?.postMessage('changed')});
export function startAuth(){
  let stopped=false,pending=false;
  const check=async()=>{
    if(pending||stopped)return;pending=true;
    const before=auth.snapshot().user?.id??null;
    try{
      await auth.refresh();
      if(!stopped&&before!==(auth.snapshot().user?.id??null))location.reload();
    }catch{}finally{pending=false;}
  };
  const resumed=()=>{if(document.visibilityState==='visible')check();};
  auth.refresh().catch(()=>{});
  if(typeof BroadcastChannel!=='undefined'){channel=new BroadcastChannel('aurameme-auth');channel.onmessage=check;}
  window.addEventListener('focus',resumed);document.addEventListener('visibilitychange',resumed);
  return()=>{stopped=true;channel?.close();channel=null;window.removeEventListener('focus',resumed);document.removeEventListener('visibilitychange',resumed);};
}
