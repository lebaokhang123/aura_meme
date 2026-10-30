import { Link } from 'react-router-dom';
import { useUI } from '../context/UIContext';
import { PostCard } from '../components/PostCard';

const categories = ['Gaming', 'Anime', 'Technology', 'School', 'Random'];

export function HomePage() {
  const { posts, selectedCategory, setSelectedCategory, feedTab, setFeedTab, showToast } = useUI();
  const filteredPosts = posts.filter((post) => !selectedCategory || post.category === selectedCategory);
  const sortedPosts = [...filteredPosts].sort((a, b) =>
    feedTab === 'top'
      ? b.reactions.like +
        b.reactions.laugh +
        b.reactions.fire -
        (a.reactions.like + a.reactions.laugh + a.reactions.fire)
      : 0,
  );
  const createPreview = () => showToast('Post creation is not connected yet. No post was created.');

  return (
    <div className="relative w-full min-w-0 isolate">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-clip -z-10">
        <div className="absolute -top-32 left-1/4 w-96 h-96 bg-primary-container/10 rounded-full blur-3xl" />
        <div className="absolute top-48 right-1/4 w-80 h-80 bg-secondary/10 rounded-full blur-3xl" />
      </div>
      <div className="w-full max-w-[1560px] mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <aside
            aria-label="Demo feed categories"
            className="hidden lg:block lg:col-span-3 sticky top-20 max-h-[calc(100dvh-6rem)] overflow-y-auto space-y-4"
          >
            <div className="surface-panel bg-surface-container-low rounded-xl p-4 shadow-md border border-surface-container-highest/30">
              <h2 className="text-xs tracking-wider uppercase text-outline px-1 pb-3">Feeds navigation</h2>
              <button
                type="button"
                onClick={() => setSelectedCategory(null)}
                className="w-full flex items-center gap-2 px-3 py-3 rounded-lg bg-surface-container-high text-primary text-[13px] font-semibold"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
                  home
                </span>
                Home Feed
              </button>
              <Link
                to="/explore"
                className="flex items-center gap-2 px-3 py-3 text-[13px] text-on-surface-variant hover:text-secondary"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">
                  explore
                </span>
                All Channels
              </Link>
            </div>
            <div className="surface-panel bg-surface-container-low rounded-xl p-4 border border-surface-container-highest/30">
              <h2 className="text-xs uppercase text-outline tracking-wider pb-3">Categories</h2>
              <div className="flex flex-col gap-1">
                {categories.map((category, index) => (
                  <button
                    key={category}
                    type="button"
                    aria-pressed={selectedCategory === category}
                    onClick={() => setSelectedCategory(selectedCategory === category ? null : category)}
                    className={`category-row flex items-center gap-2.5 text-left px-3 py-3 rounded-lg text-xs transition-colors ${selectedCategory === category ? 'bg-primary/15 text-primary' : 'text-on-surface-variant hover:bg-surface-container-high'}`}
                  >
                    <span aria-hidden="true" className="category-symbol">
                      {['🎮', '✦', '⌘', '▤', '◇'][index]}
                    </span>
                    <span>{category}</span>
                    <span className="ml-auto font-mono text-outline">
                      {posts.filter((post) => post.category === category).length}
                    </span>
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-outline mt-3">Counts in the demo collection</p>
            </div>
            <div className="surface-panel rounded-xl p-5 bg-gradient-to-b from-surface-container to-surface-container-lowest border border-surface-container-highest/40">
              <span aria-hidden="true" className="material-symbols-outlined text-secondary mb-2">
                forum
              </span>
              <h2 className="text-sm font-bold">Made for a community</h2>
              <p className="text-xs text-on-surface-variant mt-2 leading-relaxed">
                Share the joke, start a conversation, make it your own.
              </p>
              <Link to="/about" className="text-xs text-primary inline-flex items-center gap-1 mt-4">
                Meet AuraMeme
                <span aria-hidden="true" className="material-symbols-outlined text-[16px]">
                  arrow_forward
                </span>
              </Link>
            </div>
          </aside>

          <section aria-label="Sample meme feed" className="min-w-0 lg:col-span-9 xl:col-span-6 space-y-4">
            <div className="feed-hero relative overflow-hidden rounded-xl bg-surface-container-low p-5 shadow-md border border-surface-container-highest/30">
              <div aria-hidden="true" className="hero-orbit">
                <span />
                <span />
                <span />
              </div>
              <div
                aria-hidden="true"
                className="absolute inset-0 bg-gradient-to-br from-primary-container/10 via-transparent to-secondary/10"
              />
              <div className="relative">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-container-high text-secondary text-[10px] font-semibold">
                  <span aria-hidden="true" className="material-symbols-outlined text-[14px]">
                    auto_awesome
                  </span>
                  Demo collection
                </span>
                <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-[27px] sm:text-[32px] leading-tight mt-3 tracking-tight">
                  Level up your <span className="aura-word">Aura,</span>
                  <br />
                  one meme at a time.
                </h1>
                <p className="text-xs text-on-surface-variant mt-2 max-w-sm leading-relaxed">
                  A preview of our meme community. Browse sample posts and explore the look of AuraMeme.
                </p>
                <div className="composer-panel mt-5 bg-surface-container-lowest/60 rounded-xl p-3 border border-surface-container-highest/30">
                  <div className="flex items-center gap-3">
                    <span className="guest-avatar w-10 h-10 grid place-items-center rounded-full bg-primary/15 text-primary font-bold shrink-0">
                      ?
                    </span>
                    <button
                      type="button"
                      onClick={createPreview}
                      className="min-w-0 flex-1 bg-surface-container-lowest rounded-lg px-3 py-3 text-left text-xs text-outline"
                    >
                      Draft a meme — creation preview
                    </button>
                  </div>
                  <div className="flex items-center justify-between mt-3 gap-3">
                    <span className="inline-flex items-center gap-2 text-xs text-outline">
                      <span
                        aria-hidden="true"
                        className="material-symbols-outlined text-secondary text-[18px]"
                      >
                        image
                      </span>
                      One image, one good idea
                    </span>
                    <button
                      type="button"
                      onClick={createPreview}
                      className="shrink-0 min-h-11 rounded-lg px-3 bg-primary text-on-primary text-xs font-semibold"
                    >
                      Create Post
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div
              className="surface-panel feed-order flex gap-1 p-2 rounded-xl bg-surface-container-low border border-surface-container-highest/30"
              aria-label="Sample feed order"
              role="group"
            >
              {(['hot', 'new', 'top'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  aria-pressed={feedTab === tab}
                  onClick={() => setFeedTab(tab)}
                  className={`min-h-11 px-4 rounded-lg capitalize text-sm font-semibold ${feedTab === tab ? 'bg-surface-container-high text-primary' : 'text-on-surface-variant hover:text-on-surface'}`}
                >
                  {tab === 'hot' ? '🔥' : tab === 'new' ? '✦' : '🏆'} {tab}
                </button>
              ))}
            </div>
            {selectedCategory && (
              <div className="flex items-center justify-between gap-2 text-xs px-2">
                <span className="text-secondary">#{selectedCategory}</span>
                <button
                  type="button"
                  onClick={() => setSelectedCategory(null)}
                  className="min-h-11 text-primary"
                >
                  Clear filter
                </button>
              </div>
            )}
            {sortedPosts.length ? (
              sortedPosts.map((post) => <PostCard key={post.id} post={post} />)
            ) : (
              <div className="rounded-xl p-8 bg-surface-container-low text-center">
                <h2 className="font-bold">No sample posts in this category</h2>
                <button
                  type="button"
                  onClick={() => setSelectedCategory(null)}
                  className="text-secondary mt-4 min-h-11"
                >
                  Show all samples
                </button>
              </div>
            )}
            <p className="text-center text-xs text-outline py-4">
              End of the demo collection · {sortedPosts.length} sample posts
            </p>
          </section>

          <aside
            aria-label="Upcoming community features"
            className="lg:col-span-12 xl:col-span-3 min-w-0 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:overflow-y-auto space-y-4"
          >
            <div className="surface-panel aura-preview rounded-xl bg-surface-container-low p-5 shadow-md border border-surface-container-highest/30">
              <div className="flex items-center gap-3 mb-4">
                <span
                  aria-hidden="true"
                  className="material-symbols-outlined w-10 h-10 grid place-items-center rounded-lg bg-primary/15 text-primary"
                >
                  bolt
                </span>
                <div>
                  <h2 className="text-sm font-bold">Your Aura journey</h2>
                  <span className="text-[10px] text-secondary font-mono">P1 · NOT AVAILABLE YET</span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-lg bg-surface-container p-3">
                  <span className="text-outline block">Aura</span>
                  <strong className="text-primary text-lg">—</strong>
                </div>
                <div className="rounded-lg bg-surface-container p-3">
                  <span className="text-outline block">Streak</span>
                  <strong className="text-secondary text-lg">—</strong>
                </div>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed mt-4">
                Progress, check-ins and ranks will appear here when community rewards are connected.
              </p>
            </div>
            <div className="membership-preview relative overflow-hidden rounded-xl bg-gradient-to-b from-surface-container to-surface-container-lowest p-5 border border-surface-container-highest/40 shadow-xl">
              <span className="text-[10px] uppercase text-secondary font-bold">Coming later · P2</span>
              <h2 className="font-['Plus_Jakarta_Sans'] text-lg font-bold mt-2">A little more Aura.</h2>
              <p className="text-xs text-on-surface-variant leading-relaxed mt-2">
                Aura Plus and Aura Prime are planned memberships for personal progression and cosmetics.
              </p>
              <div className="mt-4 px-3 py-2.5 rounded-lg bg-gradient-to-r from-primary/15 to-secondary/10 text-xs text-primary border border-primary/15">
                Preview only · No checkout
              </div>
            </div>
            <div className="surface-panel rounded-xl bg-surface-container-low p-5 border border-surface-container-highest/30">
              <h2 className="text-xs uppercase tracking-wider text-outline">Explore a channel</h2>
              <div className="flex flex-wrap gap-2 mt-3">
                {categories.slice(0, 3).map((category) => (
                  <button
                    type="button"
                    key={category}
                    onClick={() => setSelectedCategory(category)}
                    className="min-h-11 text-xs text-secondary"
                  >
                    #{category}
                  </button>
                ))}
              </div>
              <Link
                to="/explore"
                className="inline-flex items-center gap-1 text-xs text-primary mt-3 min-h-11"
              >
                Explore all
                <span aria-hidden="true" className="material-symbols-outlined text-[16px]">
                  arrow_forward
                </span>
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
