import { useLocalized } from '../localize.jsx';
import React, { useEffect, useRef, useState } from 'react';
import { readDemoUser } from '../demo.js';
import {MOCK_AUTH} from '../auth.js';
import {logoutAccount} from '../runtime.js';
import { useFeed } from '../FeedContext.jsx';
import { LanguageSwitch } from './LanguageSwitch.jsx';
import { ThemeSwitch } from './ThemeSwitch.jsx';

const navigation = [
  ['trang-chu', '/', 'Trang chủ'], ['kham-pha', '/explore', 'Khám phá'],
  ['bao-kho', '/vault', 'Bảo Khố'],
  ['gioi-thieu', '/about', 'Giới thiệu'], ['lien-he', '/contact', 'Liên hệ'],
];
const symbol = name => <span className="material-symbols-outlined" aria-hidden="true">{name}</span>;

export function GithubIcon() {
  return <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" /></svg>;
}

export function SiteHeader() {
  const render = useLocalized();
  const { filters, update, url } = useFeed();
  const [query, setQuery] = useState(filters.q);
  useEffect(() => setQuery(filters.q), [filters.q]);
  const user = readDemoUser();
  const [open, setOpen] = useState(null);
  const header = useRef(null);
  const accountButton = useRef(null);
  const profile = useRef(null);
  const path = location.pathname.replace(/\/$/, '') || '/';
  const toggle = name => setOpen(current => current === name ? null : name);
  useEffect(() => {
    const outside = event => { if (!event.target.closest('[data-header-popup]')) setOpen(null); };
    const keys = event => {
      if (event.key === 'Escape') {
        header.current?.querySelector('[aria-expanded="true"]')?.focus();
        setOpen(null);
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        const input = header.current?.querySelector('input');
        if (input?.getClientRects().length) { event.preventDefault(); input.focus(); }
      }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', keys);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', keys); };
  }, []);
  const links = navigation.map(([key, href, label]) => <a key={key} data-path={key} href={['/', '/explore'].includes(href) ? url(href) : href} aria-current={path === href ? 'page' : undefined}>{label}</a>);
  const auth = <><a data-path="dang-nhap" href="/login" className={`auth-login${path === '/login' ? ' active' : ''}`}>Đăng nhập</a><a data-path="dang-ky" href="/register" className={`auth-register${path === '/register' ? ' active' : ''}`}>Đăng ký</a></>;
  return render(<>
    <header className="site-header" ref={header}>
      <div className="site-header-inner">
        <a href="/" data-path="trang-chu" className="site-brand" aria-label="AuraMeme — Trang chủ"><img src="/assets/brand/favicon-64.png" alt="" width="32" height="32" /><span>Aura<span>Meme</span></span></a>
        <nav className="site-nav" aria-label="Điều hướng chính">{links}</nav>
        <form className="site-search" role="search" onSubmit={event => { event.preventDefault(); update({ q: query.trim() }); }}>{symbol('search')}<input type="search" maxLength={100} value={query} onChange={event => { setQuery(event.target.value); if (!event.target.value) update({ q: '' }); }} aria-label="Tìm kiếm meme, tác giả, thẻ" placeholder="Tìm kiếm meme, tác giả, thẻ..." /><kbd>Ctrl K</kbd></form>
        <div className="site-tools">
          <ThemeSwitch />
          <LanguageSwitch open={open === 'language'} onToggle={() => toggle('language')} onClose={() => setOpen(null)} />
          {user ? <>
            <button type="button" className="site-icon-button" aria-label="Thông báo" title="Thông báo">{symbol('notifications')}</button>
            <div className="site-account" data-header-popup="account"><button ref={accountButton} type="button" className="account-trigger" aria-label="Mở menu tài khoản" aria-haspopup="true" aria-expanded={open === 'account'} aria-controls="site-account-menu" onClick={() => toggle('account')}><img className="account-avatar" src={user.avatar} alt={`Ảnh đại diện ${user.displayName}`} width="32" height="32" /></button>
              {open === 'account' && <div className="site-dropdown" id="site-account-menu"><button type="button" onClick={() => { setOpen(null); if(MOCK_AUTH)profile.current.showModal();else location.assign('/profile'); }}>{symbol('person')}Thông tin</button><button type="button" className="logout-action" onClick={event => logoutAccount(event.currentTarget)}>{symbol('logout')}Đăng xuất</button></div>}
            </div>
          </> : <div className="site-auth">{auth}</div>}
          <div className="site-menu" data-header-popup="navigation"><button type="button" className="site-icon-button compact-menu-trigger" aria-label="Mở menu điều hướng" aria-expanded={open === 'navigation'} aria-controls="compact-navigation" onClick={() => toggle('navigation')}>{symbol(open === 'navigation' ? 'close' : 'menu')}</button>
            <nav id="compact-navigation" className="compact-navigation" aria-label="Điều hướng thu gọn" hidden={open !== 'navigation'}>
              <div className="md:hidden"><form className="site-search" style={{ display: 'flex', minWidth: 0, margin: '4px 0 8px', width: '100%' }} role="search" onSubmit={event => { event.preventDefault(); update({ q: query.trim() }); setOpen(null); }}>{symbol('search')}<input type="search" maxLength={100} value={query} onChange={event => { setQuery(event.target.value); if (!event.target.value) update({ q: '' }); }} aria-label="Tìm kiếm meme, tác giả, thẻ" placeholder="Tìm kiếm bài viết..." /></form></div>
              {links}{!user && <div className="compact-auth">{auth}</div>}</nav>
          </div>
        </div>
      </div>
    </header>
    {user && <dialog ref={profile} className="demo-profile" aria-labelledby="demo-profile-title" onClose={() => accountButton.current?.focus()}><button type="button" className="site-icon-button profile-close" aria-label="Đóng thông tin" onClick={() => profile.current.close()}>{symbol('close')}</button><img src={user.avatar} width="80" height="80" alt={`Ảnh đại diện ${user.displayName}`} /><h2 id="demo-profile-title">Thông tin demo</h2><strong>{user.displayName}</strong><p>@{user.username}</p><small>Dữ liệu frontend demo.</small></dialog>}
  </>);
}

export function SiteFooter() {
  const render = useLocalized();
  return render(<footer className="site-footer"><div>© 2026 AuraMeme. All rights reserved.</div><div className="site-footer-links"><a href="/privacy.html" target="_blank" rel="noopener noreferrer">Chính sách bảo mật</a><a href="https://github.com/lebaokhang123/aura_meme" target="_blank" rel="noopener noreferrer"><GithubIcon /><span>Github</span></a></div></footer>);
}

export function MaintenancePage() {
  const render = useLocalized();
  return render(<main className="maintenance-page"><div className="maintenance-content"><div className="maintenance-frame"><img className="maintenance-art" src="/assets/brand/baotri.png" alt="Robot bảo trì AuraMeme" width="1024" height="1024" /></div><h1>Tính năng đang phát triển...</h1><a href="/" data-path="trang-chu" className="maintenance-back">{symbol('arrow_back')}Quay lại Trang chủ</a></div></main>);
}
