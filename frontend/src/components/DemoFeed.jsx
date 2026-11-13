import {MOCK_AUTH} from '../auth.js';
import { useLocalized } from '../localize.jsx';
import React, { useEffect } from 'react';
import { CATEGORIES, POSTS, selectPosts, filterUrl } from '../feed-data.js';
import { useFeed } from '../FeedContext.jsx';
import {PostCard} from './PostCard.jsx';
import {useSocial} from '../SocialContext.jsx';
import { applyDemoIdentity } from '../demo.js';

export function DemoFeed({ variant }) {
  const render = useLocalized();
  const { filters, update, url,targetId,missingPost } = useFeed();
  const {posts,error,ready,loading,retry}=useSocial();
  const matches = MOCK_AUTH?selectPosts(filters,posts):posts;
  const selected = variant==='explore'?matches.slice(0,3):matches;
  const visible = new Set(selected.map(post => post.id));
  // Preserve comment drafts while switching filters.
  const ordered = [...selected, ...posts.filter(post => !visible.has(post.id))];
  useEffect(() => {
    applyDemoIdentity();
    const target = document.getElementById('post-'+targetId);
    if (ready&&target && !target.hidden) target.scrollIntoView({ block: 'start' });
  }, [ready,targetId,filters.q,filters.category]);
  return render(<>
    {error&&<div role="alert" className="text-error font-body-sm text-body-sm">{error}<button type="button" onClick={()=>retry().catch(()=>{})}>Thử lại</button></div>}{!MOCK_AUTH&&loading&&<p role="status">Đang tải bài viết...</p>}
    {missingPost&&<div role="status" className="text-on-surface-variant font-body-sm text-body-sm">Không tìm thấy bài trong dữ liệu demo của trình duyệt này.</div>}
    {ordered.map(post=><PostCard key={post.id} post={post} variant={variant} hidden={!visible.has(post.id)} onExplore={variant==='explore'?event=>{if(!event.target.closest('button,a,input,select,textarea')&&!getSelection()?.toString())location.assign(url('/',`post-${post.id}`))}:undefined}/>)}
    {ready&&!loading&&!selected.length && <div role="status" className="bg-surface-container-low rounded-xl p-4 text-on-surface-variant font-body-md text-body-md">
      <p>Không tìm thấy bài viết phù hợp.</p><button type="button" className="text-secondary font-label-md text-label-md mt-3" onClick={() => update({ category: '', q: '' })}>Xóa bộ lọc</button>
    </div>}
  </>);
}
const homeActive = 'flex items-center justify-between px-3 py-2 rounded-lg bg-surface-container-high text-secondary transition-all';
const homeIdle = 'flex items-center justify-between px-3 py-2 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all';
const chipActive = 'flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-500/10 border border-cyan-400 text-tertiary font-label-md text-label-md font-bold shadow-[0_0_12px_rgba(76,215,246,0.3)] transition-all shrink-0';
const chipIdle = 'px-4 py-2 rounded-xl bg-surface-container-low hover:bg-surface-container border border-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors font-label-md text-label-md shrink-0';
export function CategoryList({ variant }) {
  const render = useLocalized();
  const { filters, update, url } = useFeed();
  const home = variant === 'home';
  const {posts,categories}=useSocial();
  return render(<nav aria-label={home ? 'Danh mục Home' : 'Danh mục Explore'} className={home ? 'flex flex-col gap-1' : 'flex items-center gap-3 overflow-x-auto pb-1 no-scrollbar'}>
    {!home && <button type="button" className={filters.category ? `${chipIdle} flex items-center gap-2` : chipActive} aria-pressed={!filters.category} onClick={() => update({ category: '' })}><span className="text-amber-400">⚡</span><span>Tất cả kênh</span></button>}
    {categories.map(category => {
      const active = filters.category === category.id;
      const next = active ? '' : category.id;
      const content = home ? <><div className="flex items-center gap-2.5"><span className="material-symbols-outlined text-[18px]" aria-hidden="true">{category.icon}</span><span className={`font-label-md text-label-md${active ? ' font-semibold' : ''}`}>{category.label}</span></div><span className={`font-mono-counter text-mono-counter ${active ? 'text-secondary' : 'text-outline'}`}>{MOCK_AUTH?posts.filter(post=>post.category===category.id).length:category.count}</span></> : `#${category.label.replace(/\s+(.)/g, (_, letter) => letter.toUpperCase())}`;
      return home ? <a key={category.id} data-category={category.id} aria-current={active ? 'true' : undefined} href={filterUrl(location.pathname, { ...filters, category: next })} className={active ? homeActive : homeIdle} onClick={event => { if (!event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) { event.preventDefault(); update({ category: next }); } }}>{content}</a>
        : <button type="button" key={category.id} data-category={category.id} aria-pressed={active} className={active ? chipActive : chipIdle} onClick={() => update({ category: next })}>{content}</button>;
    })}
  </nav>);
}
export function FeedControls() {
  const render = useLocalized();
  const { filters, update } = useFeed();
  const {categories}=useSocial();
  return render(<div className="flex items-center justify-between gap-3 bg-surface-container-low p-2 rounded-xl">
    <div className="flex items-center gap-1.5">
      {['hot','new'].map(sort => <button key={sort} type="button" data-sort={sort} aria-pressed={filters.sort === sort} onClick={() => update({ sort })} className={`px-3.5 py-1.5 rounded-lg font-label-md text-label-md flex items-center gap-1 transition-all ${filters.sort === sort ? 'bg-secondary-container text-on-secondary-container font-bold shadow-sm' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'}`}>
        {sort === 'hot' && <span className="material-symbols-outlined text-[16px]" aria-hidden="true">local_fire_department</span>}{sort === 'hot' ? 'Hot' : 'New'}
      </button>)}
    </div>
    <select aria-label="Lọc danh mục bài viết" value={filters.category} onChange={event => update({ category: event.target.value })} className="bg-surface-container text-on-surface-variant font-label-sm text-label-sm rounded-lg px-2 py-1 max-w-[140px]">
      <option value="">Tất cả chủ đề</option>{categories.map(c => <option key={c.id} value={c.id}>#{c.id}</option>)}
    </select>
  </div>);
}
export function FeedEnd() {
  const render = useLocalized();
  const { filters } = useFeed();
  const {posts,pagination,loading,loadMore}=useSocial();
  if(!MOCK_AUTH)return render(pagination?<div className="demo-feed-end" role="status">{pagination.page<pagination.total_pages?<button type="button" disabled={loading} onClick={()=>loadMore().catch(()=>{})}>{loading?'Đang tải bài viết...':'Xem thêm bài viết'}</button>:pagination.total>0?'Bạn đã xem hết '+pagination.total+' bài viết.':null}</div>:null);
  const count = selectPosts(filters,posts).length;
  return render(count > 0 ? <div className="demo-feed-end" role="status">Bạn đã xem hết {count} bài demo.</div> : null);
}
