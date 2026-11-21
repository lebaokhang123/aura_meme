import React from 'react';
import {usePreferences} from '../PreferencesContext.jsx';

export function AuraPerksCard() {
  const {language} = usePreferences();
  const isEn = language === 'en';

  return (
    <div className="bg-gradient-to-br from-surface-container-low via-secondary-container/40 to-surface-container-low rounded-xl p-4 shadow-[0_0_25px_rgba(208,188,255,0.18)] flex flex-col gap-3.5 relative overflow-hidden border border-secondary/30">
      <div className="absolute -right-10 -top-10 w-28 h-28 bg-tertiary/20 rounded-full blur-2xl pointer-events-none" />
      <div className="absolute -left-8 -bottom-8 w-24 h-24 bg-secondary/15 rounded-full blur-2xl pointer-events-none" />
      <div className="flex items-center justify-between relative z-10">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/50 text-cyan-400">
          <span className="material-symbols-outlined text-[15px]">diamond</span>
          <span className="font-mono-tag text-[10px] uppercase font-bold tracking-wider">AURA PERKS</span>
        </div>
        <span className="font-mono-tag text-mono-tag px-2 py-0.5 rounded-full bg-surface-container-high/80 text-tertiary border border-tertiary/20">
          {isEn ? 'Coming soon' : 'Sắp ra mắt'}
        </span>
      </div>
      <div className="flex flex-col gap-1 relative z-10">
        <h3 className="font-headline-sm text-[18px] font-bold text-on-surface tracking-tight leading-snug flex items-center gap-2">
          Aura Plus / Prime{' '}
          <span className="text-tertiary text-sm material-symbols-outlined">verified</span>
        </h3>
        <p className="font-body-sm text-[12px] text-on-surface-variant leading-relaxed">
          {isEn ? 'Coming soon: bonus EXP for your Level.' : 'Sắp ra mắt: bonus Exp dành cho Level.'}
        </p>
      </div>
      <div className="flex flex-col gap-2 pt-0.5 relative z-10">
        <div className="flex items-center gap-2.5 text-body-sm text-[13px] text-on-surface">
          <span className="text-[15px] shrink-0">✨</span>
          <span className="font-medium">
            {isEn ? 'Plus 30 days: ×2 bonus EXP for Level' : 'Plus 30 ngày: x2 bonus Exp cho Level'}
          </span>
        </div>
        <div className="flex items-center gap-2.5 text-body-sm text-[13px] text-on-surface">
          <span className="text-[15px] shrink-0">🎨</span>
          <span className="font-medium">
            {isEn ? 'Prime 365 days: ×3 bonus EXP for Level' : 'Prime 365 ngày: x3 bonus Exp cho Level'}
          </span>
        </div>
        <div className="flex items-center gap-2.5 text-body-sm text-[13px] text-on-surface">
          <span className="text-[15px] shrink-0">💎</span>
          <span className="font-medium">
            {isEn ? 'Rank retains base earned EXP' : 'Rank giữ Exp earned gốc'}
          </span>
        </div>
        <div className="flex items-center gap-2.5 text-body-sm text-[13px] text-on-surface">
          <span className="text-[15px] shrink-0">⚡</span>
          <span className="font-medium">
            {isEn ? 'No change to Vault odds or cooldown' : 'Không thay đổi odds và cooldown Bảo Khố'}
          </span>
        </div>
      </div>
      <a
        className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-secondary via-secondary to-tertiary hover:opacity-95 text-surface-container-lowest font-label-md text-label-md font-bold shadow-[0_0_15px_rgba(208,188,255,0.4)] active:scale-[0.98] transition-all flex items-center justify-center gap-2 cursor-pointer relative z-10"
        href="/premium"
      >
        <span className="material-symbols-outlined text-[18px]">workspace_premium</span>
        <span className="tracking-wide">
          {isEn ? 'Explore Plus / Prime' : 'Xem Plus / Prime'}
        </span>
      </a>
    </div>
  );
}
