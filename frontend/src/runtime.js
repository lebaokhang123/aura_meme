// Small React host around the exact Stitch visual exports. No legacy frontend dependencies.
import { USER_KEY, readDemoUser, identifyDemoUser } from './demo.js';
import { readPreferences, translate } from './preferences.js';
import {auth,MOCK_AUTH} from './auth.js';
import {authMessage} from './auth-client.js';
import {safeReturnUrl} from './return-url.js';
const ROUTES = {'trang-chu':'/','kham-pha':'/explore','gioi-thieu':'/about','lien-he':'/contact','xep-hang':'/rank','bao-kho':'/vault','dang-nhap':'/login','dang-ky':'/register'};
const PAGE = {'/':'home','/explore':'explore','/about':'about','/contact':'contact','/rank':'rank','/vault':'vault','/admin':'about','/premium':'about','/premium/checkout':'about','/premium/history':'about','/forgot-password':'about','/reset-password':'about','/verify-email':'about'};
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
export function showDemoMessage(message){
 let toast=document.getElementById('aura-demo-toast');
 if(!toast){toast=document.createElement('div');toast.id='aura-demo-toast';toast.setAttribute('role','alert');toast.style.cssText='position:fixed;bottom:16px;right:16px;z-index:9999;background:#272231;color:#e3e1ed;padding:12px 16px;border:1px solid #a078ff;border-radius:12px;font:13px Inter, sans-serif;box-shadow:0 12px 35px #0008;max-width:300px';document.body.appendChild(toast)}
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
    if(txt.includes('đăng xuất')||txt.includes('logout')){ev.preventDefault();logoutAccount();return}
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
   if(ev.target.dataset.lucianSubmit)return;
   ev.preventDefault();ev.stopPropagation();
   if(!MOCK_AUTH){submitApiForm(ev.target);return;}
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

const pendingForms=new WeakSet();
export function prepareAuthForm(){
 if(MOCK_AUTH)return;
 const form=document.getElementById('loginForm');if(!form)return;
 if(form.dataset.lucianSubmit)return;
 const lang=readPreferences().language;
 const isEn=lang==='en';
 const password=form.querySelector('#password');if(password)password.maxLength=128;
 if(location.pathname==='/register'){
  if(password){password.minLength=12;password.placeholder=isEn?'12–128 characters':'12–128 ký tự';}
  const username=form.querySelector('#username');if(username){username.minLength=3;username.maxLength=32;username.pattern='[A-Za-z0-9_]{3,32}';}
 }
 // Wire existing "Quên mật khẩu?" link on /login (or inject only if absent)
 if(location.pathname==='/login'){
  const existingForgot=Array.from(form.querySelectorAll('a')).find(a=>/quên mật khẩu|forgot password/i.test(a.textContent||''));
  if(existingForgot){
   existingForgot.href='/forgot-password';
   existingForgot.dataset.forgotPasswordLink='1';
  }else if(!form.querySelector('[data-forgot-password-link]')){
   const submit=form.querySelector('[type="submit"]');
   if(submit){
    const wrap=document.createElement('div');
    wrap.style.cssText='display:flex;justify-content:flex-end;margin:-4px 0 6px;';
    const link=document.createElement('a');
    link.href='/forgot-password';
    link.dataset.forgotPasswordLink='1';
    link.textContent=isEn?'Forgot password?':'Quên mật khẩu?';
    link.style.cssText='font-size:12.5px;color:var(--am-secondary,#d0bcff);text-decoration:none;';
    wrap.appendChild(link);
    submit.parentElement.insertBefore(wrap,submit);
   }
  }
 }
 // Wire existing Google button on /login or /register (or inject only if absent)
 if(['/login','/register'].includes(location.pathname)){
  const container=form.parentElement||form;
  const existingGoogle=Array.from(container.querySelectorAll('button')).find(b=>/google/i.test(b.textContent||'')&&!b.dataset.googleAuthButton);
  const attachGoogleHandler=(btn)=>{
   if(btn.dataset.googleWired)return;
   btn.dataset.googleWired='1';
   btn.dataset.googleAuthButton='1';
   const span=btn.querySelector('span');
   if(span&&/^google$/i.test(span.textContent.trim())){
    span.textContent=isEn?'Continue with Google':'Tiếp tục với Google';
   }
   btn.addEventListener('click',async(ev)=>{
    ev.preventDefault();
    btn.disabled=true;
    try{
     const cfg=await auth.googleConfig();
     if(!cfg?.enabled||!cfg?.client_id){
      showDemoMessage(isEn?'Google sign-in is not configured on this server yet.':'Đăng nhập Google chưa được cấu hình trên máy chủ.');
      return;
     }
     if(!window.google?.accounts?.id){
      await new Promise((resolve,reject)=>{
       const s=document.createElement('script');
       s.src='https://accounts.google.com/gsi/client';s.async=true;s.defer=true;
       s.onload=resolve;s.onerror=reject;document.head.appendChild(s);
      });
     }
     const nonce=crypto.randomUUID();
     window.google.accounts.id.initialize({
      client_id:cfg.client_id,
      nonce,
      callback:async(resp)=>{
       try{
        const res=await auth.googleLogin(resp.credential,nonce);
        if(res?.status==='needs_onboarding'){
         window.dispatchEvent(new CustomEvent('aurameme-google-onboarding',{detail:res}));
         return;
        }
        location.assign(safeReturnUrl(new URLSearchParams(location.search).get('next')));
       }catch(err){showDemoMessage(authMessage(err,readPreferences().language));}
      },
     });
     window.google.accounts.id.prompt();
    }catch(err){showDemoMessage(authMessage(err,readPreferences().language));}
    finally{btn.disabled=false;}
   });
  };
  if(existingGoogle){
   attachGoogleHandler(existingGoogle);
  }else if(!container.querySelector('[data-google-auth-button]')){
   const submit=form.querySelector('[type="submit"]');
   if(submit){
    const wrap=document.createElement('div');
    wrap.dataset.googleAuthWrap='1';
    wrap.style.cssText='margin-top:12px;display:flex;flex-direction:column;gap:10px;';
    const divider=document.createElement('div');
    divider.style.cssText='display:flex;align-items:center;gap:10px;font-size:11.5px;color:var(--am-outline,#948f9a);';
    divider.innerHTML=`<span style="flex:1;height:1px;background:var(--am-outline-variant,#49454f);"></span><span>${isEn?'or':'hoặc'}</span><span style="flex:1;height:1px;background:var(--am-outline-variant,#49454f);"></span>`;
    const btn=document.createElement('button');
    btn.type='button';
    btn.style.cssText='width:100%;min-height:42px;padding:8px 14px;border-radius:10px;border:1px solid var(--am-outline-variant,#49454f);background:var(--am-surface-container,#1e1f27);color:var(--am-on-surface,#e3e1ed);font:600 13px/18px Inter,sans-serif;display:inline-flex;align-items:center;justify-content:center;gap:10px;cursor:pointer;';
    btn.innerHTML=`<svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.6 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z"/></svg><span>${isEn?'Continue with Google':'Tiếp tục với Google'}</span>`;
    attachGoogleHandler(btn);
    wrap.appendChild(divider);wrap.appendChild(btn);
    submit.insertAdjacentElement('afterend',wrap);
   }
  }
 }
}
async function submitApiForm(form){
 if(pendingForms.has(form))return;pendingForms.add(form);
 const button=form.querySelector('[type="submit"]');if(button)button.disabled=true;
 const lang=readPreferences().language;
 const isEn=lang==='en';
 const setErr=(id,msg)=>{
  const el=document.getElementById(id);
  if(el)el.textContent=msg||'';
 };
 const clearErrors=()=>{
  form.querySelectorAll('.error-hint').forEach(el=>el.textContent='');
 };
 try{
  clearErrors();
  if(location.pathname==='/register'){
   const displayNameEl=form.querySelector('#displayName')||form.querySelector('#username');
   const usernameEl=form.querySelector('#username');
   const emailEl=form.querySelector('#identifier');
   const passEl=form.querySelector('#password');
   const confirmEl=form.querySelector('#confirmPassword');

   const displayName=(displayNameEl?.value||'').trim();
   const rawTag=(usernameEl?.value||'').trim();
   const cleanTag=rawTag.startsWith('@')?rawTag.slice(1).trim().toLowerCase():rawTag.toLowerCase();
   const email=(emailEl?.value||'').trim().toLowerCase();
   const password=passEl?.value||'';
   const confirm=confirmEl?.value||'';

   let hasErr=false;
   if(!displayName){
    setErr('err-displayName',isEn?'Display name is required.':'Vui lòng nhập tên hiển thị.');
    if(!hasErr){displayNameEl?.focus();hasErr=true;}
   }
   if(!cleanTag||!/^[a-z0-9_]{3,32}$/.test(cleanTag)){
    setErr('err-username',isEn?'Tag must be 3–32 letters, numbers or underscores.':'Tag phải từ 3 đến 32 ký tự chữ, số hoặc gạch dưới (ví dụ: @khang_dev).');
    if(!hasErr){usernameEl?.focus();hasErr=true;}
   }
   if(!email||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){
    setErr('err-identifier',isEn?'Please enter a valid email address.':'Email không hợp lệ (ví dụ: user@example.com).');
    if(!hasErr){emailEl?.focus();hasErr=true;}
   }
   if(password.length<12||password.length>128){
    setErr('err-password',isEn?'Password must be 12–128 characters.':'Mật khẩu phải từ 12 đến 128 ký tự.');
    if(!hasErr){passEl?.focus();hasErr=true;}
   }
   if(confirm!==password){
    setErr('err-confirmPassword',isEn?'Passwords do not match.':'Mật khẩu xác nhận không khớp.');
    if(!hasErr){confirmEl?.focus();hasErr=true;}
   }
   if(hasErr){
    showDemoMessage(isEn?'Please fix the errors below.':'Vui lòng kiểm tra lại các thông tin bên dưới.');
    return;
   }
   try{
    const regRes = await auth.register({email,password,username:cleanTag,display_name:displayName});
    if(regRes?.status==='pending_verification'){
     try {
      sessionStorage.setItem('aurameme_last_registered_email', email);
      sessionStorage.setItem('aurameme_verify_cooldown_' + email.toLowerCase(), (Date.now() + 30000).toString());
     } catch {}
     location.assign('/login?pending_verification='+encodeURIComponent(email));
     return;
    }
    location.assign('/login?registered=1');
   }catch(error){
    const msg=authMessage(error,lang);
    if(error.code==='USERNAME_EXISTS'||/tag|username/i.test(error.message||'')){
     setErr('err-username',msg);
     usernameEl?.focus();
    }else if(error.code==='EMAIL_EXISTS'||/email/i.test(error.message||'')){
     setErr('err-identifier',msg);
     emailEl?.focus();
    }else if(/password/i.test(error.message||'')){
     setErr('err-password',msg);
     passEl?.focus();
    }
    showDemoMessage(msg);
   }
  }else{
   const email=form.querySelector('#identifier').value.trim(),password=form.querySelector('#password').value;
   await auth.login(email,password);
   location.assign(safeReturnUrl(new URLSearchParams(location.search).get('next')));
  }
 }catch(error){showDemoMessage(authMessage(error,lang));}
 finally{pendingForms.delete(form);if(button)button.disabled=false;}
}
export async function logoutAccount(button){
 if(button?.disabled)return;if(button)button.disabled=true;
 try{
  if(MOCK_AUTH)localStorage.removeItem(USER_KEY);else await auth.logout();
  location.assign('/');
 }catch(error){
  if(error.status===401){await auth.refresh().catch(()=>{});location.assign('/');}
  else showDemoMessage(authMessage(error,readPreferences().language));
 }finally{if(button)button.disabled=false;}
}
