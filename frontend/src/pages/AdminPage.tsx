import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { AdminRow, AdminTab } from '../admin';
import type { Page } from '../blog';
import { useAuth } from '../context/AuthContext';
import { useResource } from '../hooks/useResource';
import { Pagination } from '../components/Pagination';
import { AdminEditor } from '../components/AdminEditor';

const sections: AdminTab[] = ['users', 'posts', 'categories', 'contacts', 'audit-logs'];
const columns: Record<AdminTab, (keyof AdminRow)[]> = {
  users: ['username', 'email', 'display_name', 'roles', 'status'], posts: ['title', 'author', 'category', 'status'],
  categories: ['name', 'slug', 'status'], contacts: ['name', 'email', 'subject', 'status'],
  'audit-logs': ['action', 'actor_id', 'target_type', 'target_id', 'created_at'],
};

function Workspace({ tab }: { tab: AdminTab }) {
  const [params, setParams] = useSearchParams();
  const [row, setRow] = useState<AdminRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLElement | null>(null);
  const search = params.get('search') ?? '';
  const [draftSearch, setDraftSearch] = useState(search);
  useEffect(() => setDraftSearch(search), [search]);
  const query = new URLSearchParams({ page: params.get('page') || '1', page_size: '20' });
  if (['users', 'posts', 'categories'].includes(tab) && search) query.set('search', search);
  if (tab !== 'audit-logs' && params.get('status')) query.set('status', params.get('status')!);
  const resource = useResource<Page<AdminRow>>('/admin/' + tab + '?' + query);
  const update = (values: Record<string, string>) => {
    setRow(null); setCreating(false);
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(values)) value ? next.set(key, value) : next.delete(key);
    setParams(next);
  };
  const close = () => { setRow(null); setCreating(false); requestAnimationFrame(() => trigger.current?.isConnected && trigger.current.focus()); };
  const saved = () => { setRow(null); setCreating(false); resource.reload(); requestAnimationFrame(() => document.getElementById('admin-heading')?.focus()); };
  const statuses = tab === 'users' ? ['active', 'locked', 'deleted'] : tab === 'posts' ? ['draft', 'published', 'hidden', 'deleted'] : tab === 'categories' ? ['active', 'hidden'] : ['new', 'in_review', 'resolved'];
  return <>
    <div className="flex flex-wrap items-center justify-between gap-3 my-6"><h2 className="text-xl font-bold capitalize">{tab.replace('-', ' ')}</h2>
      {['users', 'categories'].includes(tab) && <button disabled={busy || resource.pending} className="min-h-11 rounded-lg bg-primary text-on-primary px-4" onClick={event => { trigger.current = event.currentTarget; setRow(null); setCreating(true); }}>Create {tab === 'users' ? 'user' : 'category'}</button>}
    </div>
    {tab !== 'audit-logs' && <form className="flex flex-wrap gap-4 my-5" onSubmit={event => { event.preventDefault(); update({ search: draftSearch, page: '1' }); }}>
      <fieldset disabled={busy} className="contents">
      {['users', 'posts', 'categories'].includes(tab) && <><label className="min-w-0 text-sm">Search records<input className="block mt-2 min-h-11 max-w-full bg-surface-container rounded-lg px-3" value={draftSearch} onChange={event => setDraftSearch(event.target.value)} maxLength={100} /></label><button className="min-h-11 underline self-end">Search admin</button></>}
      <label className="text-sm">Filter status<select className="block mt-2 min-h-11 bg-surface-container rounded-lg px-3" value={params.get('status') ?? ''} onChange={event => update({ status: event.target.value, page: '1' })}><option value="">All</option>{statuses.map(status => <option key={status} value={status}>{status}</option>)}</select></label>
      </fieldset>
    </form>}
    {resource.pending ? <p role="status">Loading Admin records…</p> : resource.error ? <div><p role="alert">{resource.error}</p><button className="min-h-11 underline" onClick={resource.reload}>Retry Admin records</button></div> : resource.data && <>
      <p id="admin-scroll-hint" className="text-xs text-on-surface-variant mb-2">Wide table: scroll horizontally to view all columns. Keyboard: focus the table region and use arrow keys.</p>
      <div role="region" aria-describedby="admin-scroll-hint" aria-label="Admin results" tabIndex={0} className="overflow-x-auto rounded-xl border border-surface-container-highest bg-surface-container-low">
        <table className="w-full min-w-[600px] text-left text-sm"><caption className="sr-only">{tab} page {resource.data.pagination.page}</caption>
          <thead><tr>{columns[tab].map(key => <th key={key} className="p-4 font-bold capitalize">{key.replaceAll('_', ' ')}</th>)}{tab !== 'audit-logs' && <th className="p-4">Actions</th>}</tr></thead>
          <tbody>{resource.data.items.map(record => <tr key={record.id} className="border-t border-surface-container-highest">
            {columns[tab].map(key => <td key={key} className="p-4 max-w-xs break-words [overflow-wrap:anywhere]">{key === 'author' ? record.author?.username : key === 'category' ? record.category?.name : key === 'roles' ? record.roles?.join(', ') : String(record[key] ?? '')}</td>)}
            {tab !== 'audit-logs' && <td className="p-4">{record.status !== 'deleted' && <button disabled={busy} className="min-h-11 text-secondary underline" onClick={event => { trigger.current = event.currentTarget; setCreating(false); setRow(record); }}>{tab === 'contacts' ? 'Review contact ' + record.subject : 'Edit ' + (tab === 'users' ? 'user ' + record.username : tab === 'posts' ? 'post ' + record.title : 'category ' + record.name)}</button>}</td>}
          </tr>)}</tbody>
        </table>
        {!resource.data.items.length && <p className="p-5">No records found.</p>}
      </div>
      <fieldset disabled={busy} className="contents"><Pagination value={resource.data.pagination} onPage={page => update({ page: String(page) })} /></fieldset>
    </>}
    {(row || creating) && <AdminEditor key={row?.id ?? 'new'} tab={tab} row={row} busy={busy} setBusy={setBusy} onClose={close} onSaved={saved} />}
  </>;
}

export function AdminPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const allowed = user?.roles.includes('ADMIN') ?? false;
  useEffect(() => { if (!allowed) document.getElementById('admin-denied')?.focus(); }, [allowed]);
  if (!allowed) return <section className="p-8"><h1 id="admin-denied" tabIndex={-1} className="text-2xl font-bold">Admin access required</h1><p className="mt-4">Your account does not have permission to open this workspace.</p></section>;
  const tab = sections.includes(params.get('tab') as AdminTab) ? params.get('tab') as AdminTab : 'users';
  return <section className="w-full max-w-7xl mx-auto px-4 lg:px-6 py-8">
    <h1 id="admin-heading" tabIndex={-1} className="text-3xl font-bold">Admin workspace</h1>
    <nav aria-label="Admin sections" className="flex flex-wrap gap-2 mt-5">{sections.map(section => <Link key={section} to={'/admin?tab=' + section} aria-current={tab === section ? 'page' : undefined} className={'min-h-11 px-4 py-3 rounded-lg capitalize ' + (tab === section ? 'bg-primary text-on-primary' : 'bg-surface-container')}>{section.replace('-', ' ')}</Link>)}</nav>
    <Workspace key={tab} tab={tab} />
  </section>;
}
