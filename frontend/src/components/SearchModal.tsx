import { Link } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { useUI } from '../context/UIContext';

export function SearchModal() {
  const { isSearchOpen, setSearchOpen, posts, setSelectedCategory } = useUI();
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState('');
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
  const matches = posts.filter((post) =>
    [post.title, post.author.username, post.category].some((value) =>
      value.toLowerCase().includes(query.trim().toLowerCase()),
    ),
  );
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
          Search demo posts
        </h2>
        <p className="text-xs text-outline mt-1">
          Search the sample collection. Results filter the feed; post details are not connected.
        </p>
      </div>
      <div className="flex gap-3 items-center p-4">
        <span aria-hidden="true" className="material-symbols-outlined text-primary">
          search
        </span>
        <input
          autoFocus
          type="search"
          aria-label="Search sample collection"
          placeholder="Memes, categories, creators..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
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
        {matches.length === 0 ? (
          <p className="text-center py-8 text-sm text-on-surface-variant">No sample posts found</p>
        ) : (
          matches.map((post) => (
            <Link
              to="/"
              key={post.id}
              onClick={() => {
                setSelectedCategory(post.category);
                setSearchOpen(false);
              }}
              className="p-3 rounded-xl bg-surface-container hover:bg-surface-container-high transition-colors flex gap-3 items-center"
            >
              <img src={post.imageUrl} alt="" className="h-12 w-12 object-cover rounded-lg shrink-0" />
              <div className="min-w-0">
                <p className="text-xs font-semibold line-clamp-2">{post.title}</p>
                <p className="text-[11px] text-secondary mt-1">#{post.category} · Demo feed</p>
              </div>
            </Link>
          ))
        )}
      </div>
    </dialog>
  );
}
