import { Link, useLocation } from 'react-router-dom';
import React, { useState } from 'react';
import { useUI } from '../context/UIContext';
import { levelInfo } from '../data/mockData';

export const Header: React.FC = () => {
  const currentPage = useLocation().pathname.slice(1) || 'home';
  const {
    showCreatePostPreview,
    showNitroPreview,
    setSearchOpen,
    showToast,
  } = useUI();

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navItems: { label: string; page: 'home' | 'explore' | 'about-us' | 'team' | 'contact' }[] = [
    { label: 'Home', page: 'home' },
    { label: 'Explore', page: 'explore' },
    { label: 'About Us', page: 'about-us' },
    { label: 'Team', page: 'team' },
    { label: 'Contact', page: 'contact' },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[#0d0e15]/90 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.35)] border-b border-[#292932]/40">
      <div className="h-16 w-full px-4 lg:px-6 flex items-center justify-between gap-3">
        {/* Left: Brand + Level + Desktop Nav */}
        <div className="flex items-center gap-4 lg:gap-5 shrink-0">
          <Link to="/"

            className="flex items-center gap-2 group cursor-pointer text-left focus:outline-none"
          >
            <img
              alt="AuraMeme Logo"
              className="h-8 w-auto object-contain drop-shadow-[0_0_8px_rgba(208,188,255,0.4)]"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuCWoRMYIaBVINCL_MTf9Zk3GzutX04010cTJLx92wBCAIGRdeTiu1I1cEKT8HDw4ZCuAm6n3Rr3RS4Ze7b6T1E3TTY9S2b9p-1Blr6jI5t4jDyr38F4poOB7UQnZEmtYXWoi1j9Bd1sGljpfCxbzpj2K7FMqdYHJOzEC_wxs_gqY54cJ7bNcDQR5MSD3OnHXhwth61N76thr9k5NpM6zK-vfwsEaPjfaOAbnTSEWUZUshYHsJwR2gg"
            />
            <span className="font-['Plus_Jakarta_Sans'] font-bold text-xl bg-gradient-to-r from-primary via-primary-container to-secondary bg-clip-text text-transparent group-hover:opacity-90 transition-opacity">
              AuraMeme
            </span>
          </Link>

          {/* Level Pill */}
          <div className="hidden sm:inline-flex items-center px-2.5 py-1 rounded-full bg-surface-container-high text-secondary font-['Inter'] text-xs font-bold tracking-wider uppercase shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]">
            <span className="material-symbols-outlined text-[14px] mr-1 text-secondary">bolt</span>
            LVL {levelInfo.level}
          </div>

          {/* Desktop Nav Links */}
          <nav className="hidden xl:flex items-center gap-1 pl-2">
            {navItems.map((item) => {
              const isActive = currentPage === item.page;
              return (
                <Link to={item.page === 'home' ? '/' : `/${item.page}`}
                  key={item.page}

                  className={`px-3 py-1.5 rounded-lg font-['Inter'] text-[13px] font-semibold transition-all cursor-pointer ${
                    isActive
                      ? 'bg-surface-container text-on-surface shadow-sm'
                      : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Center: Search Bar with Ctrl + K */}
        <div className="flex-1 max-w-md hidden md:block">
          <div
            onClick={() => setSearchOpen(true)}
            className="relative flex items-center cursor-pointer group"
          >
            <span className="material-symbols-outlined absolute left-3 text-outline text-[18px] pointer-events-none group-hover:text-primary transition-colors">
              search
            </span>
            <input
              readOnly
              className="w-full h-9 pl-10 pr-16 bg-surface-container rounded-full text-on-surface placeholder:text-outline font-['Inter'] text-xs focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer transition-all"
              aria-label="Search memes"
              placeholder="Search memes, tags, aura creators..."
              type="text"
            />
            <kbd className="absolute right-2 px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant font-['JetBrains_Mono'] text-[11px] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]">
              Ctrl + K
            </kbd>
          </div>
        </div>

        {/* Right Actions Dock */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Create Post Button */}
          <button
            onClick={() => showCreatePostPreview()}
            className="inline-flex items-center gap-1.5 h-9 px-2 sm:px-3.5 rounded-lg bg-gradient-to-r from-primary-container to-inverse-primary text-on-primary font-['Inter'] font-semibold text-xs shadow-[0_0_12px_rgba(160,120,255,0.35)] hover:shadow-[0_0_16px_rgba(160,120,255,0.5)] transition-all cursor-pointer"
            type="button"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            <span className="hidden sm:inline">Create Post</span>
          </button>

          {/* Nitro Perks Button */}
          <button
            onClick={() => showNitroPreview()}
            aria-label="Nitro Perks"
            className="hidden sm:flex w-9 h-9 items-center justify-center rounded-lg bg-surface-container text-secondary hover:bg-surface-container-high hover:text-secondary-fixed transition-colors cursor-pointer"
            type="button"
            title="Aura Nitro Perks"
          >
            <span className="material-symbols-outlined text-[20px]">local_fire_department</span>
          </button>

          {/* Notifications Button */}
          <div className="relative hidden sm:block">
            <button
              onClick={() => showToast('🔔 You have 3 new upvote and aura streak notifications!')}
              aria-label="Notifications"
              className="w-9 h-9 flex items-center justify-center rounded-lg bg-surface-container text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors cursor-pointer"
              type="button"
            >
              <span className="material-symbols-outlined text-[20px]">notifications</span>
            </button>
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-error text-on-error font-['Inter'] text-[10px] flex items-center justify-center font-bold">
              3
            </span>
          </div>

          {/* Login & Sign Up or Profile Avatar */}
          <Link to="/login" className="hidden lg:inline-flex px-3 py-2 rounded-lg bg-surface-container text-xs">Login</Link>
          <Link to="/register" className="hidden lg:inline-flex px-3 py-2 rounded-lg bg-primary text-on-primary text-xs">Sign Up</Link>

          {/* Mobile Menu Hamburger */}
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="xl:hidden w-9 h-9 flex items-center justify-center rounded-lg bg-surface-container text-on-surface hover:bg-surface-container-high transition-colors"
            aria-label="Toggle mobile menu" aria-expanded={isMobileMenuOpen}
          >
            <span className="material-symbols-outlined text-[22px]">
              {isMobileMenuOpen ? 'close' : 'menu'}
            </span>
          </button>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {isMobileMenuOpen && (
        <div className="xl:hidden border-t border-surface-container-highest bg-[#12131b] px-4 py-3 flex flex-col gap-2">
          {navItems.map((item) => (
            <Link to={item.page === 'home' ? '/' : `/${item.page}`}
              key={item.page}
              onClick={() => {

                setIsMobileMenuOpen(false);
              }}
              className={`w-full text-left px-3 py-2 rounded-lg font-['Inter'] text-sm font-semibold transition-colors ${
                currentPage === item.page
                  ? 'bg-surface-container text-secondary'
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              }`}
            >
              {item.label}
            </Link>
          ))}
          <div className="pt-2 border-t border-surface-container-highest flex gap-2">
            <Link to="/login" onClick={() => setIsMobileMenuOpen(false)} className="flex-1 py-2 text-center bg-surface-container rounded-lg">Login</Link>
            <Link to="/register" onClick={() => setIsMobileMenuOpen(false)} className="flex-1 py-2 text-center bg-primary text-on-primary rounded-lg">Sign Up</Link>
          </div>
        </div>
      )}
    </header>
  );
};
