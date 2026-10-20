import { Link } from 'react-router-dom';
import React, { useState, useEffect, useRef } from 'react';
import { useUI } from '../context/UIContext';

export const SearchModal: React.FC = () => {
  const { isSearchOpen, setSearchOpen, posts, setSelectedCategory, } = useUI();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [localQuery, setLocalQuery] = useState('');

  // Handle Ctrl + K shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === 'Escape' && isSearchOpen) {
        setSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, setSearchOpen]);

  useEffect(() => {
    if (isSearchOpen) dialogRef.current?.showModal();
    else dialogRef.current?.close();
  }, [isSearchOpen]);

  const filteredPosts = posts.filter(
    (p) =>
      p.title.toLowerCase().includes(localQuery.toLowerCase()) ||
      p.author.username.toLowerCase().includes(localQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(localQuery.toLowerCase())
  );

  const categories = ['Gaming', 'Anime', 'Technology', 'School', 'Random'];

  return (
    <dialog ref={dialogRef} onCancel={() => setSearchOpen(false)} aria-label="Search memes" className="fixed top-20 m-auto w-[calc(100%-2rem)] max-w-xl p-0 bg-transparent text-on-surface backdrop:bg-black/80 backdrop:backdrop-blur-md">
      <div className="relative w-full max-w-xl bg-surface-container-low border border-surface-container-highest rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
        {/* Search Input Bar */}
        <div className="p-4 border-b border-surface-container-highest flex items-center gap-3">
          <span className="material-symbols-outlined text-primary text-[22px]">search</span>
          <input
            aria-label="Search memes"
            autoFocus
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Search memes, categories, creators, tags..."
            className="w-full bg-transparent text-on-surface placeholder:text-outline text-sm focus:outline-none"
          />
          <button
            onClick={() => setSearchOpen(false)}
            className="text-outline hover:text-on-surface text-xs font-mono px-2 py-1 rounded bg-surface-container cursor-pointer"
          >
            ESC
          </button>
        </div>

        {/* Category Quick Tags */}
        <div className="px-4 py-2 bg-surface-container/60 border-b border-surface-container-highest flex items-center gap-2 overflow-x-auto">
          <span className="text-[11px] text-outline uppercase tracking-wider shrink-0">Tags:</span>
          {categories.map((cat) => (
            <Link to="/"
              key={cat}
              onClick={() => {
                setSelectedCategory(cat);

                setSearchOpen(false);
              }}
              className="px-2.5 py-0.5 rounded-full bg-surface-container text-xs text-on-surface-variant hover:text-secondary hover:bg-surface-container-high transition-colors shrink-0 cursor-pointer"
            >
              #{cat}
            </Link>
          ))}
        </div>

        {/* Results List */}
        <div className="overflow-y-auto p-4 flex flex-col gap-2">
          {filteredPosts.length === 0 ? (
            <div className="py-8 text-center text-outline text-sm">
              No memes or tags matching &quot;{localQuery}&quot;
            </div>
          ) : (
            filteredPosts.map((post) => (
              <Link to="/"
                key={post.id}
                onClick={() => {
                  setSelectedCategory(post.category);
                  setSearchOpen(false);
                }}
                className="p-3 rounded-xl bg-surface-container hover:bg-surface-container-high transition-colors cursor-pointer flex items-center justify-between gap-3 group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <img
                    alt=""
                    src={post.imageUrl}
                    className="w-12 h-12 rounded-lg object-cover bg-surface-container-lowest shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="font-['Plus_Jakarta_Sans'] font-semibold text-xs text-on-surface group-hover:text-primary transition-colors truncate">
                      {post.title}
                    </p>
                    <p className="font-['Inter'] text-[11px] text-outline">
                      {post.author.username} • <span className="text-secondary">#{post.category}</span>
                    </p>
                  </div>
                </div>
                <div className="shrink-0 flex items-center gap-1 font-['JetBrains_Mono'] text-xs text-secondary">
                  <span>+{post.reactions.laugh + post.reactions.like}</span>
                  <span className="material-symbols-outlined text-[14px]">local_fire_department</span>
                </div>
              </Link>
            ))
          )}
        </div>
      </div>
    </dialog>
  );
};
