import { Link } from 'react-router-dom';
import React, { useState } from 'react';
import { useUI } from '../context/UIContext';

export const LoginPage: React.FC = () => {
  const { showToast } = useUI();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const isSubmitting = false;
  const [status, setStatus] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  const fillDemoCredentials = () => {
    setUsername('admin');
    setPassword('aura123');
    showToast('✨ Demo credentials injected: admin / aura123');
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setStatus({ type: 'info', message: 'Demo form only. No sign-in request is sent or saved.' });
  };

  const handleSocial = (provider: string) => {
    setStatus({ type: 'info', message: `${provider} sign-in is a UI preview only.` });
  };

  return (
    <div className="w-full min-h-[calc(100vh-16rem)] flex flex-col justify-center items-center px-4 py-8 relative">
      {/* Ambient glow backdrop blooms */}
      <div className="absolute -top-16 -left-20 w-80 h-80 rounded-full bg-primary-container/20 blur-3xl pointer-events-none -z-10" />
      <div className="absolute -bottom-20 -right-20 w-96 h-96 rounded-full bg-secondary-container/20 blur-3xl pointer-events-none -z-10" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 rounded-full bg-tertiary-container/15 blur-2xl pointer-events-none -z-10" />

      {/* Main Card Container */}
      <div className="w-full max-w-md bg-surface-container-low/95 backdrop-blur-xl rounded-xl p-6 sm:p-8 shadow-2xl relative overflow-hidden border border-surface-container-highest/40 transition-all duration-300">
        {/* Top Glowing Accent Line */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-primary to-secondary" />

        {/* Live Status / Daily Bonus Pill Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="inline-flex items-center gap-1.5 bg-surface-container-high px-3 py-1 rounded-full text-secondary">
            <span className="material-symbols-outlined text-[15px] animate-pulse">bolt</span>
            <span className="font-['Inter'] text-[11px] font-bold tracking-wider uppercase">
              Daily Aura Drop Active
            </span>
          </div>
          <div className="inline-flex items-center gap-1 text-primary bg-primary/10 px-2.5 py-1 rounded-full">
            <span className="material-symbols-outlined text-[14px]">local_fire_department</span>
            <span className="font-['JetBrains_Mono'] text-xs font-semibold">+250 XP</span>
          </div>
        </div>

        {/* Logo & Title Section */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="relative group cursor-pointer mb-3">
            <div className="absolute inset-0 bg-primary/30 rounded-xl blur-lg group-hover:blur-xl transition-all duration-300" />
            <div className="relative w-20 h-20 bg-surface-container-lowest rounded-xl flex items-center justify-center p-2 shadow-inner border border-surface-container-highest/30">
              <img
                alt="AuraMeme Logo"
                className="w-full h-full object-contain filter drop-shadow-[0_0_12px_rgba(208,188,255,0.7)]"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCWoRMYIaBVINCL_MTf9Zk3GzutX04010cTJLx92wBCAIGRdeTiu1I1cEKT8HDw4ZCuAm6n3Rr3RS4Ze7b6T1E3TTY9S2b9p-1Blr6jI5t4jDyr38F4poOB7UQnZEmtYXWoi1j9Bd1sGljpfCxbzpj2K7FMqdYHJOzEC_wxs_gqY54cJ7bNcDQR5MSD3OnHXhwth61N76thr9k5NpM6zK-vfwsEaPjfaOAbnTSEWUZUshYHsJwR2gg"
              />
            </div>
          </div>
          <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-2xl text-on-surface tracking-tight mb-1">
            Welcome Back to{' '}
            <span className="bg-gradient-to-r from-primary via-primary-fixed-dim to-secondary bg-clip-text text-transparent">
              AuraMeme
            </span>
          </h1>
          <p className="font-['Inter'] text-xs text-on-surface-variant max-w-xs">
            Log in to claim your daily Aura bonus and react to the hottest memes.
          </p>
        </div>

        {/* Quick Credential Helper Pill */}
        <div className="mb-5 bg-surface-container-lowest rounded-lg p-2.5 flex items-center justify-between gap-2 border border-surface-container-highest/30">
          <div className="flex items-center gap-2 min-w-0">
            <span className="material-symbols-outlined text-secondary text-[18px]">terminal</span>
            <div className="font-['JetBrains_Mono'] text-xs text-on-surface-variant truncate">
              admin <span className="text-outline">/</span> aura123
            </div>
          </div>
          <button
            onClick={fillDemoCredentials}
            className="bg-surface-container-high hover:bg-surface-bright text-secondary font-['Inter'] text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors flex items-center gap-1 shrink-0 cursor-pointer"
            type="button"
          >
            <span>Auto-fill</span>
            <span className="material-symbols-outlined text-[13px]">play_arrow</span>
          </button>
        </div>

        {/* Authentication Form */}
        <p className="text-xs text-secondary mb-3">UI demo only. No data is sent or saved.</p>
              <form className="space-y-4" onSubmit={handleLogin}>
          {/* Username / Email Field */}
          <div>
            <label className="block font-['Inter'] font-semibold text-xs text-on-surface mb-1">
              Email or Username
            </label>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3.5 text-outline text-[18px] pointer-events-none">
                alternate_email
              </span>
              <input
                className="w-full pl-10 pr-4 py-2.5 bg-surface-container-lowest text-on-surface rounded-lg font-['Inter'] text-xs placeholder:text-outline-variant focus:outline-none focus:bg-surface-container-high focus:ring-1 focus:ring-primary transition-all border border-surface-container-highest/30"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username or college email"
                required
                type="text"
              />
            </div>
          </div>

          {/* Password Field */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="font-['Inter'] font-semibold text-xs text-on-surface">Password</label>
              <button
                type="button"
                onClick={() => showToast('🔑 Reset link sent to your registered college email.')}
                className="font-['Inter'] text-[11px] text-secondary hover:underline cursor-pointer"
              >
                Forgot password?
              </button>
            </div>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3.5 text-outline text-[18px] pointer-events-none">
                lock
              </span>
              <input
                className="w-full pl-10 pr-11 py-2.5 bg-surface-container-lowest text-on-surface rounded-lg font-['Inter'] text-xs placeholder:text-outline-variant focus:outline-none focus:bg-surface-container-high focus:ring-1 focus:ring-primary transition-all border border-surface-container-highest/30"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                type={showPassword ? 'text' : 'password'}
              />
              <button
                aria-label="Toggle password view"
                className="absolute right-3 text-outline hover:text-on-surface p-1 rounded transition-colors focus:outline-none cursor-pointer"
                onClick={() => setShowPassword(!showPassword)}
                type="button"
              >
                <span className="material-symbols-outlined text-[18px]">
                  {showPassword ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>

          {/* Remember Me Checkbox */}
          <div className="flex items-center justify-between pt-1">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                className="w-4 h-4 rounded bg-surface-container-lowest text-primary accent-primary focus:ring-0 cursor-pointer"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                type="checkbox"
              />
              <span className="font-['Inter'] text-xs text-on-surface-variant">Remember my device</span>
            </label>
            <span className="font-['Inter'] text-[11px] text-outline flex items-center gap-1">
              <span className="material-symbols-outlined text-[13px] text-tertiary">verified_user</span> 256-bit safe
            </span>
          </div>

          {/* Login Submit Button */}
          <button
            disabled={isSubmitting}
            className="w-full mt-2 py-3 px-4 rounded-lg bg-gradient-to-r from-primary-container via-primary to-secondary-container text-on-primary-fixed font-['Plus_Jakarta_Sans'] font-bold text-sm tracking-wide shadow-lg hover:shadow-primary/30 hover:scale-[1.01] active:scale-[0.99] transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60"
            type="submit"
          >
            {isSubmitting ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                <span>Authenticating Aura...</span>
              </>
            ) : (
              <>
                <span>Log In</span>
                <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
              </>
            )}
          </button>

          {/* Feedback Message */}
          {status && (
            <div
              className={`font-['Inter'] text-xs p-2.5 rounded-lg text-center ${
                status.type === 'success'
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : status.type === 'error'
                  ? 'bg-error-container text-error'
                  : 'bg-surface-container-high text-secondary'
              }`}
            >
              {status.message}
            </div>
          )}
        </form>

        {/* Social Divider */}
        <div className="relative my-6 flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full h-px bg-surface-container-highest" />
          </div>
          <span className="relative px-3 bg-surface-container-low font-['Inter'] text-[11px] text-outline uppercase tracking-wider">
            Or continue with
          </span>
        </div>

        {/* Social Sign In Matrix */}
        <div className="grid grid-cols-2 gap-3">
          <button
            className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg bg-[#5865F2]/15 hover:bg-[#5865F2]/25 text-on-surface hover:text-[#5865F2] font-['Inter'] font-semibold text-xs transition-all cursor-pointer"
            onClick={() => handleSocial('Discord')}
            type="button"
          >
            <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
            </svg>
            <span>Discord</span>
          </button>

          <button
            className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface font-['Inter'] font-semibold text-xs transition-all cursor-pointer"
            onClick={() => handleSocial('Google')}
            type="button"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335" />
            </svg>
            <span>Google</span>
          </button>
        </div>

        {/* Registration Callout Footer */}
        <div className="mt-6 pt-4 bg-surface-container/60 -mx-6 sm:-mx-8 -mb-6 sm:-mb-8 px-6 sm:px-8 pb-6 flex flex-col items-center text-center border-t border-surface-container-highest/20">
          <div className="flex items-center gap-1.5 text-on-surface-variant font-['Inter'] text-xs">
            <span>Don&apos;t have an Aura account?</span>
            <Link to="/register"

              className="text-secondary hover:text-secondary-fixed font-['Inter'] font-semibold text-xs inline-flex items-center gap-0.5 cursor-pointer"
            >
              Sign Up
              <span className="material-symbols-outlined text-[14px]">arrow_outward</span>
            </Link>
          </div>
          <div className="mt-2 inline-flex items-center gap-1.5 bg-secondary-container/20 px-3 py-1 rounded-full text-secondary">
            <span className="material-symbols-outlined text-[14px]">stars</span>
            <span className="font-['Inter'] text-[11px] font-bold">+100 Starter Aura on registration</span>
          </div>
        </div>
      </div>

      {/* Micro Footer Information */}
      <div className="mt-6 flex items-center gap-4 text-outline font-['Inter'] text-xs">
        <Link to="/about-us"  className="hover:text-on-surface transition-colors cursor-pointer">
          Rules of Aura
        </Link>
        <span>•</span>
        <Link to="/about-us"  className="hover:text-on-surface transition-colors cursor-pointer">
          Privacy
        </Link>
        <span>•</span>
        <Link to="/contact"  className="hover:text-on-surface transition-colors cursor-pointer">
          Meme API
        </Link>
        <span>•</span>
        <span className="text-primary font-['JetBrains_Mono']">v2.4-quantum</span>
      </div>
    </div>
  );
};
