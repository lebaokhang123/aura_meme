// Lucian UX/UI Prompt #267 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#267
import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { translate } from '../preferences.js';

export function SwapText({ source, block = false, renderText }) {
  const { language, reducedMotion } = usePreferences();
  const [shown, setShown] = useState(language);
  const [phase, setPhase] = useState('');
  const root = useRef(null);
  const changing = useRef(false);
  useEffect(() => {
    const el = root.current;
    const box = el.getBoundingClientRect();
    if (reducedMotion || !box.width || box.bottom <= 0 || box.top >= innerHeight || shown === language) {
      changing.current = false; el.style.width = ''; setPhase(''); setShown(language); return;
    }
    const timers = [];
    timers.push(setTimeout(() => {
      if (el.closest('button,.site-nav a,.site-auth a,.compact-auth a')) el.style.width = `${el.getBoundingClientRect().width}px`;
      setPhase('is-go');
      timers.push(setTimeout(() => { changing.current = true; setShown(language); setPhase('is-in'); }, 260));
      timers.push(setTimeout(() => { changing.current = false; el.style.width = ''; setPhase(''); }, 640));
    }, Number(el.dataset.swapDelay || 0)));
    return () => timers.forEach(clearTimeout);
  }, [language, reducedMotion]);
  useLayoutEffect(() => {
    const el = root.current;
    if (!changing.current || !el.style.width) return;
    const measure = el.firstElementChild.cloneNode(true);
    measure.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;width:max-content;pointer-events:none';
    el.appendChild(measure); const width = measure.getBoundingClientRect().width; measure.remove();
    const frame = requestAnimationFrame(() => { el.style.width = `${width}px`; });
    return () => cancelAnimationFrame(frame);
  }, [shown]);
  return <span ref={root} className={`u267-sw ${phase}`} style={block ? { display:'block' } : undefined}><span>{renderText ? renderText(shown) : translate(source, shown)}</span></span>;
}
