import {MOCK_AUTH} from '../auth.js';
import { useLocalized } from '../localize.jsx';
import React, { useEffect, useState } from 'react';
import { CATEGORIES, POSTS, selectPosts, filterUrl } from '../feed-data.js';
import { useFeed } from '../FeedContext.jsx';
import {PostCard} from './PostCard.jsx';
import {useSocial} from '../SocialContext.jsx';
import { applyDemoIdentity } from '../demo.js';
import { usePreferences } from '../PreferencesContext.jsx';
import UserAvatar from './UserAvatar.jsx';

function UserSearchSection({ query }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const { language } = usePreferences?.() || { language: 'vi' };
  const t = (vi, en) => (language === 'en' ? en : vi);

  useEffect(() => {
    if (!query || !query.trim()) {
      setUsers([]);
      return;
    }
    let active = true;
    setLoading(true);
    fetch(`/api/v1/users/search?q=${encodeURIComponent(query.trim())}`)
      .then(res => res.ok ? res.json() : { items: [] })
      .then(data => {
        if (active) setUsers(data.items || []);
      })
      .catch(() => {
        if (active) setUsers([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [query]);

  return (
    <div className="col-span-full w-full flex flex-col gap-3 mb-6 p-4 rounded-2xl bg-surface-container-low border border-surface-container-high/80 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold flex items-center gap-2">
          <span>{t('Người dùng', 'Users')}</span>
          <span className="text-secondary font-mono text-xs px-2.5 py-0.5 rounded-full bg-secondary-container/30 border border-secondary/30">
            {users.length}
          </span>
        </h3>
        {loading && <span className="text-xs text-on-surface-variant animate-pulse">{t('Đang tìm kiếm...', 'Searching...')}</span>}
      </div>

      {!loading && users.length === 0 ? (
        <p className="text-on-surface-variant font-body-sm text-body-sm py-2">
          {t('Không tìm thấy người dùng phù hợp.', 'No matching users found.')}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {users.map(u => (
            <a
              key={u.id}
              href={`/u/${u.username}`}
              className="flex items-center gap-3 p-3 rounded-xl bg-surface-container border border-surface-container-high hover:border-secondary/50 hover:bg-surface-container-high transition-all group"
            >
              <UserAvatar src={u.avatar_url} alt={u.display_name} tier={u.membership_tier} size="md" />
              <div className="flex flex-col min-w-0 flex-1">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-label-md text-label-md font-semibold text-on-surface truncate group-hover:text-secondary transition-colors">
                    {u.display_name}
                  </span>
                  {u.title && (
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-tertiary-container/30 text-tertiary border border-tertiary/20 shrink-0 font-medium">
                      {u.title}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <span className="truncate">@{u.username}</span>
                  {u.level && (
                    <span className="text-[11px] font-mono text-secondary">
                      Lv.{u.level}
                    </span>
                  )}
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export function DemoFeed({ variant }) {
  const render = useLocalized();
  const { language } = usePreferences?.() || { language: 'vi' };
  const t = (vi, en) => (language === 'en' ? en : vi);
  const { filters, update, url,targetId,missingPost } = useFeed();
  const {posts,error,ready,loading,retry}=useSocial();
  const matches = MOCK_AUTH?selectPosts(filters,posts):posts;
  const selected = (MOCK_AUTH && variant==='explore' && !filters.q)?matches.slice(0,3):matches;
  const visible = new Set(selected.map(post => post.id));
  // Preserve comment drafts while switching filters.
  const ordered = [...selected, ...posts.filter(post => !visible.has(post.id))];
  useEffect(() => {
    applyDemoIdentity();
    const target = document.getElementById('post-'+targetId);
    if (ready&&target && !target.hidden) target.scrollIntoView({ block: 'start' });
  }, [ready,targetId,filters.q,filters.category]);
  return render(<>
    {filters.q && (
      <div className="col-span-full mb-3 flex items-center justify-between">
        <h2 className="font-headline-md text-headline-md text-on-surface font-bold">
          {t('Kết quả tìm kiếm cho', 'Search results for')} "{filters.q}"
        </h2>
        <button
          type="button"
          className="text-secondary font-label-sm text-label-sm hover:underline"
          onClick={() => update({ q: '' })}
        >
          {t('Xóa tìm kiếm', 'Clear search')}
        </button>
      </div>
    )}
    {filters.q && <UserSearchSection query={filters.q} />}
    {filters.q && (
      <div className="col-span-full mb-2">
        <h3 className="font-headline-sm text-headline-sm text-on-surface font-bold flex items-center gap-2">
          <span>{t('Bài viết', 'Posts')}</span>
          <span className="text-secondary font-mono text-xs px-2.5 py-0.5 rounded-full bg-secondary-container/30 border border-secondary/30">
            {selected.length}
          </span>
        </h3>
      </div>
    )}
    {error&&<div role="alert" className="col-span-full text-error font-body-sm text-body-sm">{error}<button type="button" onClick={()=>retry().catch(()=>{})}>Thử lại</button></div>}{!MOCK_AUTH&&loading&&<p role="status" className="col-span-full">Đang tải bài viết...</p>}
    {missingPost&&<div role="status" className="col-span-full text-on-surface-variant font-body-sm text-body-sm">Không tìm thấy bài trong dữ liệu demo của trình duyệt này.</div>}
    {ordered.map(post=><PostCard key={post.id} post={post} variant={variant} hidden={!visible.has(post.id)} onExplore={variant==='explore'?event=>{if(!event.target.closest('button,a,input,select,textarea')&&!getSelection()?.toString())location.assign(url('/',`post-${post.id}`))}:undefined}/>)}
    {!MOCK_AUTH&&variant==='explore'&&<div className="col-span-full"><FeedEnd/></div>}
    {ready&&!loading&&!error&&!selected.length && <div role="status" className="col-span-full bg-surface-container-low rounded-xl p-4 text-on-surface-variant font-body-md text-body-md">
      <p>{t('Không tìm thấy bài viết phù hợp.', 'No matching posts found.')}</p><button type="button" className="text-secondary font-label-md text-label-md mt-3" onClick={() => update({ category: '', q: '' })}>{t('Xóa bộ lọc', 'Clear filter')}</button>
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
