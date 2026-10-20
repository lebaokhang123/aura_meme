import React from 'react';
import { useUI } from '../context/UIContext';
import { formatAuraNumber } from '../utils/format';

export const ExplorePage: React.FC = () => {
  const {
    posts,
    selectedCategory,
    setSelectedCategory,
    toggleReaction,
    awardAuraToPost,
    toggleBookmark,
    showCreatePostPreview,
  } = useUI();

  const categories = ['All', 'Gaming', 'Anime', 'Technology', 'School', 'Random'];

  const filteredPosts =
    !selectedCategory || selectedCategory === 'All'
      ? posts
      : posts.filter((p) => p.category.toLowerCase() === selectedCategory.toLowerCase());

  const topCreators = [
    { rank: '1', handle: 'u/PixelWizard', memes: 32, aura: '18,420 Aura', badge: '🥇 Top Creator', tier: 'Aura Legend' },
    { rank: '2', handle: 'u/SyntaxSamurai', memes: 28, aura: '14,890 Aura', badge: '🥈 Master', tier: 'Aura Master' },
    { rank: '3', handle: 'u/ByteQueen', memes: 19, aura: '12,350 Aura', badge: '🥉 Artisan', tier: 'Logic Master' },
    { rank: '4', handle: 'u/CyberNeko', memes: 14, aura: '9,410 Aura', badge: 'Meme Knight', tier: 'Meme Knight' },
  ];

  return (
    <div className="w-full">
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-surface-container-highest/30">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-high text-secondary font-['JetBrains_Mono'] text-xs uppercase tracking-wider mb-2">
              <span className="material-symbols-outlined text-[16px]">explore</span>
              Campus Meme Registry
            </div>
            <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl text-on-surface">
              Explore Internet Artifacts
            </h1>
            <p className="font-['Inter'] text-xs sm:text-sm text-on-surface-variant max-w-xl mt-1">
              Discover viral collegiate artifacts, filter by topic, and back rising creators to level up your collective vibe index.
            </p>
          </div>

          <button
            onClick={() => showCreatePostPreview()}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-primary-container via-inverse-primary to-secondary text-white font-['Inter'] font-semibold text-xs shadow-lg hover:shadow-primary/30 transition-all cursor-pointer"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            <span>Forge New Meme</span>
          </button>
        </div>

        {/* Category Pills Bar */}
        <div className="flex items-center gap-2 overflow-x-auto py-4">
          {categories.map((cat) => {
            const isActive =
              (cat === 'All' && !selectedCategory) ||
              selectedCategory?.toLowerCase() === cat.toLowerCase();
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat === 'All' ? null : cat)}
                className={`px-4 py-2 rounded-xl font-['Inter'] text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? 'bg-surface-container text-secondary ring-1 ring-secondary/40 shadow-sm'
                    : 'bg-surface-container-low text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                }`}
              >
                {cat === 'All' ? '⚡ All Channels' : `#${cat}`}
              </button>
            );
          })}
        </div>

        {/* Top Leaderboard Podium Ribbon */}
        <div className="my-6 p-5 rounded-2xl bg-surface-container-low border border-surface-container-highest/30 shadow-lg">
          <div className="flex items-center justify-between pb-3 border-b border-surface-container-highest/30 mb-4">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-amber-400 text-[20px]">emoji_events</span>
              <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface">Weekly Hall of Fame</h3>
            </div>
            <span className="font-['JetBrains_Mono'] text-xs text-secondary">Updated real-time</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {topCreators.map((creator) => (
              <div
                key={creator.handle}
                className="p-3 rounded-xl bg-surface-container border border-surface-container-highest/20 flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex items-center justify-center font-bold text-xs text-primary">
                    {creator.rank}
                  </div>
                  <div className="min-w-0">
                    <p className="font-['Plus_Jakarta_Sans'] font-bold text-xs text-on-surface truncate">
                      {creator.handle}
                    </p>
                    <p className="font-['Inter'] text-[10px] text-outline">
                      {creator.memes} drops • <span className="text-secondary">{creator.tier}</span>
                    </p>
                  </div>
                </div>
                <span className="font-['JetBrains_Mono'] text-xs text-primary font-bold shrink-0">
                  {creator.aura}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Memes Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPosts.map((post) => (
            <div
              key={post.id}
              className="bg-surface-container-low rounded-xl overflow-hidden border border-surface-container-highest/30 shadow-md hover:shadow-xl transition-all duration-300 flex flex-col justify-between"
            >
              <div>
                {/* Media frame */}
                <div className="relative aspect-[16/10] bg-surface-container-lowest overflow-hidden">
                  <img
                    alt={post.title}
                    src={post.imageUrl}
                    className="w-full h-full object-cover transition-transform duration-500 hover:scale-105"
                  />
                  <div className="absolute top-3 left-3 px-2 py-0.5 rounded-full bg-surface-container-lowest/80 backdrop-blur-md text-secondary font-['Inter'] text-[10px] font-bold">
                    #{post.category}
                  </div>
                  <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-surface-container-lowest/80 backdrop-blur-md text-outline font-['JetBrains_Mono'] text-[10px]">
                    {post.buildMeta || '0.04s'}
                  </div>
                </div>

                {/* Content */}
                <div className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${post.author.avatarBg}`}
                    >
                      {post.author.initials}
                    </div>
                    <span className="font-['Plus_Jakarta_Sans'] font-semibold text-xs text-on-surface">
                      {post.author.username}
                    </span>
                    <span className="text-[11px] text-outline">• {post.timeAgo}</span>
                  </div>
                  <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface line-clamp-2 leading-snug">
                    {post.title}
                  </h3>
                </div>
              </div>

              {/* Action dock */}
              <div className="p-4 pt-0 border-t border-surface-container-highest/20 mt-2 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => toggleReaction()}
                    className="flex items-center gap-1 px-2 py-1 rounded-full bg-surface-container text-xs hover:bg-surface-container-high transition-colors cursor-pointer"
                  >
                    <span>🤣</span>
                    <span className="font-['JetBrains_Mono'] text-secondary font-semibold">
                      {formatAuraNumber(post.reactions.laugh, true)}
                    </span>
                  </button>
                  <button
                    onClick={() => toggleReaction()}
                    className="flex items-center gap-1 px-2 py-1 rounded-full bg-surface-container text-xs hover:bg-surface-container-high transition-colors cursor-pointer"
                  >
                    <span>🔥</span>
                    <span className="font-['JetBrains_Mono']">{formatAuraNumber(post.reactions.fire)}</span>
                  </button>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => toggleBookmark()}
                    className="p-1 rounded text-outline hover:text-on-surface cursor-pointer"
                    title="Save"
                  >
                    <span className="material-symbols-outlined text-[16px]">bookmark</span>
                  </button>
                  <button
                    onClick={() => awardAuraToPost()}
                    className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-primary to-secondary text-on-primary-fixed font-['Inter'] font-semibold text-xs cursor-pointer shadow-sm hover:opacity-90 active:scale-95 transition-all"
                  >
                    +50 Aura
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
