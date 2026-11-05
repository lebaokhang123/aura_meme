import { Link, useSearchParams } from 'react-router-dom';
import type { OwnPost, Page } from '../blog';
import { useResource } from '../hooks/useResource';
import { Pagination } from '../components/Pagination';

export function MyPostsPage() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams({ page: params.get('page') || '1', page_size: '20' });
  if (params.get('status')) query.set('status', params.get('status')!);
  const { data, pending, error, reload } = useResource<Page<OwnPost>>('/users/me/posts?' + query);
  return <section className="max-w-4xl w-full mx-auto px-4 py-10">
    <div className="flex flex-wrap items-center justify-between gap-4"><h1 className="text-3xl font-bold">My posts</h1><Link className="min-h-11 px-4 py-3 rounded-lg bg-primary text-on-primary" to="/posts/new">Create post</Link></div>
    <label className="block my-5 text-sm">Post status<select className="ml-3 min-h-11 rounded-lg bg-surface-container px-3" value={params.get('status') ?? ''} onChange={event => setParams(event.target.value ? { status: event.target.value } : {})}>
      <option value="">All</option><option value="draft">Draft</option><option value="published">Published</option><option value="hidden">Hidden</option>
    </select></label>
    {pending ? <p role="status">Loading your posts…</p> : error ? <div><p role="alert">{error}</p><button onClick={reload} className="underline min-h-11">Retry your posts</button></div> : data && <>
      {data.items.length ? data.items.map(post => <article key={post.id} className="surface-panel p-5 rounded-xl bg-surface-container-low my-4">
        <span className="text-xs text-secondary">{post.status}</span><h2 className="font-bold mt-2 break-words"><Link to={'/my-posts/' + post.id}>{post.title}</Link></h2>
        <p className="text-sm mt-2 text-on-surface-variant whitespace-pre-wrap break-words line-clamp-3">{post.content}</p>
        <p className="text-xs mt-3 text-outline">{post.media_id ? 'Private attachment saved' : 'Text post'}</p>
      </article>) : <p className="p-6">You have no posts yet.</p>}
      <Pagination value={data.pagination} onPage={page => { const next = new URLSearchParams(params); next.set('page', String(page)); setParams(next); }} />
    </>}
  </section>;
}
