import english from './translations.json' with { type: 'json' };
export const PREFERENCES_KEY = 'aurameme-ui-preferences';
export function readPreferences(storage) {
  try {
    const saved = JSON.parse((storage || localStorage).getItem(PREFERENCES_KEY));
    return { theme: saved?.theme === 'light' ? 'light' : 'dark', language: saved?.language === 'en' ? 'en' : 'vi' };
  } catch { return { theme: 'dark', language: 'vi' }; }
}
export function translate(source, language) {
  if (language !== 'en' || typeof source !== 'string') return source;
  const core = source.trim();
  let translated = english[core];
  if (translated === undefined) {
    if (core.startsWith('Ảnh đại diện ')) translated = 'Avatar of ' + core.slice(13);
    else if (/^Xem bài của (.+) trên Trang chủ$/.test(core)) translated = core.replace(/^Xem bài của (.+) trên Trang chủ$/, 'View $1\'s post on Home');
  }
  return translated === undefined ? source : source.slice(0, source.indexOf(core)) + translated + source.slice(source.indexOf(core) + core.length);
}
export const hasTranslation = source => typeof source === 'string' && Object.hasOwn(english, source.trim());
export function applyPreferences({ theme, language }) {
  const root = document.getElementById('root');
  root.classList.add('u219'); root.dataset.theme = theme;
  document.documentElement.dataset.theme = theme;
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document.documentElement.lang = language;
}
