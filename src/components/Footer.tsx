import { Link, useLocation } from 'react-router-dom';
import React from 'react';
import { useUI } from '../context/UIContext';

export const Footer: React.FC = () => {
  const currentPage = useLocation().pathname.slice(1) || 'home';
  const { showNitroPreview } = useUI();

  return (
    <footer className="w-full bg-[#0d0e15] border-t border-[#292932]/50 mt-auto">
      <div className="w-full px-4 lg:px-6 py-8">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 pb-8">
          {/* Brand Column */}
          <div className="lg:col-span-2 flex flex-col items-start gap-3">
            <div className="flex items-center gap-2">
              <img
                alt="AuraMeme Logo"
                className="h-7 w-auto object-contain"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCWoRMYIaBVINCL_MTf9Zk3GzutX04010cTJLx92wBCAIGRdeTiu1I1cEKT8HDw4ZCuAm6n3Rr3RS4Ze7b6T1E3TTY9S2b9p-1Blr6jI5t4jDyr38F4poOB7UQnZEmtYXWoi1j9Bd1sGljpfCxbzpj2K7FMqdYHJOzEC_wxs_gqY54cJ7bNcDQR5MSD3OnHXhwth61N76thr9k5NpM6zK-vfwsEaPjfaOAbnTSEWUZUshYHsJwR2gg"
              />
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-lg bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                AuraMeme
              </span>
            </div>
            <p className="font-['Inter'] text-xs text-on-surface-variant max-w-sm leading-relaxed">
              The definitive web3 meme playground. Forge rare internet artifacts, boost your daily Aura streaks, and claim high-tier community status.
            </p>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-low text-on-surface-variant font-['JetBrains_Mono'] text-xs shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]">
              <span className="material-symbols-outlined text-[14px] text-primary">school</span>
              CS302 Web Dev Project • React + Vite
            </div>
          </div>

          {/* Quick Links */}
          <div className="flex flex-col gap-2">
            <span className="font-['Inter'] font-semibold text-xs uppercase tracking-wider text-on-surface">Quick Links</span>
            <nav className="flex flex-col gap-1.5">
              <Link to="/"

                className={`text-left font-['Inter'] text-xs transition-colors cursor-pointer ${
                  currentPage === 'home' ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Home
              </Link>
              <Link to="/explore"

                className={`text-left font-['Inter'] text-xs transition-colors cursor-pointer ${
                  currentPage === 'explore' ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Explore
              </Link>
              <Link to="/explore"

                className="text-left font-['Inter'] text-xs text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer"
              >
                Leaderboard
              </Link>
              <button
                onClick={() => showNitroPreview()}
                className="text-left font-['Inter'] text-xs text-on-surface-variant hover:text-secondary transition-colors cursor-pointer"
              >
                Nitro Perks
              </button>
              <Link to="/about-us"

                className="text-left font-['Inter'] text-xs text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer"
              >
                Community Guidelines
              </Link>
            </nav>
          </div>

          {/* Platform */}
          <div className="flex flex-col gap-2">
            <span className="font-['Inter'] font-semibold text-xs uppercase tracking-wider text-on-surface">Platform</span>
            <nav className="flex flex-col gap-1.5">
              <Link to="/about-us"

                className={`text-left font-['Inter'] text-xs transition-colors cursor-pointer ${
                  currentPage === 'about-us' ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                About Us
              </Link>
              <Link to="/team"

                className={`text-left font-['Inter'] text-xs transition-colors cursor-pointer ${
                  currentPage === 'team' ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                The Team
              </Link>
              <Link to="/contact"

                className={`text-left font-['Inter'] text-xs transition-colors cursor-pointer ${
                  currentPage === 'contact' ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                Contact Support
              </Link>
              <Link to="/about-us"

                className="text-left font-['Inter'] text-xs text-on-surface-variant hover:text-on-surface transition-colors cursor-pointer"
              >
                Privacy Policy
              </Link>
            </nav>
          </div>

          {/* Community */}
          <div className="flex flex-col gap-2">
            <span className="font-['Inter'] font-semibold text-xs uppercase tracking-wider text-on-surface">Community</span>
            <nav className="flex flex-col gap-1.5">
              <a
                href="https://discord.com"
                target="_blank"
                rel="noreferrer"
                className="font-['Inter'] text-xs text-on-surface-variant hover:text-secondary transition-colors"
              >
                Discord Server
              </a>
              <a
                href="https://github.com/lebaokhang123/aura_meme"
                target="_blank"
                rel="noreferrer"
                className="font-['Inter'] text-xs text-on-surface-variant hover:text-primary transition-colors"
              >
                GitHub Repository
              </a>
              <a
                href="https://reddit.com"
                target="_blank"
                rel="noreferrer"
                className="font-['Inter'] text-xs text-on-surface-variant hover:text-on-surface transition-colors"
              >
                Reddit Sub
              </a>
            </nav>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="max-w-7xl mx-auto pt-6 border-t border-surface-container-highest/40 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <p className="font-['Inter'] text-xs text-outline">
            © 2025 AuraMeme. All rights reserved. Crafted for night owls and meme artisans.
          </p>
          <div className="flex items-center gap-4 font-['Inter'] text-xs text-outline">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
              All nodes operational
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};
