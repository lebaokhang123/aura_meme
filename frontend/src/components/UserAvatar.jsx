import React from 'react';
import { usePreferences } from '../PreferencesContext.jsx';

export default function UserAvatar({
  src,
  alt = 'Avatar',
  tier = 'free',
  size = 'md',
  className = '',
  wrapClassName = '',
  badge = true,
  width,
  height,
}) {
  const { language } = usePreferences?.() || { language: 'vi' };
  const t = (vi, en) => (language === 'en' ? en : vi);

  const cleanTier = (tier || 'free').toLowerCase();
  const isPlus = cleanTier === 'plus';
  const isPrime = cleanTier === 'prime';
  const hasAura = isPlus || isPrime;

  // Size mapping
  const sizeClasses = {
    xs: 'w-6 h-6',
    sm: 'w-8 h-8',
    md: 'w-9 h-9',
    lg: 'w-28 h-28',
  }[size] || 'w-9 h-9';

  const badgeSizeClasses = {
    xs: 'w-3 h-3 bottom-[-2px] right-[-2px]',
    sm: 'w-3.5 h-3.5 bottom-[-2px] right-[-2px]',
    md: 'w-4 h-4 bottom-[-2px] right-[-2px]',
    lg: 'w-6 h-6 bottom-[4px] right-[4px]',
  }[size] || 'w-4 h-4 bottom-[-2px] right-[-2px]';

  const checkSize = size === 'lg' ? 14 : size === 'xs' ? 7 : size === 'sm' ? 8 : 10;

  return (
    <div className={`user-avatar-wrap ${wrapClassName}`}>
      <img
        src={src || '/assets/identity/default-avatar.svg'}
        alt={alt}
        className={`rounded-full object-cover shrink-0 ${sizeClasses} ${
          isPrime
            ? 'aura-avatar--prime'
            : isPlus
            ? 'aura-avatar--plus'
            : 'ring-1 ring-secondary/50'
        } ${className}`}
        width={width}
        height={height}
      />
      {hasAura && badge && (
        <span
          className={`aura-member-badge ${
            isPrime ? 'aura-member-badge--prime' : 'aura-member-badge--plus'
          } ${badgeSizeClasses}`}
          title={
            isPrime
              ? t('Hội viên Aura Prime', 'Aura Prime Member')
              : t('Hội viên Aura Plus', 'Aura Plus Member')
          }
          aria-label={
            isPrime
              ? t('Hội viên Aura Prime', 'Aura Prime Member')
              : t('Hội viên Aura Plus', 'Aura Plus Member')
          }
        >
          <svg viewBox="0 0 24 24" width={checkSize} height={checkSize} fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
          </svg>
        </span>
      )}
    </div>
  );
}
