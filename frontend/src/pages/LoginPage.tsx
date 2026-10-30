import { useState } from 'react';
import { Link } from 'react-router-dom';

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState('');
  return (
    <div className="auth-page w-full min-h-[calc(100dvh-12rem)] relative isolate flex flex-col items-center justify-center px-4 py-10 sm:py-14">
      <div aria-hidden="true" className="auth-glows absolute inset-0 pointer-events-none overflow-clip -z-10">
        <div className="absolute -top-16 -left-20 w-80 h-80 rounded-full bg-primary-container/20 blur-3xl" />
        <div className="absolute -bottom-20 -right-20 w-96 h-96 rounded-full bg-secondary-container/15 blur-3xl" />
      </div>
      <div className="relative w-full max-w-md bg-surface-container-low/95 backdrop-blur-xl rounded-xl p-6 sm:p-8 shadow-2xl border border-surface-container-highest/40">
        <div
          aria-hidden="true"
          className="absolute top-0 left-4 right-4 h-[2px] bg-gradient-to-r from-transparent via-primary to-secondary"
        />
        <div className="flex items-center justify-between gap-3 mb-6">
          <span className="inline-flex items-center gap-1.5 bg-surface-container-high px-3 py-1.5 rounded-full text-secondary text-[10px] uppercase tracking-wider font-semibold">
            <span aria-hidden="true" className="material-symbols-outlined text-[15px]">
              bolt
            </span>
            Welcome back
          </span>
          <span className="text-xs text-outline">Form preview</span>
        </div>
        <div className="text-center mb-7">
          <div className="relative w-20 h-20 mx-auto mb-4">
            <div aria-hidden="true" className="absolute inset-0 bg-primary/20 blur-xl rounded-xl" />
            <img
              src="/assets/illustrations/brand-placeholder.svg"
              alt=""
              className="relative w-full h-full rounded-xl border border-primary/20"
            />
          </div>
          <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-2xl">
            Welcome Back to <span className="text-primary">AuraMeme</span>
          </h1>
          <p id="login-preview" className="text-xs text-on-surface-variant leading-relaxed mt-3">
            Explore the sign-in form. Authentication is not connected yet, and this preview does not send or
            save your details.
          </p>
        </div>
        <form
          aria-describedby="login-preview"
          onSubmit={(event) => {
            event.preventDefault();
            setMessage('Sign-in is not connected yet. No request was sent and no session was created.');
          }}
          className="flex flex-col gap-5"
        >
          <div>
            <label htmlFor="login-username" className="block text-xs font-semibold mb-2">
              Email or username
            </label>
            <input
              id="login-username"
              name="username"
              autoComplete="username"
              required
              placeholder="Your email or username"
              className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 px-4 py-3 text-sm placeholder:text-outline"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-xs font-semibold mb-2">
              Password
            </label>
            <div className="relative">
              <input
                id="login-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                placeholder="Your password"
                className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 pl-4 pr-14 py-3 text-sm placeholder:text-outline"
              />
              <button
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-1 top-0 bottom-0 w-11 grid place-items-center text-outline hover:text-primary"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
                  {showPassword ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="w-full min-h-12 rounded-lg bg-gradient-to-r from-primary-container via-primary-fixed-dim to-secondary text-on-primary-fixed font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg hover:shadow-primary/20 transition-shadow flex items-center justify-center gap-2"
          >
            Preview sign-in
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
              arrow_forward
            </span>
          </button>
        </form>
        {message && (
          <p
            role="status"
            className="mt-4 rounded-lg bg-secondary/10 border border-secondary/20 p-3 text-xs text-secondary leading-relaxed"
          >
            {message}
          </p>
        )}
        <p className="text-center text-xs text-on-surface-variant mt-6 border-t border-surface-container-highest/40 pt-5">
          New around here?{' '}
          <Link to="/register" className="text-primary font-semibold underline underline-offset-4">
            Explore registration
          </Link>
        </p>
      </div>
    </div>
  );
}
