// Lucian UX/UI Prompt #219 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#219
import React, { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { usePreferences } from '../PreferencesContext.jsx';
import { translate } from '../preferences.js';
import './preferences-controls.css';

export function ThemeSwitch() {
  const { theme, language, reducedMotion, update } = usePreferences();
  const busy = useRef(false), transition = useRef(null), animation = useRef(null);
  const [running, setRunning] = useState(false);
  useEffect(() => () => { transition.current?.skipTransition(); animation.current?.cancel(); }, []);
  useEffect(() => { if (reducedMotion) { transition.current?.skipTransition(); animation.current?.cancel(); } }, [reducedMotion]);
  const toggle = async event => {
    if (busy.current) return;
    const target = theme === 'dark' ? 'light' : 'dark';
    if (reducedMotion || !document.startViewTransition) { update({theme:target}); return; }
    const box = event.currentTarget.getBoundingClientRect();
    const x = box.left + box.width/2, y = box.top + box.height/2;
    const radius = Math.hypot(Math.max(x,innerWidth-x), Math.max(y,innerHeight-y));
    busy.current = true; setRunning(true);
    document.documentElement.classList.add('u219-reveal');
    try {
      transition.current = document.startViewTransition(() => flushSync(() => update({theme:target})));
      await transition.current.ready;
      animation.current = document.documentElement.animate({clipPath:[`circle(0px at ${x}px ${y}px)`,`circle(${radius}px at ${x}px ${y}px)`]}, {duration:700,easing:'cubic-bezier(.65,0,.35,1)',pseudoElement:'::view-transition-new(root)',fill:'both'});
      await animation.current.finished;
      await transition.current.finished;
    } catch { transition.current?.skipTransition(); update({theme:target}); }
    finally { document.documentElement.classList.remove('u219-reveal'); busy.current=false; setRunning(false); }
  };
  return <div className="u219-control"><button type="button" className={`u219-tg${theme === 'dark' ? ' is-dark' : ''}`} onClick={toggle} aria-label={translate(theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối',language)} aria-pressed={theme === 'dark'} aria-disabled={running}>
    <svg viewBox="0 0 16 16" aria-hidden="true">{theme === 'dark' ? <path d="M13.5 9.8A5.6 5.6 0 0 1 6.2 2.5a5.6 5.6 0 1 0 7.3 7.3z" fill="currentColor"/> : <><circle cx="8" cy="8" r="3" fill="currentColor"/><g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 1.5v1.4M8 13.1v1.4M1.5 8h1.4M13.1 8h1.4M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1"/></g></>}</svg>
  </button></div>;
}
