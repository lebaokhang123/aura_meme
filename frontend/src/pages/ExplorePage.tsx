import { useUI } from '../context/UIContext';
import { formatAuraNumber } from '../utils/format';

export function ExplorePage() {
  const { posts, selectedCategory, setSelectedCategory, setSearchOpen, showToast } = useUI();
  const categories = ['Gaming', 'Anime', 'Technology', 'School', 'Random'];
  const filteredPosts = posts.filter((post) => !selectedCategory || post.category === selectedCategory);
  return (
    <div className="explore-page max-w-7xl w-full mx-auto px-4 lg:px-6 py-8 min-w-0">
      <div className="explore-intro relative isolate flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-surface-container-highest/30">
        <div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-high text-secondary font-mono text-xs uppercase tracking-wider mb-3">
            <span aria-hidden="true" className="material-symbols-outlined text-[16px]">
              explore
            </span>
            Demo meme registry
          </span>
          <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl sm:text-4xl tracking-tight">
            Explore Internet <span className="aura-word">Artifacts</span>
          </h1>
          <p className="text-sm text-on-surface-variant mt-2 max-w-xl">
            A small sample collection, a few familiar channels, and space for your next great meme.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setSearchOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-5 min-h-11 rounded-xl bg-gradient-to-r from-primary-container to-secondary text-on-primary font-semibold text-xs shadow-lg"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
            search
          </span>
          Search samples
        </button>
      </div>
      <div role="group" aria-label="Demo categories" tabIndex={0} className="flex items-center gap-2 overflow-x-auto py-4">
        {[null, ...categories].map((category) => (
          <button
            key={category ?? 'all'}
            type="button"
            aria-pressed={selectedCategory === category}
            onClick={() => setSelectedCategory(category)}
            className={`min-h-11 px-4 rounded-xl text-xs whitespace-nowrap shrink-0 transition-colors ${selectedCategory === category ? 'bg-surface-container text-secondary ring-1 ring-secondary/40' : 'bg-surface-container-low text-on-surface-variant hover:bg-surface-container-high'}`}
          >
            {category ? `#${category}` : '⚡ All Channels'}
          </button>
        ))}
      </div>
      <section className="discovery-ribbon my-6 p-5 rounded-2xl bg-surface-container-low border border-surface-container-highest/30 shadow-lg">
        <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-surface-container-highest/30">
          <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-sm">A community in the making</h2>
          <span className="font-mono text-[10px] text-secondary">THE SAMPLE COLLECTION</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
          {['Original memes', 'Good conversations', 'Your own identity'].map((label, index) => (
            <div
              key={label}
              className="discovery-tile p-3 rounded-xl bg-surface-container flex items-center gap-3"
            >
              <img
                src={`/assets/illustrations/meme-${index + 1}.svg`}
                alt=""
                className="h-11 w-11 rounded-lg object-cover shrink-0"
              />
              <span className="text-xs text-on-surface-variant">{label}</span>
            </div>
          ))}
        </div>
      </section>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredPosts.map((post) => (
          <article
            key={post.id}
            className="meme-card explore-card min-w-0 bg-surface-container-low rounded-xl overflow-hidden border border-surface-container-highest/30 shadow-md hover:shadow-xl transition-shadow flex flex-col"
          >
            <div className="post-media relative aspect-[16/10] bg-surface-container-lowest overflow-hidden">
              <img
                alt={post.imageAlt}
                src={post.imageUrl}
                className="w-full h-full object-cover transition-transform duration-500 hover:scale-105"
              />
              <span className="absolute top-3 left-3 px-2 py-1 rounded-full bg-surface-container-lowest/90 text-secondary text-[10px]">
                #{post.category}
              </span>
              <span className="absolute bottom-3 right-3 rounded bg-surface-container-lowest/90 text-outline px-2 py-1 text-[10px]">
                DEMO
              </span>
            </div>
            <div className="p-4 flex-1">
              <div className="flex items-center gap-2 mb-3">
                <span
                  className={`grid place-items-center w-7 h-7 rounded-full text-[10px] font-bold ${post.author.avatarBg}`}
                >
                  {post.author.initials}
                </span>
                <span className="text-xs text-on-surface-variant break-words min-w-0">
                  {post.author.username}
                </span>
              </div>
              <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-sm line-clamp-2 leading-snug">
                {post.title}
              </h2>
            </div>
            <div className="p-4 border-t border-surface-container-highest/20 flex items-center justify-between gap-2">
              <span className="text-xs text-secondary font-mono">
                🤣 {formatAuraNumber(post.reactions.laugh, true)}{' '}
                <span className="text-outline font-sans">sample</span>
              </span>
              <button
                type="button"
                aria-label="Bookmark preview"
                onClick={() => showToast('Bookmarks are a preview only. No bookmark was saved.')}
                className="w-11 h-11 grid place-items-center rounded-lg text-outline hover:text-primary"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
                  bookmark
                </span>
              </button>
            </div>
          </article>
        ))}
      </div>
      {filteredPosts.length === 0 && (
        <div className="text-center bg-surface-container-low rounded-xl py-12">
          <h2 className="font-bold">No sample posts in this category</h2>
          <button
            type="button"
            onClick={() => setSelectedCategory(null)}
            className="min-h-11 mt-3 text-secondary text-sm"
          >
            Show all samples
          </button>
        </div>
      )}
    </div>
  );
}
