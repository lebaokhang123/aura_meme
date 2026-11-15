// Lucian UX/UI Prompt #363 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#363
// Lucian UX/UI Prompt #352 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#352
// Lucian UX/UI Prompt #226 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#226
// Lucian UX/UI Prompt #330 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#330
import React, { useEffect, useRef } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { BACKGROUND_EFFECTS, mountBackground } from '../background-effects.js';
import '../global-background.css';

export default function GlobalBackground({ effect = null }) {
  const root = useRef(null);
  const preferences = usePreferences();
  const theme = preferences?.theme || 'dark';
  const selected = BACKGROUND_EFFECTS.includes(effect) ? effect : null;
  useEffect(() => {
    if (!root.current || selected === 'violet-base') return;
    return mountBackground(root.current, selected);
  }, [selected, theme]);
  if (!selected) return null;
  return <div ref={root} className="global-background" data-effect={selected} data-theme={theme} aria-hidden="true">
    {selected === 'lucian-226' && <><div className="global-background-grid" /><div className="global-background-spot" /><div className="global-background-glow" /></>}
    {selected !== 'violet-base' && <canvas />}
  </div>;
}
