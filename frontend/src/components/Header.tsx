import { Link, NavLink } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { useUI } from '../context/UIContext';
import { useAuth } from '../context/AuthContext';
import { ApiError, errorMessage } from '../api';

const navigation = [
  { label: 'Home', to: '/' },
  { label: 'Explore', to: '/explore' },
  { label: 'About', to: '/about' },
  { label: 'Contact', to: '/contact' },
];

export function Header() {
  const { setSearchOpen, showToast } = useUI();
  const { user, pending, error, logout, refresh } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const accountLinks = user ? <>
    <Link to="/my-posts" onClick={() => setMenuOpen(false)} className="min-h-11 px-3 py-3 rounded-lg bg-surface-container text-xs">My posts</Link>
    <Link to="/settings" onClick={() => setMenuOpen(false)} className="min-h-11 px-3 py-3 rounded-lg bg-surface-container text-xs">Settings</Link>
    {user.roles.includes('ADMIN') && <Link to="/admin" onClick={() => setMenuOpen(false)} className="min-h-11 px-3 py-3 rounded-lg bg-surface-container text-xs">Admin</Link>}
    <button disabled={signingOut} className="min-h-11 px-3 py-3 rounded-lg bg-primary text-on-primary text-xs" onClick={async () => {
      if (signingOut) return;
      setSigningOut(true);
      try { await logout(); setMenuOpen(false); showToast('Signed out.'); }
      catch (fault) {
        showToast(errorMessage(fault));
        if (fault instanceof ApiError && fault.status === 401) await refresh();
      }
      finally { setSigningOut(false); }
    }}>{signingOut ? 'Signing out…' : 'Sign out'}</button>
  </> : <>
    <Link to="/login" onClick={() => setMenuOpen(false)} className="min-h-11 px-3 py-3 rounded-lg bg-surface-container text-xs">Login</Link>
    <Link to="/register" onClick={() => setMenuOpen(false)} className="min-h-11 px-3 py-3 rounded-lg bg-primary text-on-primary text-xs">Sign Up</Link>
  </>;
  const sessionControls = pending ? <span className="text-xs">Checking session…</span> : error
    ? <Link to="/settings" className="text-xs underline">Connection issue</Link> : accountLinks;
  const [isMenuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!isMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isMenuOpen]);

  return (
    <header className="fixed top-0 inset-x-0 z-40 bg-[#0d0e15]/95 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.35)] border-b border-[#292932]/40">
      <div className="h-16 w-full px-4 lg:px-6 flex items-center justify-between gap-3">
        <div className="flex items-center gap-5 min-w-0">
          <Link
            to="/"
            aria-label="AuraMeme home"
            onClick={() => setMenuOpen(false)}
            className="flex items-center gap-2 shrink-0 group"
          >
            <img
              alt=""
              className="h-8 w-8 rounded-lg drop-shadow-[0_0_8px_rgba(208,188,255,0.4)]"
              src="/assets/illustrations/brand-placeholder.svg"
            />
            <span className="font-['Plus_Jakarta_Sans'] font-bold text-xl max-[374px]:text-base bg-gradient-to-r from-primary via-primary-container to-secondary bg-clip-text text-transparent">
              AuraMeme
            </span>
          </Link>
          <nav aria-label="Main navigation" className="hidden xl:flex items-center gap-1">
            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `px-3 py-3 rounded-lg text-[13px] font-semibold transition-colors ${isActive ? 'bg-surface-container text-on-surface' : 'text-on-surface-variant hover:bg-surface-container-high'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <button
          type="button"
          aria-label="Search posts"
          onClick={() => {
            setMenuOpen(false);
            setSearchOpen(true);
          }}
          className="hidden md:flex items-center gap-3 flex-1 max-w-md min-h-11 px-4 rounded-full bg-surface-container text-outline text-xs hover:ring-1 hover:ring-primary/40"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
            search
          </span>
          <span className="flex-1 text-left">Search posts...</span>
          <kbd className="font-mono text-[10px] px-1.5 py-1 rounded bg-surface-container-high">Ctrl K</kbd>
        </button>
        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <button
            type="button"
            aria-label="Search posts"
            onClick={() => {
              setMenuOpen(false);
              setSearchOpen(true);
            }}
            className="md:hidden w-11 h-11 grid place-items-center rounded-lg bg-surface-container text-secondary"
          >
            <span aria-hidden="true" className="material-symbols-outlined">
              search
            </span>
          </button>
          <Link
            to="/posts/new"
            aria-label="Create post"
            onClick={() => setMenuOpen(false)}
            className="h-11 min-w-11 px-2 sm:px-3.5 rounded-lg bg-gradient-to-r from-primary-container to-primary text-on-primary-fixed font-semibold text-xs shadow-[0_0_12px_rgba(160,120,255,0.35)] inline-flex items-center justify-center gap-1.5 transition-shadow hover:shadow-[0_0_20px_rgba(160,120,255,0.5)]"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
              add
            </span>
            <span className="hidden sm:inline">Create Post</span>
          </Link>
          <div className="hidden xl:flex items-center gap-2">{sessionControls}</div>
          <button
            ref={menuButton}
            type="button"
            aria-label="Toggle navigation menu"
            aria-expanded={isMenuOpen}
            aria-controls="mobile-navigation"
            onClick={() => setMenuOpen(!isMenuOpen)}
            className="xl:hidden w-11 h-11 grid place-items-center rounded-lg bg-surface-container"
          >
            <span aria-hidden="true" className="material-symbols-outlined">
              {isMenuOpen ? 'close' : 'menu'}
            </span>
          </button>
        </div>
      </div>
      {isMenuOpen && (
        <nav
          id="mobile-navigation"
          aria-label="Mobile navigation"
          className="xl:hidden border-t border-surface-container-highest px-4 py-3 flex flex-col gap-1 max-h-[calc(100dvh-4rem)] overflow-y-auto"
        >
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `min-h-11 px-3 py-3 rounded-lg text-sm ${isActive ? 'bg-surface-container text-secondary' : 'text-on-surface-variant hover:bg-surface-container-high'}`
              }
            >
              {item.label}
            </NavLink>
          ))}
          <div className="flex flex-wrap gap-2 border-t border-surface-container-highest pt-3 mt-2">{sessionControls}</div>
        </nav>
      )}
    </header>
  );
}
