export function relativeTime(createdAt, language = 'vi') {
  const lang = language === 'en' ? 'en' : 'vi';
  if (!createdAt) return lang === 'en' ? 'Just now' : 'Vừa xong';
  const time = typeof createdAt === 'string' ? Date.parse(createdAt) : Number(createdAt);
  if (!Number.isFinite(time)) return lang === 'en' ? 'Just now' : 'Vừa xong';
  const diffSeconds = (Date.now() - time) / 1000;
  if (diffSeconds < 1) return lang === 'en' ? 'Just now' : 'Vừa xong';
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: 'always' });
  if (diffSeconds < 60) return rtf.format(-Math.floor(diffSeconds), 'second');
  const diffMinutes = diffSeconds / 60;
  if (diffMinutes < 60) return rtf.format(-Math.floor(diffMinutes), 'minute');
  const diffHours = diffMinutes / 60;
  if (diffHours < 24) return rtf.format(-Math.floor(diffHours), 'hour');
  const diffDays = diffHours / 24;
  if (diffDays < 30) return rtf.format(-Math.floor(diffDays), 'day');
  const diffMonths = diffDays / 30;
  if (diffMonths < 12) return rtf.format(-Math.floor(diffMonths), 'month');
  const diffYears = diffDays / 365;
  return rtf.format(-Math.max(1, Math.floor(diffYears)), 'year');
}
