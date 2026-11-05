import { Link, useNavigate } from 'react-router-dom';
import type { Page, Post } from '../blog';
import { useResource } from '../hooks/useResource';
import { useState, useEffect, useRef } from 'react';
import { useUI } from '../context/UIContext';

export function SearchModal() {
  const { isSearchOpen, setSearchOpen } = useUI();
  const navigate = useNavigate();
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => { const timer = window.setTimeout(() => setDebounced(query.trim()), 250); return () => window.clearTimeout(timer); }, [query]);
  const results = useResource<Page<Post>>(isSearchOpen ? '/posts?search=' + encodeURIComponent(debounced) + '&page_size=5' : null);
  const openResults = () => { setSearchOpen(false); navigate('/explore?search=' + encodeURIComponent(query.trim())); };
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === 'Escape' && isSearchOpen) {
        event.preventDefault();
        setSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, setSearchOpen]);
  useEffect(() => {
    if (isSearchOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [isSearchOpen]);
  return (
    <dialog
      ref={dialog}
      onCancel={(event) => {
        event.preventDefault();
        setSearchOpen(false);
      }}
      aria-labelledby="search-title"
      className="fixed top-20 mx-auto w-[calc(100%-2rem)] max-w-xl p-0 rounded-2xl bg-surface-container-low text-on-surface border border-surface-container-highest shadow-2xl backdrop:bg-black/80 backdrop:backdrop-blur-md"
    >
      <div className="p-4 border-b border-surface-container-highest">
        <h2 id="search-title" className="font-bold text-sm">
          Search posts
        </h2>
        <p className="text-xs text-outline mt-1">
          Search published titles and post text. Open a discussion or view all results.
        </p>
      </div>
      <div className="flex gap-3 items-center p-4">
        <span aria-hidden="true" className="material-symbols-outlined text-primary">
          search
        </span>
        <input
          autoFocus
          type="search"
          aria-label="Search posts"
          placeholder="Titles and post text..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); openResults(); } }}
          className="min-w-0 flex-1 bg-transparent text-sm placeholder:text-outline py-2"
        />
        <button
          type="button"
          aria-label="Close search"
          onClick={() => setSearchOpen(false)}
          className="h-11 w-11 grid place-items-center rounded-lg bg-surface-container-high text-xs"
        >
          ESC
        </button>
      </div>
      <div className="max-h-[55dvh] overflow-y-auto px-4 pb-4 flex flex-col gap-2">
        {results.pending ? <p role="status">Searching…</p> : results.error ? <p role="alert">{results.error}</p> : results.data?.items.length ? results.data.items.map(post => (
          <Link to={'/posts/' + post.id} key={post.id} onClick={() => setSearchOpen(false)} className="min-h-11 p-3 rounded-xl bg-surface-container hover:bg-surface-container-high">
            <p className="text-sm font-semibold break-words">{post.title}</p><p className="mt-1 text-xs text-secondary">#{post.category.name}</p>
          </Link>
        )) : <p className="text-center py-8 text-sm text-on-surface-variant">No posts found.</p>}
        <form onSubmit={event => { event.preventDefault(); openResults(); }}>
          <button className="min-h-11 text-secondary underline">View all results</button>
        </form>
      </div>
    </dialog>
  );
}
