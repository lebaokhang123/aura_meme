import { useEffect, useRef, useState } from 'react';
import { api, ApiError, errorMessage } from '../api';
import type { AdminRow, AdminTab } from '../admin';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';
import { useCategories } from '../hooks/useFeed';

const input = 'block mt-2 w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest p-3';
const button = 'min-h-11 px-4 py-3 rounded-lg bg-primary text-on-primary disabled:opacity-50';

export function AdminEditor({ tab, row, busy, setBusy, onSaved, onClose }: { tab: AdminTab; row: AdminRow | null; busy: boolean; setBusy: (value: boolean) => void; onSaved: () => void; onClose: () => void }) {
  const { user, refresh } = useAuth();
  const { showToast } = useUI();
  const categories = useCategories(tab === 'posts' ? '/admin/categories' : null);
  const [error, setError] = useState('');
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { panel.current?.focus(); }, []);
  const execute = async (path: string, method: string, body?: unknown) => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      await api(path, { method, body });
      showToast('Saved.');
      if (tab === 'users' && row?.id === user?.id) await refresh();
      onSaved();
    } catch (fault) {
      setError(errorMessage(fault));
      if (fault instanceof ApiError && [401, 403].includes(fault.status)) { showToast(errorMessage(fault)); await refresh(); }
    } finally { setBusy(false); }
  };
  const title = tab === 'contacts' ? 'Review contact' : (row ? 'Edit ' : 'Create ') + ({ users: 'user', posts: 'post', categories: 'category', 'audit-logs': 'audit' }[tab]);
  const path = '/admin/' + tab + (row ? '/' + row.id : '');
  return <section ref={panel} tabIndex={-1} aria-labelledby="admin-editor-title" className="surface-panel rounded-xl bg-surface-container-low p-5 sm:p-8 my-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="admin-editor-title" className="text-xl font-bold">{title}</h2><button onClick={onClose} disabled={busy} className="min-h-11 underline">Cancel editor</button></div>
    {error && <p role="alert" className="my-4 text-primary">{error}</p>}
    {tab === 'users' && <p className="my-4 text-xs text-on-surface-variant">At least one active Admin must remain. Identity, status or role changes can sign out affected sessions.</p>}
    {tab === 'contacts' && row && <div className="my-5 text-sm grid gap-3 break-words"><p>{row.name} · {row.email}</p><h3 className="font-bold">{row.subject}</h3><p className="whitespace-pre-wrap">{row.body}</p></div>}
    <form onSubmit={event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const fields = tab === 'users' ? row ? ['email', 'display_name', 'status'] : ['username', 'email', 'display_name', 'password']
        : tab === 'posts' ? ['title', 'content', 'category_id', 'status'] : tab === 'categories' ? row ? ['name', 'status'] : ['name', 'slug'] : ['status'];
      const body: Record<string, unknown> = {};
      for (const key of fields) {
        const value = String(data.get(key) ?? '');
        const previous = key === 'category_id' ? row?.category?.id : row?.[key as keyof AdminRow];
        if (!row || value !== previous) body[key] = value;
      }
      if (tab === 'users' && !row) body.roles = data.getAll('roles');
      if (!Object.keys(body).length) { showToast('No changes to save.'); return; }
      void execute(path, row ? 'PATCH' : 'POST', body);
    }}>
      <fieldset disabled={busy} className="grid gap-5 my-5">
        {tab === 'users' && <>
          {!row && <label>Username<input className={input} name="username" required pattern="[a-z0-9_]{3,32}" minLength={3} maxLength={32} autoComplete="off" /></label>}
          <label>Account email<input className={input} name="email" type="email" required defaultValue={row?.email ?? ''} autoComplete="off" /></label>
          <label>Account display name<input className={input} name="display_name" required maxLength={80} defaultValue={row?.display_name ?? ''} autoComplete="off" /></label>
          {!row && <><label>Initial password<input className={input} name="password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
            <fieldset className="flex flex-wrap gap-4"><legend className="mb-2">Initial roles</legend>{(['USER', 'ADMIN'] as const).map(role => <label key={role}><input type="checkbox" name="roles" value={role} defaultChecked={role === 'USER'} /> {role} role</label>)}</fieldset></>}
        </>}
        {tab === 'posts' && <>
          <p className="text-sm text-on-surface-variant">Author: {row?.author?.display_name}. Attachments stay unchanged; authors manage their media.</p>
          <label>Post title<input className={input} name="title" required maxLength={160} defaultValue={row?.title ?? ''} /></label>
          <label>Post content<textarea className={input} name="content" maxLength={20000} rows={6} defaultValue={row?.content ?? ''} /></label>
          <label>Post category<select className={input} name="category_id" defaultValue={row?.category?.id} required>
            {row?.category && !categories.items.some(item => item.id === row.category!.id) && <option value={row.category.id}>{row.category.name}</option>}
            {categories.items.map(item => <option value={item.id} key={item.id}>{item.name} ({item.status})</option>)}
          </select></label>
          {categories.error && <p role="alert">{categories.error} <button type="button" className="min-h-11 underline" onClick={categories.reload}>Retry channels</button></p>}
          {categories.hasPages && <button type="button" className="min-h-11 underline" aria-disabled={categories.pending || !categories.more} aria-live="polite" onClick={categories.loadMore}>{categories.more || categories.pending ? "More channels" : "All channels loaded"}</button>}
        </>}
        {tab === 'categories' && <>
          <label>Category name<input className={input} name="name" required maxLength={80} defaultValue={row?.name ?? ''} /></label>
          {!row && <label>Category slug<input className={input} name="slug" required maxLength={80} pattern="[a-z0-9-]+" /></label>}
        </>}
        {row && <label>{tab === 'users' ? 'Account status' : tab === 'contacts' ? 'Contact status' : 'Status'}<select name="status" className={input} defaultValue={row.status}>
          {(tab === 'users' ? ['active', 'locked'] : tab === 'posts' ? ['draft', 'published', 'hidden'] : tab === 'categories' ? ['active', 'hidden'] : ['new', 'in_review', 'resolved']).map(status => <option key={status} value={status}>{status}</option>)}
        </select></label>}
        <div><button className={button} disabled={busy}>{busy ? 'Saving…' : row ? 'Save changes' : 'Create record'}</button></div>
      </fieldset>
    </form>
    {tab === 'users' && row && <form className="border-t border-surface-container-highest pt-5 my-5" onSubmit={event => {
      event.preventDefault();
      const roles = new FormData(event.currentTarget).getAll('roles');
      if ([...roles].sort().join() === [...(row.roles ?? [])].sort().join()) { showToast('No changes to save.'); return; }
      void execute('/admin/users/' + row.id + '/roles', 'PUT', { roles });
    }}><fieldset disabled={busy} className="flex flex-wrap items-center gap-4"><legend className="font-bold mb-3">User roles</legend>
      {(['USER', 'ADMIN'] as const).map(role => <label key={role}><input type="checkbox" name="roles" value={role} defaultChecked={row.roles?.includes(role)} /> {role} role</label>)}
      <button className={button} disabled={busy}>Save roles</button>
    </fieldset></form>}
    {row && tab !== 'contacts' && <button disabled={busy || (tab === 'categories' && row.status === 'hidden')} className="min-h-11 underline text-primary" onClick={() => {
      if (window.confirm(tab === 'categories' ? 'Hide this category? Posts will no longer be public in this channel.' : 'Delete this ' + (tab === 'users' ? 'user? Their sessions will be revoked.' : 'post? It will no longer be public.'))) void execute(path, 'DELETE');
    }}>{tab === 'categories' ? 'Hide category' : tab === 'users' ? 'Delete user' : 'Delete post'}</button>}
  </section>;
}
