import { useState } from 'react';
import { Link } from 'react-router-dom';
import { evaluatePasswordStrength } from '../utils/format';

export function SignUpPage() {
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState('');
  const strength = evaluatePasswordStrength(password);
  return (
    <div className="auth-page relative isolate w-full min-h-[calc(100dvh-12rem)] flex flex-col items-center justify-center px-4 py-10 sm:py-14">
      <div aria-hidden="true" className="auth-glows absolute inset-0 pointer-events-none overflow-clip -z-10">
        <div className="absolute -top-16 -left-16 w-80 h-80 rounded-full bg-primary-container/20 blur-3xl" />
        <div className="absolute -bottom-16 -right-16 w-96 h-96 rounded-full bg-secondary/10 blur-3xl" />
      </div>
      <div className="relative w-full max-w-[560px] bg-surface-container-low/95 backdrop-blur-xl rounded-xl shadow-2xl p-6 sm:p-10 border border-surface-container-highest/40">
        <div className="text-center">
          <img
            src="/assets/illustrations/brand-placeholder.svg"
            alt=""
            className="w-16 h-16 rounded-xl mx-auto mb-4 shadow-lg"
          />
          <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-2xl sm:text-3xl">
            Create Your Aura Account
          </h1>
          <p
            id="register-preview"
            className="text-xs sm:text-sm text-on-surface-variant leading-relaxed mt-3"
          >
            Your community identity starts here. This is a form preview; registration is not connected and no
            account will be created.
          </p>
        </div>
        <div className="mt-6 p-3 flex items-center gap-3 rounded-lg bg-gradient-to-r from-primary/10 to-secondary/10 border border-primary/15">
          <span aria-hidden="true" className="material-symbols-outlined text-secondary">
            auto_awesome
          </span>
          <p className="text-xs text-on-surface-variant">
            A little more personality for your corner of the internet.
          </p>
        </div>
        <form
          aria-describedby="register-preview"
          className="flex flex-col gap-5 mt-6"
          onSubmit={(event) => {
            event.preventDefault();
            setMessage(
              password !== confirmation
                ? 'Passwords do not match. This is a local form check only.'
                : 'Registration is not connected yet. No account was created and no request was sent.',
            );
          }}
        >
          <div>
            <label htmlFor="register-username" className="text-xs font-semibold block mb-2">
              Username
            </label>
            <input
              id="register-username"
              name="username"
              autoComplete="username"
              required
              placeholder="Choose a username"
              className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 px-4 py-3 text-sm placeholder:text-outline"
            />
          </div>
          <div>
            <label htmlFor="register-email" className="text-xs font-semibold block mb-2">
              Email
            </label>
            <input
              id="register-email"
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@example.com"
              className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 px-4 py-3 text-sm placeholder:text-outline"
            />
          </div>
          <div>
            <div className="flex justify-between items-center gap-3 mb-2">
              <label htmlFor="register-password" className="text-xs font-semibold">
                Password
              </label>
              <span className={`text-xs ${strength.color}`}>{strength.label}</span>
            </div>
            <div className="relative">
              <input
                id="register-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                required
                aria-describedby="strength-note"
                placeholder="Choose a password"
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
            <div aria-hidden="true" className="flex gap-1 mt-3">
              {[1, 2, 3].map((segment) => (
                <span
                  key={segment}
                  className={`h-1 flex-1 rounded-full ${strength.score >= segment ? 'bg-secondary' : 'bg-surface-container-highest'}`}
                />
              ))}
            </div>
            <p id="strength-note" className="text-[10px] text-outline mt-2">
              Length hint only; the account password policy is not connected.
            </p>
          </div>
          <div>
            <label htmlFor="confirm-password" className="text-xs font-semibold block mb-2">
              Confirm password
            </label>
            <input
              id="confirm-password"
              name="password_confirmation"
              type="password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              autoComplete="new-password"
              required
              placeholder="Repeat your password"
              className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 px-4 py-3 text-sm placeholder:text-outline"
            />
          </div>
          <button
            type="submit"
            className="w-full min-h-12 rounded-lg bg-gradient-to-r from-primary-container via-primary-fixed-dim to-secondary text-on-primary-fixed font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg hover:shadow-primary/20 transition-shadow flex items-center justify-center gap-2"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
              bolt
            </span>
            Preview registration
          </button>
        </form>
        {message && (
          <p
            role="status"
            className="rounded-lg bg-secondary/10 border border-secondary/20 p-3 mt-4 text-xs text-secondary leading-relaxed"
          >
            {message}
          </p>
        )}
        <p className="text-center text-xs text-on-surface-variant mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-primary font-semibold underline underline-offset-4">
            Explore sign-in
          </Link>
        </p>
      </div>
    </div>
  );
}
