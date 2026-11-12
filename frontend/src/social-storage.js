import { emptyState, reduceSocial, validateState, repairDemoComments } from './social-model.js';
import {validateImage} from './social-files.js';

export const SOCIAL_DB='aurameme-social-demo-v1';
let connection;
function open() {
  if(connection)return connection;
  connection=new Promise((resolve,reject)=>{
    const request=indexedDB.open(SOCIAL_DB,1);
    request.onupgradeneeded=()=>{const db=request.result;db.createObjectStore('state');db.createObjectStore('media');};
    request.onerror=()=>reject(Error('STORAGE_FAILED'));
    request.onblocked=()=>reject(Error('STORAGE_BLOCKED'));
    request.onsuccess=()=>{const db=request.result;db.onversionchange=()=>{db.close();connection=null;};resolve(db);};
  }).catch(error=>{connection=null;throw error});
  return connection;
}
export async function loadSocial() {
  const db=await open();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction(['state','media'],'readwrite'),request=tx.objectStore('state').get('current');
    let state,files={};
    request.onsuccess=()=>{try{const previous=request.result?validateState(request.result):emptyState();state=repairDemoComments(previous);if(!request.result||state!==previous)tx.objectStore('state').put(state,'current');}catch(error){tx.abort();}};
    tx.objectStore('media').openCursor().onsuccess=event=>{const cursor=event.target.result;if(cursor){files[cursor.key]=cursor.value;cursor.continue();}};
    tx.oncomplete=()=>{if(state.posts.some(post=>post.mediaId&&!(files[post.mediaId] instanceof Blob))){reject(Error('STORAGE_FAILED'));return;}resolve({state,files});};
    tx.onabort=tx.onerror=()=>reject(Error('STORAGE_FAILED'));
  });
}
export async function saveSocial(action,user,file) {
  if(file){if(action.type!=='create-post'||action.mediaType!==file.type)throw Error('INVALID_FILE');await validateImage(file);}
  const db=await open();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction(['state','media'],'readwrite'),request=tx.objectStore('state').get('current');
    let state,reason;
    request.onsuccess=()=>{
      try{
        const previous=request.result?validateState(request.result):emptyState();
        if(action.type==='create-post'&&!!action.mediaId!==!!file)throw Error('INVALID_FILE');
        state=reduceSocial(previous,action,user);
        tx.objectStore('state').put(state,'current');
        if(file)tx.objectStore('media').put(file,action.mediaId);
      }catch(error){reason=error;tx.abort();}
    };
    // A successful request is not enough: acknowledge only the committed transaction.
    tx.oncomplete=()=>resolve(state);
    tx.onabort=tx.onerror=()=>reject(reason||Error('STORAGE_FAILED'));
  });
}
