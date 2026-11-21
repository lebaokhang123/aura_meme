import React from 'react';
import {usePreferences} from '../PreferencesContext.jsx';
import {usePremium} from '../PremiumContext.jsx';

export function AuraPerksCard() {
  const {language} = usePreferences();
  const isEn = language === 'en';
  const {subscription} = usePremium();
  const isActive = !!subscription?.is_active;
  const isPrime = isActive && subscription?.tier === 'prime';
  const isPlus = isActive && subscription?.tier === 'plus';

  return (
    <div className={`bg-gradient-to-br from-surface-container-low via-secondary-container/40 to-surface-container-low rounded-xl p-4 shadow-[0_0_25px_rgba(208,188,255,0.18)] flex flex-col gap-3.5 relative overflow-hidden border ${isPrime ? 'border-cyan-400/50 shadow-[0_0_25px_rgba(6,182,212,0.25)]' : isPlus ? 'border-amber-500/50 shadow-[0_0_25px_rgba(249,115,22,0.25)]' : 'border-secondary/30'}`}>
      <div className="absolute -right-10 -top-10 w-28 h-28 bg-tertiary/20 rounded-full blur-2xl pointer-events-none" />
      <div className="absolute -left-8 -bottom-8 w-24 h-24 bg-secondary/15 rounded-full blur-2xl pointer-events-none" />
      <div className="flex items-center justify-between relative z-10">
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full ${isPrime ? 'bg-cyan-500/15 border border-cyan-400/60 text-cyan-300' : isPlus ? 'bg-orange-500/15 border border-orange-400/60 text-orange-300' : 'bg-cyan-500/10 border border-cyan-500/50 text-cyan-400'}`}>
          <span className="material-symbols-outlined text-[15px]">{isPrime ? 'diamond' : 'workspace_premium'}</span>
          <span className="font-mono-tag text-[10px] uppercase font-bold tracking-wider">AURA PERKS</span>
        </div>
        <span className={`font-mono-tag text-mono-tag px-2 py-0.5 rounded-full ${isActive ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30' : 'bg-surface-container-high/80 text-tertiary border border-tertiary/20'}`}>
          {isActive ? (isEn ? 'Active' : 'Đang kích hoạt') : (isEn ? 'Available' : 'Đã mở đăng ký')}
        </span>
      </div>
      <div className="flex flex-col gap-1 relative z-10">
        <h3 className="font-headline-sm text-[18px] font-bold text-on-surface tracking-tight leading-snug flex items-center gap-2">
          {isActive ? (isPrime ? 'Aura Prime' : 'Aura Plus') : 'Aura Plus / Prime'}{' '}
          <span className={`${isActive ? (isPrime ? 'text-cyan-400' : 'text-amber-400') : 'text-tertiary'} text-sm material-symbols-outlined`}>verified</span>
        </h3>
        <p className="font-body-sm text-[12px] text-on-surface-variant leading-relaxed">
          {isActive
            ? (isEn ? `Active · ${subscription.days_remaining} days remaining.` : `Đang kích hoạt · Còn ${subscription.days_remaining} ngày sử dụng.`)
            : (isEn ? 'Earn bonus EXP towards your Level.' : 'Nhận bonus Exp hấp dẫn cho Level.')}
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
        className={`w-full py-2.5 px-3 rounded-lg ${isPrime ? 'bg-gradient-to-r from-cyan-500 via-sky-400 to-amber-300 text-surface-container-lowest shadow-[0_0_15px_rgba(6,182,212,0.5)]' : isPlus ? 'bg-gradient-to-r from-red-500 via-orange-400 to-amber-400 text-surface-container-lowest shadow-[0_0_15px_rgba(249,115,22,0.5)]' : 'bg-gradient-to-r from-secondary via-secondary to-tertiary text-surface-container-lowest shadow-[0_0_15px_rgba(208,188,255,0.4)]'} hover:opacity-95 font-label-md text-label-md font-bold active:scale-[0.98] transition-all flex items-center justify-center gap-2 cursor-pointer relative z-10`}
        href="/premium"
      >
        <span className="material-symbols-outlined text-[18px]">workspace_premium</span>
        <span className="tracking-wide">
          {isActive ? (isEn ? 'Extend Subscription' : 'Gia hạn gói') : (isEn ? 'Explore Plus / Prime' : 'Xem Plus / Prime')}
        </span>
      </a>
    </div>
  );
}
