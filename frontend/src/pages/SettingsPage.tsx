import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, errorMessage } from '../api';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';

export function SettingsPage() {
  const { user, refresh } = useAuth();
  const { showToast } = useUI();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!user) return null;
  const fail = async (fault: unknown) => {
    setError(errorMessage(fault));
    if (fault instanceof ApiError && fault.status === 401) await refresh();
  };
  const input = 'w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest px-4 py-3 mt-2';
  const button = 'min-h-11 rounded-lg bg-primary text-on-primary px-5 py-3 font-semibold disabled:opacity-50';
  return <section className="w-full max-w-2xl mx-auto px-4 py-10">
    <h1 className="text-3xl font-bold">Account settings</h1>
    <p className="mt-3 text-on-surface-variant">Signed in as {user.username}. <Link className="text-secondary underline" to={'/profile/' + user.username}>View public profile</Link></p>
    {error && <p role="alert" className="mt-4 text-primary">{error}</p>}
    <form className="surface-panel bg-surface-container-low p-6 rounded-xl my-6 grid gap-5" onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      const data = new FormData(event.currentTarget);
      const body: Record<string, unknown> = { display_name: data.get('display_name') };
      for (const name of ['bio', 'address', 'phone']) body[name] = data.get(name) || null;
      body.birth_year = data.get('birth_year') ? Number(data.get('birth_year')) : null;
      setBusy(true); setError('');
      try { await api('/users/me', { method: 'PATCH', body }); await refresh(); showToast('Profile saved.'); }
      catch (fault) { await fail(fault); } finally { setBusy(false); }
    }}>
      <h2 className="text-xl font-bold">Profile</h2>
      <label>Display name<input className={input} name="display_name" defaultValue={user.display_name} required maxLength={80} autoComplete="nickname" /></label>
      <label>Bio<textarea className={input} name="bio" defaultValue={user.bio ?? ''} maxLength={1000} rows={3} /></label>
      <label>Birth year<input className={input} name="birth_year" type="number" min={1900} max={new Date().getFullYear()} defaultValue={user.birth_year ?? ''} autoComplete="bday-year" /></label>
      <label>Address (private)<input className={input} name="address" defaultValue={user.address ?? ''} maxLength={255} autoComplete="street-address" /></label>
      <label>Phone (private)<input className={input} name="phone" type="tel" defaultValue={user.phone ?? ''} maxLength={30} autoComplete="tel" /></label>
      <button className={button} disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button>
    </form>
    <form className="surface-panel bg-surface-container-low p-6 rounded-xl grid gap-5" onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      const form = event.currentTarget, data = new FormData(form);
      if (data.get('new_password') !== data.get('confirmation')) { setError('Passwords do not match.'); return; }
      setBusy(true); setError('');
      try {
        await api('/users/me/password', { method: 'PUT', body: { current_password: data.get('current_password'), new_password: data.get('new_password') } });
        form.reset(); showToast('Password changed. Other sessions have been signed out.');
      } catch (fault) { await fail(fault); } finally { setBusy(false); }
    }}>
      <h2 className="text-xl font-bold">Change password</h2>
      <label>Current password<input className={input} name="current_password" type="password" required autoComplete="current-password" /></label>
      <label>New password<input className={input} name="new_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
      <label>Confirm new password<input className={input} name="confirmation" type="password" required autoComplete="new-password" /></label>
      <button className={button} disabled={busy}>{busy ? 'Saving…' : 'Change password'}</button>
    </form>
  </section>;
}
