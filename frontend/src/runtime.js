// Small React host around the exact Stitch visual exports. No legacy frontend dependencies.
import { USER_KEY, readDemoUser, identifyDemoUser } from './demo.js';
import { readPreferences, translate } from './preferences.js';
const ROUTES = {'trang-chu':'/','kham-pha':'/explore','gioi-thieu':'/about','lien-he':'/contact','xep-hang':'/rank','bao-kho':'/vault','dang-nhap':'/login','dang-ky':'/register'};
const PAGE = {'/':'home','/explore':'explore','/about':'about','/contact':'contact','/rank':'rank','/vault':'vault'};
const PAGE_BODY_CLASS = {"guest-home": "bg-surface font-body-md text-on-surface antialiased selection:bg-secondary-container selection:text-on-secondary-container", "guest-explore": "bg-background font-body-md text-body-md text-on-surface antialiased", "guest-about": "bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col justify-between selection:bg-secondary-container selection:text-on-secondary-container", "guest-contact": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "guest-rank": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "guest-vault": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "user-home": "bg-surface font-body-md text-on-surface antialiased selection:bg-secondary-container selection:text-on-secondary-container", "user-explore": "bg-background font-body-md text-body-md text-on-surface antialiased", "user-about": "bg-surface font-body-md text-on-surface antialiased min-h-screen flex flex-col justify-between selection:bg-secondary-container selection:text-on-secondary-container", "user-contact": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "user-rank": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "user-vault": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "login": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col", "register": "bg-background font-body-md text-body-md text-on-surface antialiased min-h-screen flex flex-col"};
export function resolveScreen(){
 const path=location.pathname.replace(/\/$/,'')||'/';
 const authed=readDemoUser()!==null;
 const key=path==='/login'?'login':path==='/register'?'register':(authed?'user':'guest')+'-'+(PAGE[path]||'home');
 return {key,bodyClass:PAGE_BODY_CLASS[key],authed,path};
}
export function initLegacyEffects(scripts){
 // Execute scripts from user-provided Stitch HTML at the original DOM position.
 // No eval, iframe, or old frontend dependency. Script elements are temporary.
 scripts.forEach((content,i)=>{
   const slot=document.querySelector(`[data-stitch-script-slot="${i}"]`);
   if(!slot)return;
   const el=document.createElement('script');el.text=content;slot.parentElement.insertBefore(el,slot);el.remove();
 });
 return ()=>{}; // Route navigation causes full reload, so native listeners are disposed by browser.
}
function showDemoMessage(message){
 let toast=document.getElementById('aura-demo-toast');
 if(!toast){toast=document.createElement('div');toast.id='aura-demo-toast';toast.style.cssText='position:fixed;bottom:16px;right:16px;z-index:9999;background:#272231;color:#e3e1ed;padding:12px 16px;border:1px solid #a078ff;border-radius:12px;font:13px Inter, sans-serif;box-shadow:0 12px 35px #0008;max-width:300px';document.body.appendChild(toast)}
 toast.textContent=translate(message,readPreferences().language);setTimeout(()=>toast.remove(),3300);
}
export function attachNavigation(){
 function onClick(ev){
  if(ev.defaultPrevented||ev.button!==0||ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.altKey)return;
  const a=ev.target.closest('a');
  if(a){
   const dataPath=a.getAttribute('data-path');
   if(dataPath && ROUTES[dataPath] && a.getAttribute('href')==='#'){ev.preventDefault();location.assign(ROUTES[dataPath]);return}
   if(a.getAttribute('href')==='#'){
    const txt=(a.textContent||'').trim().toLowerCase();
    if(txt.includes('đăng xuất')||txt.includes('logout')){ev.preventDefault();localStorage.removeItem(USER_KEY);location.assign('/');return}
    if(txt.includes('đăng nhập')||txt.includes('log in')){ev.preventDefault();location.assign('/login');return}
    if(txt.includes('đăng ký')||txt.includes('register')){ev.preventDefault();location.assign('/register');return}
   }
  }
  const btn=ev.target.closest('button');
  if(btn && !btn.form){
    const txt=(btn.textContent||'').trim().toLowerCase();
    if(txt.includes('đăng nhập')||txt.includes('log in')){ev.preventDefault();location.assign('/login');return}
    if(txt.includes('đăng ký')||txt.includes('register')){ev.preventDefault();location.assign('/register');return}
  }
 }
 function onSubmit(ev){
   if(!['/login','/register'].includes(location.pathname))return;
   if(ev.target.id!=='loginForm')return;
   ev.preventDefault();ev.stopPropagation();
   const id=document.getElementById('identifier')?.value||'';
   const password=document.getElementById('password')?.value||'';
   if(!id.trim()||!password.trim()){showDemoMessage('Vui lòng nhập đủ thông tin demo.');return}
   if(location.pathname==='/register'){
     const confirm=document.getElementById('confirmPassword')?.value;
     if(confirm !== password){showDemoMessage('Mật khẩu xác nhận không khớp.');return}
   }
   // This is explicitly frontend-only: never store the password or claim real authentication.
   const {displayName,username}=identifyDemoUser(id);
   try {localStorage.setItem(USER_KEY,JSON.stringify({displayName,username}));}
   catch {showDemoMessage('Không lưu được phiên demo. Vui lòng cho phép lưu trữ trình duyệt.');return}
   setTimeout(()=>location.assign('/'),160);
 }
 document.addEventListener('click',onClick,true);
 document.addEventListener('submit',onSubmit,true);
 return()=>{document.removeEventListener('click',onClick,true);document.removeEventListener('submit',onSubmit,true)};
}
