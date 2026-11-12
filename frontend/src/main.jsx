import React,{useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import { resolveScreen, initLegacyEffects, attachNavigation } from './runtime.js';
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
  const page = resolveScreen();
  const [screen,setScreen] = React.useState(null);
  const [failed,setFailed] = React.useState(false);
  useEffect(() => {
    let active=true;
    document.body.className=page.bodyClass;
    document.body.dataset.screen=page.key;
    const style=document.createElement('style');style.id='stitch-active-styles';
    const maintenance=['/contact','/rank','/vault'].includes(page.path);
    const pageLoader=maintenance ? Promise.resolve(MaintenancePage) : pages[`./generated/${page.key}.js`]().then(mod=>mod.default);
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
    let stopped=false;let cleanup=()=>{};
    const loader=effectsFiles[`./generated/${page.key}.effects.json`]; if(loader&&!['/','/explore'].includes(page.path))loader().then(mod=>{
      if(stopped)return;cleanup=initLegacyEffects(mod.default);
    });
    return()=>{stopped=true;cleanup()};
  },[page.key,screen]);
  useEffect(()=>attachNavigation(),[]);
  // Reveal the header and page together after the lazy content and CSS are ready.
  if(!screen&&!failed)return null;
  return render(<><SiteHeader />{failed ? <main role="alert">Không tải được trang. <button type="button" onClick={()=>location.reload()}>Tải lại</button></main> : screen===MaintenancePage ? <MaintenancePage /> : <LocalizedPage component={screen} />}{page.path==='/' ? null : <SiteFooter />}</>);
}

applyPreferences(readPreferences());
createRoot(document.getElementById('root')).render(<PreferencesProvider><SocialProvider><FeedProvider><App /></FeedProvider></SocialProvider></PreferencesProvider>);
