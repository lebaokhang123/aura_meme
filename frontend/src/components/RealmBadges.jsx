import React from 'react';
import { resolveRealmBadges } from '../realm-tier.js';

function SpecialGlyph({ kind }) {
  if (kind === 'thunder') {
    return (
      <span className="am-title-badge-glyph" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="currentColor">
          <path d="M9.6 1.2 3.5 8.8h4.1L6.4 14.8l6.1-7.6H8.4l1.2-6Z" />
        </svg>
      </span>
    );
  }
  if (kind === 'warden') {
    return (
      <span className="am-title-badge-glyph" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 1.4 2.4 3.6v4.1c0 3.3 2.3 6.2 5.6 6.9 3.3-.7 5.6-3.6 5.6-6.9V3.6L8 1.4Zm0 2.1 3.6 1.4v2.8c0 2.3-1.5 4.4-3.6 5-2.1-.6-3.6-2.7-3.6-5V4.9L8 3.5Z" />
        </svg>
      </span>
    );
  }
  return null;
}

export function LevelPill({ level, size = 'md', className = '' }) {
  const { levelLabel, realmTier } = resolveRealmBadges({ level });
  if (!levelLabel || !realmTier) return null;
  return (
    <span
      className={`am-lvl-pill am-lvl-pill--${size}${className ? ' ' + className : ''}`}
      data-realm-tier={realmTier}
      translate="no"
    >
      {levelLabel}
    </span>
  );
}

export function TitleBadge({ level, realm, title, size = 'md', className = '' }) {
  const { realmTier, titleText, specialKind } = resolveRealmBadges({ level, realm, title });
  if (!realmTier || !titleText) return null;
  return (
    <span
      className={`am-title-badge am-title-badge--${size}${className ? ' ' + className : ''}`}
      data-realm-tier={realmTier}
      data-special-title={specialKind || undefined}
      translate="no"
    >
      <SpecialGlyph kind={specialKind} />
      <span>{titleText}</span>
    </span>
  );
}

export function AuthorRankBadges({ level, realm, title, size = 'md', className = '' }) {
  return (
    <>
      <LevelPill level={level} size={size} className={className} />
      <TitleBadge level={level} realm={realm} title={title} size={size} className={className} />
    </>
  );
}
