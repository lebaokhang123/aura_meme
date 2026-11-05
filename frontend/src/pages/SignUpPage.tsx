import { useState } from 'react';
import { Link } from 'react-router-dom';
import { evaluatePasswordStrength } from '../utils/format';
import { api, errorMessage } from '../api';

export function SignUpPage() {
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(false);
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
            Create your community identity. After registration, sign in to start posting.
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
          onSubmit={async (event) => {
            event.preventDefault();
            if (busy || created) return;
            if (password !== confirmation) { setMessage('Passwords do not match.'); return; }
            const data = new FormData(event.currentTarget);
            setBusy(true); setMessage('');
            try {
              await api('/auth/register', { method: 'POST', body: { username: data.get('username'), email: data.get('email'), display_name: data.get('display_name'), password } });
              setCreated(true); setPassword(''); setConfirmation('');
              setMessage('Account created. Sign in to continue.');
            } catch (error) { setMessage(errorMessage(error)); }
            finally { setBusy(false); }
          }}
        >
          <div>
            <label htmlFor="register-username" className="text-xs font-semibold block mb-2">
              Username
            </label>
            <input
              id="register-username"
              name="username"
              pattern="[a-z0-9_]{3,32}"
              minLength={3}
              maxLength={32}
              autoComplete="username"
              required
              placeholder="Choose a username"
              className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 px-4 py-3 text-sm placeholder:text-outline"
            />
          </div>
          <div>
            <label htmlFor="register-name" className="text-xs font-semibold block mb-2">Display name</label>
            <input id="register-name" name="display_name" required maxLength={80} autoComplete="nickname"
              className="w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest/50 px-4 py-3 text-sm" />
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
                minLength={12}
                maxLength={128}
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
              Use 12–128 characters. This meter is a length hint, not a security guarantee.
            </p>
          </div>
          <div>
            <label htmlFor="confirm-password" className="text-xs font-semibold block mb-2">
              Confirm password
            </label>
            <input
              id="confirm-password"
              name="password_confirmation"
              aria-invalid={message === 'Passwords do not match.'}
              aria-describedby={message ? 'registration-feedback' : undefined}
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
            disabled={busy || created}
            className="w-full min-h-12 rounded-lg bg-gradient-to-r from-primary-container via-primary-fixed-dim to-secondary text-on-primary-fixed font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-lg hover:shadow-primary/20 transition-shadow flex items-center justify-center gap-2"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
              bolt
            </span>
            {busy ? 'Creating account…' : created ? 'Account created' : 'Create account'}
          </button>
        </form>
        {message && (
          <p
            id="registration-feedback"
            role={created ? 'status' : 'alert'}
            className="rounded-lg bg-secondary/10 border border-secondary/20 p-3 mt-4 text-xs text-secondary leading-relaxed"
          >
            {message}
          </p>
        )}
        <p className="text-center text-xs text-on-surface-variant mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-primary font-semibold underline underline-offset-4">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
