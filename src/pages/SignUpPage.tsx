import { Link } from 'react-router-dom';
import React, { useState } from 'react';
import { useUI } from '../context/UIContext';
import { evaluatePasswordStrength } from '../utils/format';

export const SignUpPage: React.FC = () => {
  const { showToast } = useUI();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [showConfirmPass, setShowConfirmPass] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('Anime');
  const [termsAgreed, setTermsAgreed] = useState(true);

  const strength = evaluatePasswordStrength(password);

  const categories = [
    { label: '🎮 Gaming', id: 'Gaming' },
    { label: '🎌 Anime', id: 'Anime' },
    { label: '💻 Tech', id: 'Tech' },
    { label: '🏫 School', id: 'School' },
    { label: '🎲 Random', id: 'Random' },
  ];

  const handleSignUp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) {
      showToast('⚠️ Please enter an Aura username.');
      return;
    }
    if (password !== confirmPassword) {
      showToast('⚠️ Passwords do not match.');
      return;
    }
    if (!termsAgreed) {
      showToast('⚠️ You must accept the community guidelines.');
      return;
    }

    showToast('Demo form only. No account is created or saved.');
  };

  const handleDiscordSignUp = () => {
    showToast('Discord sign-up is a UI preview only.');
  };

  return (
    <div className="w-full min-h-[calc(100vh-16rem)] flex flex-col justify-center items-center px-4 py-8 relative">
      <div className="relative w-full max-w-[560px] flex flex-col items-center">
        {/* Ambient Neon Backdrop Glows */}
        <div className="absolute -top-16 -left-16 w-64 h-64 bg-primary-container/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-16 -right-16 w-64 h-64 bg-secondary-container/20 rounded-full blur-3xl pointer-events-none" />

        {/* Main Registration Shell Card */}
        <div className="relative w-full bg-surface-container-low/90 backdrop-blur-xl rounded-xl shadow-2xl p-6 sm:p-10 flex flex-col gap-6 border border-surface-container-highest/40">
          {/* Logo & Header Block */}
          <div className="flex flex-col items-center text-center">
            <div className="relative flex items-center justify-center mb-3">
              <div className="absolute inset-0 bg-primary/20 rounded-full blur-md" />
              <img
                alt="AuraMeme Logo"
                className="relative w-16 h-16 object-contain drop-shadow-md rounded-lg"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCWoRMYIaBVINCL_MTf9Zk3GzutX04010cTJLx92wBCAIGRdeTiu1I1cEKT8HDw4ZCuAm6n3Rr3RS4Ze7b6T1E3TTY9S2b9p-1Blr6jI5t4jDyr38F4poOB7UQnZEmtYXWoi1j9Bd1sGljpfCxbzpj2K7FMqdYHJOzEC_wxs_gqY54cJ7bNcDQR5MSD3OnHXhwth61N76thr9k5NpM6zK-vfwsEaPjfaOAbnTSEWUZUshYHsJwR2gg"
              />
            </div>
            <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-2xl sm:text-3xl text-on-surface tracking-tight">
              Create Your Aura Account
            </h1>
            <p className="font-['Inter'] text-xs sm:text-sm text-on-surface-variant max-w-sm mt-1 leading-relaxed">
              Join the community, start at Level 1 with 100 Aura points, and climb the ranks.
            </p>
          </div>

          {/* Starter Perk Banner */}
          <div className="relative overflow-hidden rounded-lg bg-surface-container p-3 flex items-center gap-3 shadow-inner border border-surface-container-highest/30">
            <div className="absolute inset-0 bg-gradient-to-r from-primary-container/15 via-secondary/10 to-transparent pointer-events-none" />
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center shrink-0 text-primary">
              <span className="material-symbols-outlined text-[18px]">redeem</span>
            </div>
            <div className="flex flex-col min-w-0 z-10">
              <span className="font-['Inter'] font-bold text-[11px] text-secondary uppercase tracking-wider">
                Starter Perk
              </span>
              <p className="font-['Inter'] text-xs text-on-surface truncate">
                🎁 New Member Bonus:{' '}
                <span className="font-['Inter'] text-primary font-bold">+100 Aura</span> & Novice Creator Badge unlocked on registration!
              </p>
            </div>
          </div>

          {/* Social Signup (Discord) */}
          <button
            onClick={handleDiscordSignUp}
            className="w-full bg-[#5865F2]/15 hover:bg-[#5865F2]/25 text-on-surface transition-all duration-200 py-2.5 px-4 rounded-lg flex items-center justify-center gap-3 font-['Inter'] font-semibold text-xs group shadow-sm cursor-pointer border border-[#5865F2]/30"
            type="button"
          >
            <svg className="w-5 h-5 fill-current text-[#5865F2] group-hover:scale-105 transition-transform" viewBox="0 0 24 24">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.893.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
            </svg>
            <span>
              Sign up with Discord <span className="text-on-surface-variant font-normal text-xs">(Sync Avatar & Tag)</span>
            </span>
          </button>

          {/* Minimal Divider */}
          <div className="flex items-center gap-4">
            <div className="h-[1px] flex-1 bg-surface-container-highest" />
            <span className="font-['Inter'] text-[11px] text-outline uppercase tracking-wider">
              or continue with email
            </span>
            <div className="h-[1px] flex-1 bg-surface-container-highest" />
          </div>

          {/* Registration Form */}
          <p className="text-xs text-secondary mb-3">UI demo only. No data is sent or saved.</p>
              <form className="flex flex-col gap-4" onSubmit={handleSignUp}>
            {/* Username Field */}
            <div className="flex flex-col gap-1.5">
              <label className="font-['Inter'] font-semibold text-xs text-on-surface-variant flex items-center justify-between">
                <span>Username</span>
                <span className="font-['Inter'] text-[11px] text-secondary flex items-center gap-1 font-semibold">
                  <span className="material-symbols-outlined text-[14px]">check_circle</span> Username available
                </span>
              </label>
              <div className="relative flex items-center rounded-lg bg-surface-container-lowest focus-within:ring-1 focus-within:ring-primary transition-all border border-surface-container-highest/30">
                <span className="pl-3.5 pr-1 font-['JetBrains_Mono'] text-xs text-outline select-none">@</span>
                <input
                  className="w-full bg-transparent py-2.5 pr-4 text-on-surface font-['Inter'] text-xs focus:outline-none placeholder:text-outline"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="aura_legend"
                  required
                  type="text"
                />
              </div>
            </div>

            {/* Email Field */}
            <div className="flex flex-col gap-1.5">
              <label className="font-['Inter'] font-semibold text-xs text-on-surface-variant">
                College or Personal Email
              </label>
              <div className="relative flex items-center rounded-lg bg-surface-container-lowest focus-within:ring-1 focus-within:ring-primary transition-all border border-surface-container-highest/30">
                <span className="material-symbols-outlined text-outline pl-3.5 pr-2 text-[18px]">
                  alternate_email
                </span>
                <input
                  className="w-full bg-transparent py-2.5 pr-4 text-on-surface font-['Inter'] text-xs focus:outline-none placeholder:text-outline"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@campus.edu or you@gmail.com"
                  required
                  type="email"
                />
              </div>
            </div>

            {/* Password Field with Indicator */}
            <div className="flex flex-col gap-1.5">
              <label className="font-['Inter'] font-semibold text-xs text-on-surface-variant flex items-center justify-between">
                <span>Password</span>
                <span className={`font-['Inter'] text-[11px] font-bold ${strength.color}`}>
                  {strength.label}
                </span>
              </label>
              <div className="relative flex items-center rounded-lg bg-surface-container-lowest focus-within:ring-1 focus-within:ring-primary transition-all border border-surface-container-highest/30">
                <span className="material-symbols-outlined text-outline pl-3.5 pr-2 text-[18px]">lock</span>
                <input
                  className="w-full bg-transparent py-2.5 pr-10 text-on-surface font-['Inter'] text-xs focus:outline-none placeholder:text-outline"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
                  required
                  type={showPass ? 'text' : 'password'}
                />
                <button
                  className="absolute right-3 text-outline hover:text-on-surface transition-colors cursor-pointer"
                  onClick={() => setShowPass(!showPass)}
                  type="button"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {showPass ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>

              {/* Cyan & Purple Progress Indicator Segments */}
              <div className="grid grid-cols-3 gap-1.5 mt-1">
                <div
                  className={`h-1 rounded-full transition-all ${
                    strength.score >= 1 ? (strength.score === 1 ? 'bg-error' : 'bg-primary') : 'bg-surface-container-highest'
                  }`}
                />
                <div
                  className={`h-1 rounded-full transition-all ${
                    strength.score >= 2 ? 'bg-primary' : 'bg-surface-container-highest'
                  }`}
                />
                <div
                  className={`h-1 rounded-full transition-all ${
                    strength.score >= 3 ? 'bg-secondary' : 'bg-surface-container-highest'
                  }`}
                />
              </div>
            </div>

            {/* Confirm Password Field */}
            <div className="flex flex-col gap-1.5">
              <label className="font-['Inter'] font-semibold text-xs text-on-surface-variant">
                Confirm Password
              </label>
              <div className="relative flex items-center rounded-lg bg-surface-container-lowest focus-within:ring-1 focus-within:ring-primary transition-all border border-surface-container-highest/30">
                <span className="material-symbols-outlined text-outline pl-3.5 pr-2 text-[18px]">
                  verified_user
                </span>
                <input
                  className="w-full bg-transparent py-2.5 pr-10 text-on-surface font-['Inter'] text-xs focus:outline-none placeholder:text-outline"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter your password"
                  required
                  type={showConfirmPass ? 'text' : 'password'}
                />
                <button
                  className="absolute right-3 text-outline hover:text-on-surface transition-colors cursor-pointer"
                  onClick={() => setShowConfirmPass(!showConfirmPass)}
                  type="button"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {showConfirmPass ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            {/* Favorite Meme Category Chips */}
            <div className="flex flex-col gap-2 pt-1">
              <div className="flex items-center justify-between">
                <span className="font-['Inter'] font-semibold text-xs text-on-surface-variant">
                  Favorite Meme Category
                </span>
                <span className="font-['Inter'] text-[11px] text-outline">Tailors your initial feed</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {categories.map((cat) => {
                  const isSelected = selectedCategory === cat.id;
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => setSelectedCategory(cat.id)}
                      className={`px-3 py-1.5 rounded-full font-['Inter'] font-semibold text-xs transition-all duration-200 active:scale-95 flex items-center gap-1.5 cursor-pointer ${
                        isSelected
                          ? 'bg-primary/20 text-primary ring-1 ring-primary/40'
                          : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface'
                      }`}
                    >
                      <span>{cat.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Terms Agreement Checkbox */}
            <div className="flex items-start gap-2.5 pt-2">
              <div className="relative flex items-center pt-0.5">
                <input
                  checked={termsAgreed}
                  onChange={(e) => setTermsAgreed(e.target.checked)}
                  className="w-4 h-4 rounded bg-surface-container-lowest accent-primary text-on-primary cursor-pointer focus:ring-0"
                  id="terms"
                  type="checkbox"
                />
              </div>
              <label
                className="font-['Inter'] text-xs text-on-surface-variant cursor-pointer select-none leading-tight"
                htmlFor="terms"
              >
                I agree to the{' '}
                <Link to="/about-us"
                  type="button"

                  className="text-primary hover:underline cursor-pointer"
                >
                  AuraMeme Community Guidelines & Rules
                </Link>{' '}
                and acknowledge the privacy protocol.
              </label>
            </div>

            {/* Primary Vivid Gradient CTA Button */}
            <button
              className="relative w-full overflow-hidden mt-3 py-3 px-6 rounded-lg bg-gradient-to-r from-primary-container via-inverse-primary to-secondary text-white font-['Plus_Jakarta_Sans'] font-bold text-sm tracking-wide shadow-lg hover:shadow-primary/30 transition-all duration-300 hover:scale-[1.01] active:scale-[0.99] flex items-center justify-center gap-2 group cursor-pointer"
              type="submit"
            >
              <span className="material-symbols-outlined text-[20px] transition-transform group-hover:rotate-12">
                bolt
              </span>
              <span>Claim 100 Aura & Sign Up</span>
              <span className="material-symbols-outlined text-[18px] transition-transform group-hover:translate-x-1">
                arrow_forward
              </span>
            </button>
          </form>

          {/* Bottom Footer Note */}
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-1 text-center font-['Inter'] text-xs text-on-surface-variant">
            <span>Already have an account?</span>
            <Link to="/login"

              className="text-secondary hover:text-secondary-fixed font-['Inter'] font-semibold text-xs hover:underline flex items-center gap-0.5 cursor-pointer"
            >
              Log In
              <span className="material-symbols-outlined text-[14px]">chevron_right</span>
            </Link>
          </div>
        </div>

        {/* Practical React State Mock Info Pill */}
        <div className="mt-4 px-3 py-1.5 rounded-full bg-surface-container-lowest/80 text-outline font-['JetBrains_Mono'] text-xs flex items-center gap-2 text-center select-none border border-surface-container-highest/20">
          <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
          <span>
            Mock state: <span className="text-on-surface">initialAura: 100</span> |{' '}
            <span className="text-on-surface">tier: &quot;Novice Lvl 1&quot;</span>
          </span>
        </div>
      </div>
    </div>
  );
};
