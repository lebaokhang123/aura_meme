import React from 'react';
import {usePreferences} from '../PreferencesContext.jsx';
import '../workspace.css';

export default function PremiumPage(){
 const {language}=usePreferences(),t=(vi,en)=>language==='en'?en:vi;
 return <main className="workspace-page premium-page"><div className="workspace-content">
  <header className="workspace-hero"><span className="workspace-kicker">AURA PERKS</span><h1>Aura Plus <span>&</span> Aura Prime</h1><p>{t('Thêm động lực cho hành trình lên Level của bạn.','A little more momentum for your Level journey.')}</p><span className="workspace-badge">{t('Sắp ra mắt · Chưa mở đăng ký','Coming Soon · Registration closed')}</span></header>
  <section className="premium-plans" aria-label={t('Hai gói dự kiến','Planned memberships')}>{[['Plus',30,2],['Prime',365,3]].map(([name,days,multiplier])=><article className={'premium-plan premium-'+name.toLowerCase()} key={name}><span className="material-symbols-outlined" aria-hidden="true">{name==='Plus'?'auto_awesome':'diamond'}</span><h2>Aura {name}</h2><p className="premium-duration">{days} {t('ngày','days')}</p><p className="premium-boost">×{multiplier} <span>{t('bonus XP cho Level','bonus XP for Level')}</span></p><p>{t('Quyền lợi dự kiến khi mở đăng ký.','Planned benefit when registration opens.')}</p><button type="button" disabled>{t('Chưa mở đăng ký','Registration closed')}</button></article>)}</section>
  <section className="workspace-panel premium-details" aria-labelledby="premium-benefits"><h2 id="premium-benefits">{t('Quyền lợi V1 dự kiến','Planned V1 benefits')}</h2><ul><li>{t('Rank tính XP earned gốc, không nhân boost.','Rank uses original earned XP, without the boost.')}</li><li>{t('Giữ nguyên odds và cooldown Bảo Khố.','Vault odds and cooldown stay the same.')}</li><li>{t('Hết hạn vẫn giữ XP đã nhận.','Previously earned XP remains after expiry.')}</li><li>{t('Không tự động gia hạn.','No automatic renewal.')}</li></ul><p>{t('Giá và thanh toán chưa được công bố. Hiện chưa có đăng ký hoặc giao dịch.','Pricing and payment are not announced. Registration and transactions are not available yet.')}</p></section>
  <a className="workspace-back" href="/">{t('Quay lại Trang chủ','Back to Home')}</a>
 </div></main>;
}
