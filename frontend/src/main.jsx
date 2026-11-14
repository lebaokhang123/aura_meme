import React,{useEffect,useSyncExternalStore} from 'react';
import {createRoot} from 'react-dom/client';
import { resolveScreen, initLegacyEffects, attachNavigation, prepareAuthForm, showDemoMessage } from './runtime.js';
import {AuthBoundary} from './AuthBoundary.jsx';
import {auth,MOCK_AUTH} from './auth.js';
import {authMessage} from './auth-client.js';
import {ProfilePage,ContactPage,VaultPage,ContactInbox} from './components/AccountPages.jsx';
import './account-pages.css';
import {loginUrl} from './return-url.js';
import {usePreferences} from './PreferencesContext.jsx';
import { applyDemoIdentity } from './demo.js';
import { SiteHeader, SiteFooter, MaintenancePage } from './components/SiteShell.jsx';
import './mobile.css';
import './site.css';
import { FeedProvider } from './FeedContext.jsx';
import { PreferencesProvider } from './PreferencesContext.jsx';
import { applyPreferences, readPreferences } from './preferences.js';
import { LocalizedPage, useLocalized } from './localize.jsx';
import './preferences-theme.css';
import { SocialProvider } from './SocialContext.jsx';
import './social.css';
const pages=import.meta.glob('./generated/*.js');
const cssFiles=import.meta.glob('./generated/*.css',{query:'?raw',import:'default'});
const effectsFiles=import.meta.glob('./generated/*.effects.json');

function App() {
  const render = useLocalized();
  const authState=useSyncExternalStore(auth.subscribe,auth.snapshot);
  const {language}=usePreferences();
  const page = resolveScreen();
  const [screen,setScreen] = React.useState(null);
  const [failed,setFailed] = React.useState(false);
  useEffect(() => {
    let active=true;
    document.body.className=page.bodyClass;
    document.body.dataset.screen=page.key;
    const style=document.createElement('style');style.id='stitch-active-styles';
    const custom=!MOCK_AUTH&&(page.path.startsWith('/profile')?ProfilePage:page.path==='/contact'?ContactPage:page.path==='/vault'?VaultPage:page.path==='/admin/contacts'?ContactInbox:null);
    const maintenance=page.path==='/rank'||MOCK_AUTH&&['/contact','/vault'].includes(page.path);
    const pageLoader=custom?Promise.resolve(custom):maintenance ? Promise.resolve(MaintenancePage) : pages[`./generated/${page.key}.js`]().then(mod=>mod.default);
    const cssLoader=cssFiles[`./generated/${page.key}.css`]();
    // Mount with its own CSS ready, avoiding an unstyled frame during navigation.
    Promise.all([pageLoader,cssLoader]).then(([component,css])=>{
      if(!active)return;
      style.textContent=css;document.head.appendChild(style);setScreen(()=>component);
    }).catch(()=>{if(active)setFailed(true)});
    return () => {active=false;style.remove()};
  },[page.key]);
  useEffect(() => {
    if(!screen)return;
    applyDemoIdentity();
    if(!MOCK_AUTH&&!['/','/explore','/about','/login','/register','/rank'].includes(page.path))return;
    let stopped=false;let cleanup=()=>{};
    const loader=effectsFiles[`./generated/${page.key}.effects.json`]; if(loader&&!['/','/explore'].includes(page.path))loader().then(mod=>{
      if(stopped)return;cleanup=initLegacyEffects(mod.default);
    });
    return()=>{stopped=true;cleanup()};
  },[page.key,screen]);
  useEffect(()=>attachNavigation(),[]);
  useEffect(()=>{if(!MOCK_AUTH&&screen&&page.path==='/login'&&new URLSearchParams(location.search).has('registered'))showDemoMessage(language==='en'?'Account created. Please sign in.':'Đăng ký thành công. Vui lòng đăng nhập.');},[screen]);
  useEffect(()=>{if(screen)prepareAuthForm();},[screen,language]);
  useEffect(()=>{if(!MOCK_AUTH&&authState.error)showDemoMessage(authMessage(authState.error,language));},[authState.error]);
  const protectedPage=['/contact','/vault','/admin/contacts','/profile'].includes(page.path);
  useEffect(()=>{if(!MOCK_AUTH&&protectedPage&&authState.status==='guest')location.replace(loginUrl());},[protectedPage,authState.status]);
  if(!MOCK_AUTH&&protectedPage&&authState.status!=='authenticated')return null;
  // Reveal the header and page together after the lazy content and CSS are ready.
  if(!screen&&!failed)return null;
  return render(<><SiteHeader />{failed ? <main role="alert">Không tải được trang. <button type="button" onClick={()=>location.reload()}>Tải lại</button></main> : screen===MaintenancePage ? <MaintenancePage /> : [ProfilePage,ContactPage,VaultPage,ContactInbox].includes(screen)?React.createElement(screen):<LocalizedPage component={screen} />}{page.path==='/' ? null : <SiteFooter />}</>);
}

applyPreferences(readPreferences());
createRoot(document.getElementById('root')).render(<PreferencesProvider><AuthBoundary><SocialProvider><FeedProvider><App /></FeedProvider></SocialProvider></AuthBoundary></PreferencesProvider>);
