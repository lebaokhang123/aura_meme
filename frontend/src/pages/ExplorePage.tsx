import { useUI } from '../context/UIContext';
import { FeedView } from '../components/FeedView';
import { useFeed } from '../hooks/useFeed';

export function ExplorePage() {
  const feed = useFeed();
  const { setSearchOpen } = useUI();
  return (
    <div className="explore-page max-w-7xl w-full mx-auto px-4 lg:px-6 py-8 min-w-0">
      <div className="explore-intro relative isolate flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-surface-container-highest/30">
        <div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-high text-secondary font-mono text-xs uppercase tracking-wider mb-3">
            <span aria-hidden="true" className="material-symbols-outlined text-[16px]">
              explore
            </span>
            Community channels
          </span>
          <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl sm:text-4xl tracking-tight">
            Explore Internet <span className="aura-word">Artifacts</span>
          </h1>
          <p className="text-sm text-on-surface-variant mt-2 max-w-xl">
            Browse published posts, find a channel, and join the conversation.
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
          Search community
        </button>
      </div>
      <section className="discovery-ribbon my-6 p-5 rounded-2xl bg-surface-container-low border border-surface-container-highest/30 shadow-lg">
        <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-surface-container-highest/30">
          <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-sm">A community in the making</h2>
          <span className="font-mono text-[10px] text-secondary">EXPLORE TOGETHER</span>
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
      <FeedView feed={feed} grid />
    </div>
  );
}
