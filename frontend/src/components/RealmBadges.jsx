import React from 'react';
import { resolveRealmBadges } from '../realm-tier.js';

function SpecialGlyph({ kind }) {
  if (kind === 'creator') {
    return (
      <span className="am-title-badge-glyph am-title-badge-glyph--creator" aria-hidden="true">
        <svg viewBox="0 0 18 18" fill="none">
          <circle cx="9" cy="9" r="6.4" stroke="currentColor" strokeOpacity="0.45" strokeWidth="1" />
          <path
            d="M9 1.6 10.65 7.35 16.4 9 10.65 10.65 9 16.4 7.35 10.65 1.6 9 7.35 7.35 9 1.6Z"
            fill="currentColor"
          />
          <circle cx="9" cy="9" r="1.5" fill="#fffdf7" />
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
  const isCreator = specialKind === 'creator';
  return (
    <span
      className={`am-title-badge am-title-badge--${size}${className ? ' ' + className : ''}`}
      data-realm-tier={realmTier}
      data-special-title={specialKind || undefined}
      translate="no"
    >
      {isCreator && <span className="am-creator-convergence" aria-hidden="true" />}
      <SpecialGlyph kind={specialKind} />
      <span className="am-title-badge-label">{titleText}</span>
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
