import { useFeed } from '../hooks/useFeed';
import { Pagination } from './Pagination';
import { PostCard } from './PostCard';
import { useEffect, useState } from 'react';

export function FeedView({ feed, grid = false }: { feed: ReturnType<typeof useFeed>; grid?: boolean }) {
  const { data, pending, error, reload, params, update, categories } = feed;
  const currentSearch = params.get('search') ?? '';
  const [search, setSearch] = useState(currentSearch);
  useEffect(() => setSearch(currentSearch), [currentSearch]);
  const input = 'min-h-11 min-w-0 rounded-lg bg-surface-container-lowest px-3 py-2 text-sm border border-surface-container-highest';
  return <>
    <form className="surface-panel bg-surface-container-low rounded-xl p-3 flex flex-wrap gap-3" onSubmit={event => {
      event.preventDefault(); update({ search: String(new FormData(event.currentTarget).get('search') ?? ''), page: '1' });
    }}>
      <label className="flex-1 min-w-0 text-xs">Search posts<input name="search" type="search" value={search} onChange={event => setSearch(event.target.value)} maxLength={100} className={input + ' block w-full mt-1'} /></label>
      <button className={input + ' self-end text-primary'}>Search feed</button>
      <label className="text-xs max-w-full">Category<select className={input + ' block w-full mt-1'} value={params.get('category') ?? ''} onChange={event => update({ category: event.target.value, page: '1' })}>
        <option value="">All channels</option>
        {params.get('category') && !categories.items.some(item => item.slug === params.get('category')) && <option value={params.get('category')!}>{params.get('category')}</option>}
        {categories.items.map(item => <option key={item.id} value={item.slug}>{item.name}</option>)}
      </select></label>
      <label className="text-xs">Sort posts<select className={input + ' block mt-1'} value={params.get('sort') ?? 'created_desc'} onChange={event => update({ sort: event.target.value, page: '1' })}>
        <option value="created_desc">Newest</option><option value="created_asc">Oldest</option><option value="title_asc">Title A–Z</option>
      </select></label>
      {categories.hasPages && <button type="button" aria-disabled={categories.pending || !categories.more} aria-live="polite" className="text-secondary min-h-11" onClick={categories.loadMore}>{categories.more || categories.pending ? "More channels" : "All channels loaded"}</button>}
    </form>
    {categories.error && <p role="alert">{categories.error} <button onClick={categories.reload} className="underline min-h-11">Retry channels</button></p>}
    {pending ? <p role="status" className="p-6">Loading posts…</p> : error ? <div className="surface-panel p-6 rounded-xl bg-surface-container-low"><p role="alert">{error}</p><button onClick={reload} className="text-secondary underline min-h-11">Retry feed</button></div> : data && <>
      {data.items.length ? <div className={grid ? 'mt-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'mt-5 space-y-4'}>{data.items.map(post => <PostCard key={post.id} post={post} />)}</div>
        : <div className="surface-panel rounded-xl bg-surface-container-low p-8 text-center"><h2 className="font-bold">No posts found.</h2><p className="mt-2 text-sm text-on-surface-variant">Try another search or start a conversation.</p></div>}
      <Pagination value={data.pagination} onPage={page => update({ page: String(page) })} />
    </>}
  </>;
}
