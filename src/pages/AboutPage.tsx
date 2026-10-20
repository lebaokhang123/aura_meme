import { Link } from 'react-router-dom';
import React from 'react';
import { useUI } from '../context/UIContext';

export const AboutPage: React.FC = () => {
  const { showToast } = useUI();

  return (
    <div className="w-full">
      {/* Subtle Ambient Glow Orbs */}
      <div className="relative w-full overflow-hidden">
        <div className="absolute -top-32 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-20 right-10 w-80 h-80 bg-secondary/10 rounded-full blur-3xl pointer-events-none" />

        {/* Editorial Header / Manifesto Splash */}
        <section className="w-full px-4 lg:px-6 py-8 max-w-7xl mx-auto relative z-10">
          <div className="flex flex-col lg:flex-row items-start lg:items-end justify-between gap-6 pb-6">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-container-high text-secondary font-['JetBrains_Mono'] text-xs tracking-wide mb-4 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
                MANIFESTO // ACADEMIC R&D BUILD
              </div>
              <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl sm:text-4xl text-on-surface tracking-tight leading-tight">
                About{' '}
                <span className="bg-gradient-to-r from-primary via-primary-container to-secondary bg-clip-text text-transparent drop-shadow-[0_0_25px_rgba(208,188,255,0.4)]">
                  AuraMeme
                </span>
              </h1>
              <p className="mt-3 font-['Inter'] text-sm sm:text-base text-on-surface-variant max-w-2xl leading-relaxed">
                A university ReactJS project reinventing meme culture with Discord-style gamification and Reddit-style community blogging. Built for night-shift creators, scroll connoisseurs, and campus culture architects.
              </p>
            </div>

            {/* Live Community Aura Metric Pill */}
            <div className="bg-surface-container-low p-4 rounded-xl flex items-center gap-4 shadow-lg shrink-0 w-full sm:w-auto border border-surface-container-highest/30">
              <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
                <span className="material-symbols-outlined text-[28px]">electric_bolt</span>
              </div>
              <div>
                <div className="font-['Inter'] font-semibold text-xs uppercase tracking-wider text-outline">
                  Network Aura Level
                </div>
                <div className="font-['Plus_Jakarta_Sans'] font-bold text-xl text-on-surface flex items-center gap-2">
                  <span>982,420</span>
                  <span className="font-['Inter'] text-xs px-2 py-0.5 rounded-full bg-surface-container-highest text-secondary font-bold">
                    +14.2%
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Hero Visual Canvas / Atmosphere Showcase */}
          <div className="relative w-full h-72 sm:h-96 md:h-[420px] rounded-xl overflow-hidden shadow-xl mt-4 group border border-surface-container-highest/40 bg-surface-container-lowest">
            <div
              className="w-full h-full bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-105"
              style={{
                backgroundImage:
                  "url('https://lh3.googleusercontent.com/aida-public/AB6AXuDhr5zP13Odxq4pF2f-5RhreMnYU-43mXDrx_AyeK9nOXsEN-EzImTa7tU-6WB77Rz50z2WKD6YsWMyjDc_PxytOQR9CwT9CZrTojmCLkQ66mevQ6Isqyh41nTkYoXBp27M1QmR2eDwN5fWaApr7hDII5LlAGdmCR9ol4RpV0QggAi8G4PdlT63Uxfz2tXDOHh269fvXmisYMs9LcdFQFeqRsdw9tKTbGCVAsol31s8MW79WKdgeI4')",
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-surface-container-lowest via-surface-container-lowest/50 to-transparent" />
            {/* Floating HUD Tag Layer */}
            <div className="absolute bottom-6 left-6 right-6 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 bg-surface-container-lowest/80 backdrop-blur-md px-3.5 py-2 rounded-lg shadow-md border border-surface-container-highest/30">
                <span className="material-symbols-outlined text-secondary text-[20px]">hub</span>
                <span className="font-['Inter'] text-xs font-semibold text-on-surface">
                  Decentralized Vibe Index • Node #084
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full bg-surface-container-highest/90 text-primary-fixed-dim font-['JetBrains_Mono'] text-xs backdrop-blur-md">
                  CS302 Capstone
                </span>
                <span className="px-3 py-1 rounded-full bg-secondary-container/80 text-on-secondary-container font-['JetBrains_Mono'] text-xs font-bold backdrop-blur-md">
                  Vite
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Mission & Core Philosophy */}
        <section className="w-full px-4 lg:px-6 py-8 max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-6">
            <div>
              <span className="font-['Inter'] text-xs font-bold tracking-widest text-primary uppercase">
                Core Directives
              </span>
              <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-2xl text-on-surface mt-1">
                Our Mission & Philosophy
              </h2>
            </div>
            <p className="font-['Inter'] text-xs text-on-surface-variant max-w-md mt-2 md:mt-0">
              Bridging genuine college humor and gamified social protocols into a single, lightning-fast web experience.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Card 1 */}
            <div className="bg-surface-container-low rounded-xl p-6 flex flex-col justify-between shadow-md hover:shadow-xl transition-all duration-300 group border border-surface-container-highest/30">
              <div>
                <div className="w-12 h-12 rounded-xl bg-surface-container-highest flex items-center justify-center text-secondary mb-4 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-[26px]">grid_view</span>
                </div>
                <div className="font-['Inter'] font-semibold text-xs text-outline uppercase tracking-wider mb-1">
                  01 / DISCOVERY
                </div>
                <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-base text-on-surface mb-2">
                  Share & Discover Memes
                </h3>
                <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                  Community-driven micro-blog for college students and meme artisans to curate punchy content across Gaming, Tech, Anime, and late-night University life. No generic algorithms—pure peer curation.
                </p>
              </div>
              <div className="mt-6 pt-3 flex items-center gap-2 border-t border-surface-container-highest/20">
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-['JetBrains_Mono'] text-[11px]">
                  #cs-humor
                </span>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-['JetBrains_Mono'] text-[11px]">
                  #dormlife
                </span>
                <span className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface-variant font-['JetBrains_Mono'] text-[11px]">
                  #finals
                </span>
              </div>
            </div>

            {/* Card 2 */}
            <div className="bg-surface-container-low rounded-xl p-6 flex flex-col justify-between shadow-md hover:shadow-xl transition-all duration-300 group border border-surface-container-highest/30">
              <div>
                <div className="w-12 h-12 rounded-xl bg-surface-container-highest flex items-center justify-center text-primary mb-4 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-[26px]">local_fire_department</span>
                </div>
                <div className="font-['Inter'] font-semibold text-xs text-outline uppercase tracking-wider mb-1">
                  02 / RECOGNITION
                </div>
                <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-base text-on-surface mb-2">
                  Earn & Level Up Aura
                </h3>
                <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                  Every laugh counts toward your rep. Collect upvotes, trigger LOL and Fire reactions, complete daily publishing streaks, and watch your aggregate Aura score climb with zero pay-to-win mechanics.
                </p>
              </div>
              <div className="mt-6 bg-surface-container p-2 rounded-lg flex items-center justify-around border border-surface-container-highest/20">
                <span className="inline-flex items-center gap-1 font-['JetBrains_Mono'] text-xs text-on-surface">
                  <span>🔥</span> 4.2k
                </span>
                <span className="inline-flex items-center gap-1 font-['JetBrains_Mono'] text-xs text-on-surface">
                  <span>💀</span> 1.8k
                </span>
                <span className="inline-flex items-center gap-1 font-['JetBrains_Mono'] text-xs text-on-surface">
                  <span>⚡</span> 890
                </span>
              </div>
            </div>

            {/* Card 3 */}
            <div className="bg-surface-container-low rounded-xl p-6 flex flex-col justify-between shadow-md hover:shadow-xl transition-all duration-300 group border border-surface-container-highest/30">
              <div>
                <div className="w-12 h-12 rounded-xl bg-surface-container-highest flex items-center justify-center text-secondary mb-4 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-[26px]">military_tech</span>
                </div>
                <div className="font-['Inter'] font-semibold text-xs text-outline uppercase tracking-wider mb-1">
                  03 / STATUS TIER
                </div>
                <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-base text-on-surface mb-2">
                  Interactive Gamification
                </h3>
                <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                  Ascend rank ranks from Aura Novice all the way to Aura Legend. Unlock rare holographic avatar frames, custom Discord-styled perks, and campus leaderboard bragging rights.
                </p>
              </div>
              <div className="mt-6 flex items-center gap-2">
                <div className="px-2.5 py-1 rounded-full bg-primary/10 text-primary font-['Inter'] text-xs inline-flex items-center gap-1 font-semibold">
                  <span className="material-symbols-outlined text-[14px]">shield</span> Novice
                </div>
                <span className="text-outline">→</span>
                <div className="px-2.5 py-1 rounded-full bg-secondary/10 text-secondary font-['Inter'] text-xs inline-flex items-center gap-1 font-bold">
                  <span className="material-symbols-outlined text-[14px]">workspace_premium</span> Legend
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Gamification Engine: How Aura Works */}
        <section className="w-full px-4 lg:px-6 py-8 max-w-7xl mx-auto">
          <div className="bg-surface-container-lowest rounded-xl p-6 md:p-8 shadow-xl relative overflow-hidden border border-surface-container-highest/30">
            <div className="flex flex-col md:flex-row md:items-end justify-between mb-6">
              <div>
                <div className="inline-flex items-center gap-2 text-primary font-['JetBrains_Mono'] text-xs mb-1 uppercase tracking-wider">
                  <span className="material-symbols-outlined text-[18px]">account_tree</span>
                  System Workflow
                </div>
                <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-2xl text-on-surface">How Aura Works</h2>
              </div>
              <p className="font-['Inter'] text-xs text-on-surface-variant max-w-sm mt-2 md:mt-0">
                A 4-step perpetual loop transforming viral humor into verifiable status.
              </p>
            </div>

            {/* 4 Steps Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 relative">
              {/* Step 1 */}
              <div className="bg-surface-container rounded-xl p-4 flex flex-col justify-between shadow-sm border border-surface-container-highest/20 hover:bg-surface-container-high transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-full bg-surface-container-highest text-on-surface font-['JetBrains_Mono'] text-xs font-bold flex items-center justify-center">
                      01
                    </span>
                    <span className="material-symbols-outlined text-secondary text-[24px]">post_add</span>
                  </div>
                  <h4 className="font-['Plus_Jakarta_Sans'] font-semibold text-sm text-on-surface mb-1">
                    Post Quality Memes
                  </h4>
                  <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                    Publish high-res image drops, GIF loops, or witty college observations into dedicated niche feeds.
                  </p>
                </div>
                <div className="mt-4 pt-1 flex items-center text-primary font-['Inter'] text-xs font-semibold">
                  <span>Markdown + Media</span>
                </div>
              </div>

              {/* Step 2 */}
              <div className="bg-surface-container rounded-xl p-4 flex flex-col justify-between shadow-sm border border-surface-container-highest/20 hover:bg-surface-container-high transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-full bg-surface-container-highest text-on-surface font-['JetBrains_Mono'] text-xs font-bold flex items-center justify-center">
                      02
                    </span>
                    <span className="material-symbols-outlined text-primary text-[24px]">mood</span>
                  </div>
                  <h4 className="font-['Plus_Jakarta_Sans'] font-semibold text-sm text-on-surface mb-1">
                    Receive Reactions
                  </h4>
                  <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                    Peers react in real-time with custom emojis: Like, LOL, Fire, or Clown depending on the absurdity.
                  </p>
                </div>
                <div className="mt-4 pt-1 flex items-center text-secondary font-['Inter'] text-xs font-semibold">
                  <span>Multi-Emoji Weights</span>
                </div>
              </div>

              {/* Step 3 */}
              <div className="bg-surface-container rounded-xl p-4 flex flex-col justify-between shadow-sm border border-surface-container-highest/20 hover:bg-surface-container-high transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-full bg-surface-container-highest text-on-surface font-['JetBrains_Mono'] text-xs font-bold flex items-center justify-center">
                      03
                    </span>
                    <span className="material-symbols-outlined text-secondary text-[24px]">trending_up</span>
                  </div>
                  <h4 className="font-['Plus_Jakarta_Sans'] font-semibold text-sm text-on-surface mb-1">
                    Gain Aura Points
                  </h4>
                  <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                    Algorithmically compiled Aura points increment your profile XP gauge and maintain your hot-streak index.
                  </p>
                </div>
                <div className="mt-4 pt-1">
                  <div className="w-full bg-surface-container-highest h-2 rounded-full overflow-hidden">
                    <div className="bg-gradient-to-r from-primary to-secondary h-full rounded-full" style={{ width: '76%' }} />
                  </div>
                  <div className="flex justify-between font-['JetBrains_Mono'] text-[10px] text-outline mt-1">
                    <span>XP 1,520</span>
                    <span>LEVEL UP 2,000</span>
                  </div>
                </div>
              </div>

              {/* Step 4 */}
              <div className="bg-surface-container rounded-xl p-4 flex flex-col justify-between shadow-sm border border-surface-container-highest/20 hover:bg-surface-container-high transition-colors">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="w-8 h-8 rounded-full bg-surface-container-highest text-primary font-['JetBrains_Mono'] text-xs font-bold flex items-center justify-center">
                      04
                    </span>
                    <span className="material-symbols-outlined text-primary text-[24px]">star</span>
                  </div>
                  <h4 className="font-['Plus_Jakarta_Sans'] font-semibold text-sm text-on-surface mb-1">
                    Unlock Nitro Perks
                  </h4>
                  <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                    Cash out aura into custom neon user-handles, hall-of-fame podium ranks, and exclusive site themes.
                  </p>
                </div>
                <div className="mt-4 pt-1 flex items-center text-primary font-['Inter'] text-xs font-semibold">
                  <span>Cosmetics • Badges</span>
                </div>
              </div>
            </div>

            {/* Interactive Playground Mini-Widget */}
            <div className="mt-6 bg-surface-container-low rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4 border border-surface-container-highest/30">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-secondary">
                  <span className="material-symbols-outlined text-[20px]">science</span>
                </div>
                <div>
                  <div className="font-['Inter'] font-semibold text-xs text-on-surface">
                    Test the Aura Multiplier Formula
                  </div>
                  <div className="font-['Inter'] text-xs text-on-surface-variant">
                    Preview only — Aura points stay unchanged.
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 w-full md:w-auto">
                <button
                  onClick={() => showToast('Aura values are sample data in this prototype.')}
                  className="w-full md:w-auto px-4 py-2 rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface font-['Inter'] font-semibold text-xs transition-colors flex items-center justify-center gap-2 cursor-pointer active:scale-95"
                  type="button"
                >
                  <span className="material-symbols-outlined text-[16px] text-secondary">bolt</span>
                  Simulate Viral Upvote
                </button>
                <div className="px-3 py-1.5 bg-surface-container-highest rounded-lg font-['JetBrains_Mono'] text-xs text-secondary font-bold shrink-0">
                  <span>+250 XP (sample)</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Visual Asymmetric Spotlight / College Team Workspace */}
        <section className="w-full px-4 lg:px-6 py-6 max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            {/* Photo Vignette Left */}
            <div className="lg:col-span-5 relative">
              <div className="w-full h-80 sm:h-96 rounded-xl overflow-hidden shadow-xl border border-surface-container-highest/30 bg-surface-container-lowest">
                <img
                  className="w-full h-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuCS-pLqdkBp-o7iYkgYOEmR_LtYlUasmGbeEqMtlqWItp0YXmEedsT_NJV6Df1bq-8ACBF3koyOPiHFfZ4ESZ2-lf1UAjsGdmOfhj_G6I0F2id1OOqGqB3XJa0ckVCfVtM0nRiiHWxNMQ0F-No3KuXQSTJrCONmRK74AelFrAkpyCmIj5s9dWXAbD22f04DoR42V7SUqgaZijKZD9LyjZsShA5AJfDIijN4YgfNiECJXDjHh1vRQcM"
                  alt="Student programmers collaborating during hackathon sprint"
                />
              </div>
              <div className="absolute -bottom-4 -right-4 bg-surface-container-high p-4 rounded-xl shadow-2xl max-w-xs hidden sm:block border border-surface-container-highest/40">
                <div className="flex items-center gap-1.5 text-secondary mb-1">
                  <span className="material-symbols-outlined text-[18px]">verified</span>
                  <span className="font-['Inter'] font-bold text-xs uppercase tracking-wider">Lab Approved</span>
                </div>
                <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed">
                  Built during sleepless 72-hour sprint iterations for the CS302 Final Showcase.
                </p>
              </div>
            </div>

            {/* Text Right */}
            <div className="lg:col-span-7 lg:pl-6">
              <span className="font-['Inter'] text-xs text-primary uppercase tracking-widest font-bold">
                Project Genesis
              </span>
              <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-2xl text-on-surface mt-2 mb-3">
                Why We Built AuraMeme
              </h2>
              <p className="font-['Inter'] text-xs sm:text-sm text-on-surface-variant leading-relaxed mb-3">
                Mainstream social platforms optimize exclusively for engagement farms and sterile sponsor content. College group chats, meanwhile, were overflowing with gold-standard comedy that vanished into ephemeral thread histories.
              </p>
              <p className="font-['Inter'] text-xs sm:text-sm text-on-surface-variant leading-relaxed mb-6">
                We wanted to build an ecosystem where humor carries permanent equity. By engineering a hybrid of Reddit’s threaded discovery and Discord’s badge-first gamified identity, AuraMeme gives creators a high-octane stage to celebrate internet craftsmanship.
              </p>
              {/* Core Stat Tickers */}
              <div className="grid grid-cols-3 gap-3 pt-1">
                <div className="bg-surface-container-low p-3.5 rounded-xl border border-surface-container-highest/20">
                  <div className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-primary">100%</div>
                  <div className="font-['Inter'] text-xs text-outline">Student Engineered</div>
                </div>
                <div className="bg-surface-container-low p-3.5 rounded-xl border border-surface-container-highest/20">
                  <div className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-secondary">&lt; 40ms</div>
                  <div className="font-['Inter'] text-xs text-outline">Vite HMR Latency</div>
                </div>
                <div className="bg-surface-container-low p-3.5 rounded-xl border border-surface-container-highest/20">
                  <div className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-on-surface">0 Ads</div>
                  <div className="font-['Inter'] text-xs text-outline">Community Owned</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Tech Stack & Project Info Banner */}
        <section className="w-full px-4 lg:px-6 py-8 max-w-7xl mx-auto">
          <div className="bg-gradient-to-r from-surface-container-high via-surface-container to-surface-container-high rounded-xl p-6 lg:p-8 shadow-2xl relative overflow-hidden border border-surface-container-highest/40">
            <div className="absolute -right-16 -top-16 w-64 h-64 bg-primary-container/20 rounded-full blur-2xl pointer-events-none" />
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 relative z-10">
              <div className="max-w-2xl">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-container-highest text-secondary font-['JetBrains_Mono'] text-xs uppercase tracking-wide mb-2">
                  <span className="material-symbols-outlined text-[16px]">code</span>
                  Architecture Overview
                </div>
                <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-xl text-on-surface mb-2">
                  Built for CS Web Development
                </h3>
                <p className="font-['Inter'] text-xs text-on-surface-variant leading-relaxed mb-4">
                  Powered by a modern front-end workflow: React components, React Router navigation, Vite, and Tailwind CSS. This classroom prototype uses fixed sample data.
                </p>
                {/* Pill Badges of Stack Components */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface font-['JetBrains_Mono'] text-xs shadow-sm">
                    React
                  </span>
                  <span className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface font-['JetBrains_Mono'] text-xs shadow-sm">
                    React Router
                  </span>
                  <span className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface font-['JetBrains_Mono'] text-xs shadow-sm">
                    Vite.js
                  </span>
                  <span className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface font-['JetBrains_Mono'] text-xs shadow-sm">
                    Tailwind CSS
                  </span>
                  <span className="px-3 py-1 rounded-lg bg-surface-container-lowest text-on-surface font-['JetBrains_Mono'] text-xs shadow-sm">
                    CSS
                  </span>
                </div>
              </div>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto shrink-0">
                <Link to="/team"

                  className="inline-flex items-center justify-center gap-2 h-11 px-5 rounded-xl bg-gradient-to-r from-primary-container to-inverse-primary text-on-primary font-['Inter'] font-semibold text-xs shadow-[0_0_16px_rgba(160,120,255,0.35)] hover:shadow-[0_0_24px_rgba(160,120,255,0.5)] transition-all cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[18px]">groups</span>
                  <span>Meet The Team</span>
                </Link>
                <a
                  href="https://github.com/lebaokhang123/aura_meme"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 h-11 px-5 rounded-xl bg-surface-container-highest hover:bg-surface-bright text-on-surface font-['Inter'] font-semibold text-xs transition-all shadow-sm cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[18px]">terminal</span>
                  <span>Inspect Source</span>
                </a>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
