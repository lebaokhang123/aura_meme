// Lucian UX/UI Prompt #267 · MIT License (c) 2026 Seokwoooo · https://lucianlabs.dev/uxui-prompt/#267
import React, { useEffect, useRef } from 'react';
import { usePreferences } from '../PreferencesContext.jsx';
import { translate } from '../preferences.js';
import './preferences-controls.css';

export function LanguageSwitch({ open, onToggle, onClose }) {
  const { language, update } = usePreferences();
  const trigger = useRef(null), list = useRef(null);
  const options = [{ code:'vi', label:'Tiếng Việt' }, { code:'en', label:'English' }];
  useEffect(() => {
    if (open) list.current.querySelector('[aria-selected="true"]')?.focus({preventScroll:true});
  }, [open]);
  const close = () => { onClose(); trigger.current.focus({preventScroll:true}); };
  const keys = event => {
    if (event.key === 'Escape') { event.stopPropagation(); close(); }
    const buttons = [...list.current.querySelectorAll('[role="option"]')];
    if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
      event.preventDefault(); event.stopPropagation();
      const current = buttons.indexOf(document.activeElement);
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length-1 : (current + (event.key === 'ArrowUp' ? -1 : 1) + buttons.length) % buttons.length;
      buttons[index].focus();
    }
  };
  return <div className={`u267 site-language${open ? ' is-open' : ''}`} data-header-popup="language" onKeyDown={keys} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) onClose(); }}>
    <button ref={trigger} type="button" className="u267-gb" aria-label={translate('Chọn ngôn ngữ',language)} aria-haspopup="listbox" aria-expanded={open} aria-controls="site-language-menu" onClick={onToggle} onKeyDown={event => { if (['ArrowDown','ArrowUp'].includes(event.key) && !open) { event.preventDefault(); onToggle(); } }}>
      <svg viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.3"/><path d="M1.5 7h11M7 1.5c1.8 1.6 1.8 9.4 0 11M7 1.5c-1.8 1.6-1.8 9.4 0 11" fill="none" stroke="currentColor" strokeWidth="1.3"/></svg><span className="u267-cd">{language.toUpperCase()}</span>
    </button>
    <div ref={list} className="u267-dd" id="site-language-menu" role="listbox" aria-label={translate('Chọn ngôn ngữ',language)} aria-hidden={!open} inert={!open}>
      {options.map(option => <button type="button" className={`u267-op${language === option.code ? ' is-on' : ''}`} key={option.code} role="option" lang={option.code} aria-selected={language === option.code} tabIndex={open ? 0 : -1} onClick={() => { if (language !== option.code) update({language:option.code}); close(); }}><em aria-hidden="true">{option.code.toUpperCase()}</em><span>{option.label}</span><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2.5 7.5l3 3 6-6.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg></button>)}
    </div>
  </div>;
}
