import { Link } from 'react-router-dom';
import React from 'react';
import { useUI } from '../context/UIContext';
import { levelInfo } from '../data/mockData';
import { PostCard } from '../components/PostCard';

export const HomePage: React.FC = () => {
  const {
    posts,
    user,
    claimDailyBonus,
    dailyBonusClaimed,
    showNitroPreview,
    showCreatePostPreview,
    selectedCategory,
    setSelectedCategory,
    feedTab,
    setFeedTab,
    showToast,
    } = useUI();

  const isLoadingMore = false;
  const extraBatchesLoaded = 0;

  // Filter posts by selected category if active
  const filteredPosts = selectedCategory
    ? posts.filter((p) => p.category.toLowerCase() === selectedCategory.toLowerCase())
    : posts;

  // Sort according to active tab
  const sortedPosts = [...filteredPosts].sort((a, b) => {
    if (feedTab === 'top') {
      const aTotal = a.reactions.like + a.reactions.laugh + a.reactions.fire;
      const bTotal = b.reactions.like + b.reactions.laugh + b.reactions.fire;
      return bTotal - aTotal;
    }
    if (feedTab === 'new') return posts.indexOf(a) - posts.indexOf(b);
    return 0; // Keep the sample feed order.
  });

  const categories = [
    { name: 'Gaming', icon: 'sports_esports', count: '142k', color: 'text-primary', activeColor: 'bg-primary-container text-on-primary' },
    { name: 'Anime', icon: 'auto_awesome', count: '98k', color: 'text-secondary', activeColor: 'bg-secondary-container text-on-secondary' },
    { name: 'Technology', icon: 'terminal', count: '87k', color: 'text-tertiary', activeColor: 'bg-tertiary-container text-on-tertiary' },
    { name: 'School', icon: 'school', count: '45k', color: 'text-primary', activeColor: 'bg-primary-container text-on-primary' },
    { name: 'Random', icon: 'casino', count: '62k', color: 'text-secondary', activeColor: 'bg-secondary-container text-on-secondary' },
  ];

  const handleLoadMore = () => showToast('All sample posts are already displayed.');

  return (
    <div className="w-full">
      {/* Dynamic Atmospheric Glow Backdrop */}
      <div className="relative w-full overflow-hidden">
        <div className="absolute -top-32 left-1/4 w-96 h-96 bg-primary-container/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-48 right-1/4 w-80 h-80 bg-secondary/10 rounded-full blur-3xl pointer-events-none" />

        {/* 3-Column Master Layout Frame */}
        <div className="w-full max-w-[1560px] mx-auto px-4 sm:px-6 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* ========================================== */}
            {/* LEFT COLUMN: Navigation & Subreddits Dock  */}
            {/* ========================================== */}
            <aside className="hidden lg:block lg:col-span-3 xl:col-span-3 sticky top-20 space-y-4">
              {/* Primary Feed Nav Card */}
              <div className="bg-surface-container-low rounded-xl p-4 shadow-md border border-surface-container-highest/30">
                <div className="px-1 pb-2">
                  <span className="font-['Inter'] text-xs tracking-wider uppercase text-outline">Feeds Navigation</span>
                </div>
                <nav className="flex flex-col gap-1">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg font-['Inter'] text-[13px] font-semibold transition-all cursor-pointer ${
                      selectedCategory === null
                        ? 'bg-surface-container-high text-primary shadow-[0_0_12px_rgba(160,120,255,0.25)]'
                        : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-[20px] text-primary">home</span>
                      <span>Home Feed</span>
                    </div>
                    {selectedCategory === null && <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />}
                  </button>

                  <button
                    onClick={() => {
                      setSelectedCategory(null);
                      setFeedTab('hot');
                      showToast('🔥 Switched to Popular Hot stream!');
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface font-['Inter'] text-[13px] font-semibold transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-[20px] text-outline group-hover:text-secondary transition-colors">
                        local_fire_department
                      </span>
                      <span>Popular</span>
                    </div>
                    <span className="font-['JetBrains_Mono'] text-xs text-outline group-hover:text-secondary">HOT</span>
                  </button>

                  <button
                    onClick={() => {
                      setSelectedCategory(null);
                      setFeedTab('new');
                      showToast('🌐 Syncing all campus channels...');
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface font-['Inter'] text-[13px] font-semibold transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-2">
                      <span className="material-symbols-outlined text-[20px] text-outline group-hover:text-on-surface transition-colors">
                        public
                      </span>
                      <span>All Channels</span>
                    </div>
                    <span className="px-1.5 py-0.5 rounded-full bg-surface-container-highest font-['JetBrains_Mono'] text-[10px] text-on-surface-variant">
                      SYNC
                    </span>
                  </button>
                </nav>
              </div>

              {/* Categories Channel Hub */}
              <div className="bg-surface-container-low rounded-xl p-4 shadow-md border border-surface-container-highest/30">
                <div className="flex items-center justify-between px-1 pb-2">
                  <span className="font-['Inter'] text-xs tracking-wider uppercase text-outline">Categories</span>
                  {selectedCategory && (
                    <button
                      onClick={() => setSelectedCategory(null)}
                      className="font-['JetBrains_Mono'] text-xs text-secondary hover:underline cursor-pointer"
                    >
                      Clear
                    </button>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  {categories.map((cat) => {
                    const isCatActive = selectedCategory?.toLowerCase() === cat.name.toLowerCase();
                    return (
                      <button
                        key={cat.name}
                        onClick={() => setSelectedCategory(isCatActive ? null : cat.name)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-all cursor-pointer group ${
                          isCatActive
                            ? 'bg-surface-container text-on-surface shadow-sm ring-1 ring-primary/40'
                            : 'hover:bg-surface-container text-on-surface-variant hover:text-on-surface'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-7 h-7 rounded-md bg-surface-container-high flex items-center justify-center transition-colors ${
                              isCatActive ? cat.activeColor : `${cat.color} group-hover:bg-surface-bright`
                            }`}
                          >
                            <span className="material-symbols-outlined text-[18px]">{cat.icon}</span>
                          </span>
                          <span className="font-medium text-xs text-on-surface">{cat.name}</span>
                        </div>
                        <span className="font-['JetBrains_Mono'] text-xs px-1.5 py-0.5 rounded bg-surface-container-highest text-outline">
                          {cat.count}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quick Community Discord Card */}
              <div className="relative overflow-hidden rounded-xl bg-gradient-to-b from-surface-container to-surface-container-lowest p-5 shadow-md border border-surface-container-highest/40">
                <div className="absolute -top-10 -right-10 w-24 h-24 bg-primary/20 rounded-full blur-xl pointer-events-none" />
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-[24px] text-tertiary">forum</span>
                  <span className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface">Aura Central</span>
                </div>
                <p className="font-['Inter'] text-xs text-on-surface-variant mb-4 leading-relaxed">
                  24/7 live voice lounges, instant meme drops, code debug squads, and aura bot rewards.
                </p>
                <a
                  href="https://discord.com"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg bg-surface-container-high hover:bg-primary text-on-surface hover:text-on-primary font-['Inter'] font-semibold text-xs shadow-sm transition-all duration-200"
                >
                  <span className="material-symbols-outlined text-[16px]">rocket_launch</span>
                  Join Aura Discord
                </a>
              </div>

              {/* Micro links */}
              <div className="px-2 flex flex-wrap gap-x-3 gap-y-1 font-['Inter'] text-[11px] text-outline">
                <Link to="/about-us"  className="hover:text-on-surface transition-colors cursor-pointer">
                  Content Policy
                </Link>
                <span>•</span>
                <Link to="/team"  className="hover:text-on-surface transition-colors cursor-pointer">
                  Mod Tools
                </Link>
                <span>•</span>
                <Link to="/contact"  className="hover:text-on-surface transition-colors cursor-pointer">
                  API Status
                </Link>
              </div>
            </aside>

            {/* ========================================== */}
            {/* CENTER COLUMN: Primary Social Meme Feed    */}
            {/* ========================================== */}
            <main className="col-span-1 lg:col-span-9 xl:col-span-6 space-y-4">
              {/* Feed Header Banner HUD */}
              <div className="relative overflow-hidden rounded-xl bg-surface-container-low p-5 shadow-md border border-surface-container-highest/30">
                <div className="absolute -right-8 -top-8 w-44 h-44 bg-gradient-to-br from-primary-container/20 to-secondary/20 rounded-full blur-2xl pointer-events-none" />
                <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-container-high font-['Inter'] text-xs font-semibold text-secondary">
                      <span className="material-symbols-outlined text-[14px]">trending_up</span> Season 3 Live
                    </div>
                    <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-2xl text-on-surface tracking-tight">
                      Level up your Aura, one meme at a time.
                    </h1>
                    <p className="font-['Inter'] text-xs text-primary font-medium">
                      Share top-tier memes, earn Aura points, unlock perks.
                    </p>
                  </div>

                  {/* Daily Bonus Claim Button */}
                  <button
                    onClick={claimDailyBonus}
                    disabled={dailyBonusClaimed}
                    className={`shrink-0 flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all cursor-pointer text-left ${
                      dailyBonusClaimed
                        ? 'bg-surface-container/60 opacity-80 cursor-default'
                        : 'bg-surface-container hover:bg-surface-container-high shadow-inner active:scale-95'
                    }`}
                  >
                    <div className="w-10 h-10 rounded-lg bg-surface-container-highest flex items-center justify-center text-secondary">
                      <span className="material-symbols-outlined text-[24px]">award_star</span>
                    </div>
                    <div>
                      <div className="font-['JetBrains_Mono'] text-[11px] text-outline uppercase tracking-wider">
                        {dailyBonusClaimed ? 'Claimed Today' : 'Daily Bonus'}
                      </div>
                      <div className="font-['Plus_Jakarta_Sans'] font-bold text-xs text-on-surface">
                        {dailyBonusClaimed ? 'Streak Active 🔥' : '+150 XP Ready'}
                      </div>
                    </div>
                  </button>
                </div>

                {/* Interactive Create Post Prompt Box */}
                <div className="mt-4 pt-3 bg-surface-container rounded-xl p-3 shadow-inner border border-surface-container-highest/20">
                  <div className="flex items-center gap-3">
                    <img
                      alt="Profile Avatar"
                      className="w-10 h-10 rounded-full object-cover shrink-0 ring-2 ring-primary/40"
                      src={user.avatar}
                    />
                    <div className="relative flex-1">
                      <input
                        onClick={() => showCreatePostPreview()}
                        readOnly
                        className="w-full h-10 pl-3.5 pr-3.5 bg-surface-container-lowest rounded-lg text-on-surface placeholder:text-outline font-['Inter'] text-xs focus:outline-none cursor-pointer transition-all hover:bg-surface-container-low"
                        placeholder="Draft a meme or drop an image link..."
                        type="text"
                      />
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 mt-3 pt-2 border-t border-surface-container-highest/20">
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => showCreatePostPreview()}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant hover:text-on-surface font-['Inter'] text-xs transition-colors cursor-pointer"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[16px] text-secondary">image</span>
                        <span className="hidden sm:inline">Image / GIF</span>
                      </button>
                      <button
                        onClick={() => showCreatePostPreview()}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant hover:text-on-surface font-['Inter'] text-xs transition-colors cursor-pointer"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[16px] text-tertiary">how_to_vote</span>
                        <span className="hidden sm:inline">Poll</span>
                      </button>
                      <button
                        onClick={() => showCreatePostPreview()}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant hover:text-on-surface font-['Inter'] text-xs transition-colors cursor-pointer"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[16px] text-outline">link</span>
                        <span className="hidden sm:inline">Link</span>
                      </button>
                    </div>
                    <button
                      onClick={() => showCreatePostPreview()}
                      className="inline-flex items-center gap-1 px-4 py-1.5 rounded-lg bg-primary hover:bg-primary-container text-on-primary font-['Inter'] font-semibold text-xs shadow-[0_0_12px_rgba(160,120,255,0.35)] transition-all cursor-pointer"
                      type="button"
                    >
                      <span className="material-symbols-outlined text-[16px]">send</span>
                      Create Post
                    </button>
                  </div>
                </div>
              </div>

              {/* Sorting Tabs Bar */}
              <div className="flex items-center justify-between bg-surface-container-low px-4 py-2 rounded-xl shadow-sm border border-surface-container-highest/20">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setFeedTab('hot')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-['Inter'] text-xs font-semibold cursor-pointer transition-colors ${
                      feedTab === 'hot'
                        ? 'bg-surface-container text-secondary shadow-sm'
                        : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                    }`}
                    type="button"
                  >
                    <span className="material-symbols-outlined text-[16px]">local_fire_department</span>
                    Hot
                  </button>
                  <button
                    onClick={() => setFeedTab('new')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-['Inter'] text-xs font-semibold cursor-pointer transition-colors ${
                      feedTab === 'new'
                        ? 'bg-surface-container text-secondary shadow-sm'
                        : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                    }`}
                    type="button"
                  >
                    <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
                    New
                  </button>
                  <button
                    onClick={() => setFeedTab('top')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-['Inter'] text-xs font-semibold cursor-pointer transition-colors ${
                      feedTab === 'top'
                        ? 'bg-surface-container text-secondary shadow-sm'
                        : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                    }`}
                    type="button"
                  >
                    <span className="material-symbols-outlined text-[16px]">emoji_events</span>
                    <span>Top</span>
                  </button>
                </div>
                {selectedCategory && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-outline">Filtered:</span>
                    <span className="font-semibold text-secondary">#{selectedCategory}</span>
                    <button
                      onClick={() => setSelectedCategory(null)}
                      className="text-xs text-outline hover:text-on-surface ml-1"
                    >
                      ✕
                    </button>
                  </div>
                )}
              </div>

              {/* Meme Posts Feed */}
              {sortedPosts.length === 0 && <p className="p-5 text-on-surface-variant" role="status">No sample posts in this category.</p>}
              {sortedPosts.map((post) => (
                <PostCard key={post.id} post={post} />
              ))}

              {/* Stream Pagination Loader */}
              <div className="flex items-center justify-center py-4">
                <button
                  onClick={handleLoadMore}
                  disabled={isLoadingMore}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-surface-container hover:bg-surface-container-high text-on-surface font-['Inter'] font-semibold text-xs transition-all shadow-sm cursor-pointer disabled:opacity-50"
                  type="button"
                >
                  {isLoadingMore ? (
                    <>
                      <span className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                      <span>Loading next batch of memes...</span>
                    </>
                  ) : (
                    <span>Load more campus memes ({extraBatchesLoaded > 0 ? `${extraBatchesLoaded} synced` : 'Scroll next'})</span>
                  )}
                </button>
              </div>
            </main>

            {/* ========================================== */}
            {/* RIGHT COLUMN: Gamification & Leaderboard   */}
            {/* ========================================== */}
            <aside className="col-span-1 lg:col-span-12 xl:col-span-3 sticky top-20 space-y-4">
              {/* User Aura Gamification Card */}
              <div className="relative overflow-hidden rounded-xl bg-surface-container-low p-5 shadow-md border border-surface-container-highest/30">
                <div className="absolute -right-8 -top-8 w-32 h-32 bg-primary/20 rounded-full blur-2xl pointer-events-none" />
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    {/* Glowing Purple Crest */}
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-primary-container to-inverse-primary flex items-center justify-center text-on-primary shadow-[0_0_16px_rgba(160,120,255,0.4)]">
                      <span className="material-symbols-outlined text-[26px]">shield_with_heart</span>
                    </div>
                    <div>
                      <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface">Level {levelInfo.level}</div>
                      <div className="font-['Inter'] text-xs text-secondary font-medium">{levelInfo.rankTitle}</div>
                    </div>
                  </div>
                  <span className="font-['JetBrains_Mono'] text-xs px-2 py-0.5 rounded bg-surface-container font-bold text-primary">
                    LVL {levelInfo.level}
                  </span>
                </div>

                {/* Stats Cluster */}
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <div className="p-2.5 rounded-lg bg-surface-container">
                    <div className="font-['Inter'] text-[11px] text-outline uppercase tracking-wider">Aura Balance</div>
                    <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface mt-0.5">
                      {user.auraBalance.toLocaleString()} Aura
                    </div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container">
                    <div className="font-['Inter'] text-[11px] text-outline uppercase tracking-wider">Upvote Multiplier</div>
                    <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-secondary mt-0.5">
                      {levelInfo.multiplier}x Active
                    </div>
                  </div>
                </div>

                {/* Progress to Next Rank */}
                <div className="space-y-1.5 mb-3">
                  <div className="flex items-center justify-between font-['JetBrains_Mono'] text-xs">
                    <span className="text-on-surface-variant">Rank Progress</span>
                    <span className="text-primary font-bold">
                      {user.auraBalance.toLocaleString()} / {levelInfo.targetXp.toLocaleString()} XP
                    </span>
                  </div>
                  {/* Gamified XP Progress Bar */}
                  <div className="w-full h-2.5 rounded-full bg-surface-container-highest overflow-hidden relative">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary via-primary-container to-secondary shadow-[0_0_8px_rgba(76,215,246,0.6)] transition-all duration-500"
                      style={{ width: `${levelInfo.progressPercent}%` }}
                    />
                  </div>
                </div>

                {/* Daily Streak Badge */}
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-surface-container-high/60 shadow-inner">
                  <div className="flex items-center gap-1.5 font-['Inter'] text-xs font-semibold text-amber-300">
                    <span className="material-symbols-outlined text-[18px]">local_fire_department</span>
                    <span>{user.streakDays} Day Streak</span>
                  </div>
                  <span className="font-['JetBrains_Mono'] text-[11px] text-outline">+{user.streakDays * 3}% Aura bonus</span>
                </div>
              </div>

              {/* Upgrade to Aura Nitro Card */}
              <div className="relative overflow-hidden rounded-xl bg-gradient-to-b from-surface-container to-surface-container-lowest p-5 shadow-xl border border-surface-container-highest/40">
                <div className="absolute inset-0 bg-gradient-to-tr from-primary-container/10 via-transparent to-secondary/10 pointer-events-none" />
                <div className="relative z-10">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="material-symbols-outlined text-secondary text-[20px]">diamond</span>
                    <span className="font-['Inter'] font-bold text-[11px] uppercase tracking-widest text-secondary">
                      Nitro Perks
                    </span>
                  </div>
                  <h3 className="font-['Plus_Jakarta_Sans'] font-extrabold text-base text-on-surface mb-1">
                    Upgrade to Aura Nitro
                  </h3>
                  <p className="font-['Inter'] text-xs text-on-surface-variant mb-3">
                    Elevate your presence across every channel with elite aesthetic modifiers.
                  </p>
                  <ul className="space-y-1.5 mb-4 font-['Inter'] text-xs text-on-surface">
                    <li className="flex items-center gap-2">
                      <span className="text-primary">✨</span>
                      <span>Animated avatar frame</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-secondary">🎨</span>
                      <span>Custom profile theme & banner</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-tertiary">🔊</span>
                      <span>Reaction sound effects</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="text-primary">💎</span>
                      <span>Exclusive Nitro Aura badge</span>
                    </li>
                  </ul>
                  <button
                    onClick={() => showNitroPreview()}
                    className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-primary-container via-primary to-secondary text-on-primary font-['Plus_Jakarta_Sans'] font-bold text-xs shadow-[0_0_16px_rgba(160,120,255,0.4)] hover:shadow-[0_0_24px_rgba(76,215,246,0.6)] hover:scale-[1.01] transition-all duration-200 cursor-pointer"
                    type="button"
                  >
                    Upgrade to Nitro
                  </button>
                </div>
              </div>

              {/* Trending Tags with SVG Sparklines */}
              <div className="bg-surface-container-low rounded-xl p-4 shadow-md border border-surface-container-highest/30">
                <div className="flex items-center justify-between pb-2 px-1">
                  <span className="font-['Inter'] text-xs tracking-wider uppercase text-outline">Trending Tags</span>
                  <span className="material-symbols-outlined text-[16px] text-outline">query_stats</span>
                </div>
                <div className="space-y-2">
                  <div
                    onClick={() => setSelectedCategory('Gaming')}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container transition-colors cursor-pointer"
                  >
                    <div>
                      <div className="font-['Inter'] font-bold text-xs text-on-surface">#Gaming</div>
                      <div className="font-['Inter'] text-[11px] text-outline">18.4k posts today</div>
                    </div>
                    <svg className="w-16 h-7 text-secondary" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 64 24">
                      <path d="M0 18 L14 14 L28 17 L42 8 L54 11 L64 3" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <div
                    onClick={() => setSelectedCategory('Technology')}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container transition-colors cursor-pointer"
                  >
                    <div>
                      <div className="font-['Inter'] font-bold text-xs text-on-surface">#ReactDev</div>
                      <div className="font-['Inter'] text-[11px] text-outline">9.2k posts today</div>
                    </div>
                    <svg className="w-16 h-7 text-primary" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 64 24">
                      <path d="M0 20 L12 16 L24 10 L38 12 L50 4 L64 2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <div
                    onClick={() => setSelectedCategory('School')}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container transition-colors cursor-pointer"
                  >
                    <div>
                      <div className="font-['Inter'] font-bold text-xs text-on-surface">#FinalsWeek</div>
                      <div className="font-['Inter'] text-[11px] text-outline">6.1k posts today</div>
                    </div>
                    <svg className="w-16 h-7 text-tertiary" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 64 24">
                      <path d="M0 12 L16 18 L30 11 L44 14 L54 6 L64 9" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Mini Aura Leaderboard */}
              <div className="bg-surface-container-low rounded-xl p-4 shadow-md border border-surface-container-highest/30">
                <div className="flex items-center justify-between pb-2 px-1">
                  <span className="font-['Inter'] text-xs tracking-wider uppercase text-outline">Top Aura Creators</span>
                  <span className="font-['JetBrains_Mono'] text-xs text-secondary font-medium">This Week</span>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between p-2 rounded-lg bg-surface-container/60 hover:bg-surface-container transition-colors">
                    <div className="flex items-center gap-2">
                      <span className="text-[16px]">🥇</span>
                      <div className="flex flex-col">
                        <span className="font-['Inter'] font-semibold text-xs text-on-surface">u/PixelWizard</span>
                        <span className="font-['Inter'] text-[11px] text-outline">32 memes posted</span>
                      </div>
                    </div>
                    <span className="font-['JetBrains_Mono'] text-xs text-primary font-bold">18,420 Aura</span>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container transition-colors">
                    <div className="flex items-center gap-2">
                      <span className="text-[16px]">🥈</span>
                      <div className="flex flex-col">
                        <span className="font-['Inter'] font-semibold text-xs text-on-surface">u/SyntaxSamurai</span>
                        <span className="font-['Inter'] text-[11px] text-outline">28 memes posted</span>
                      </div>
                    </div>
                    <span className="font-['JetBrains_Mono'] text-xs text-on-surface-variant font-bold">14,890 Aura</span>
                  </div>
                  <div className="flex items-center justify-between p-2 rounded-lg hover:bg-surface-container transition-colors">
                    <div className="flex items-center gap-2">
                      <span className="text-[16px]">🥉</span>
                      <div className="flex flex-col">
                        <span className="font-['Inter'] font-semibold text-xs text-on-surface">u/ByteQueen</span>
                        <span className="font-['Inter'] text-[11px] text-outline">19 memes posted</span>
                      </div>
                    </div>
                    <span className="font-['JetBrains_Mono'] text-xs text-on-surface-variant font-bold">12,350 Aura</span>
                  </div>
                </div>
                <div className="pt-3 text-center">
                  <Link to="/explore"

                    className="inline-flex items-center gap-1 font-['Inter'] font-semibold text-xs text-primary hover:text-primary-fixed transition-colors cursor-pointer"
                  >
                    <span>View Full Leaderboard</span>
                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                  </Link>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
};
