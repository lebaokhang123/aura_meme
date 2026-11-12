import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { applyPreferences, PREFERENCES_KEY, readPreferences } from './preferences.js';
const PreferencesContext = createContext(null);
export const usePreferences = () => useContext(PreferencesContext);
export function PreferencesProvider({ children }) {
  const [preferences, setPreferences] = useState(readPreferences);
  const current = useRef(preferences);
  const [reducedMotion, setReducedMotion] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)');
    const changed = () => setReducedMotion(media.matches);
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  const update = patch => {
    if (patch.language && patch.language !== current.current.language) {
      [...document.querySelectorAll('.u267-sw')].filter(el => {
        const box = el.getBoundingClientRect(); return box.width && box.bottom > 0 && box.top < innerHeight;
      }).sort((a,b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).forEach((el, i) => { el.dataset.swapDelay = i * 45; });
    }
    const next = { ...current.current, ...patch };
    current.current = next;
    applyPreferences(next); setPreferences(next);
    try { localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next)); } catch { /* The current page still works when browser storage is blocked. */ }
  };
  return <PreferencesContext.Provider value={{ ...preferences, reducedMotion, update }}>{children}</PreferencesContext.Provider>;
}
