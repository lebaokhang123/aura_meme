import React, { useState } from 'react';
import { useUI } from '../context/UIContext';

export const TeamPage: React.FC = () => {
  const { communityTeamAura, boostCommunityTeamAura } = useUI();
  const [boostEffect, setBoostEffect] = useState(false);

  const handleBoost = () => {
    setBoostEffect(true);
    boostCommunityTeamAura();
    setTimeout(() => {
      setBoostEffect(false);
    }, 600);
  };

  const teamMembers = [
    {
      name: 'Alex Rivera',
      role: 'Lead Frontend Developer & UI/UX',
      badge: 'Aura Architect',
      status: 'Lead UI/UX',
      level: 24,
      avatar:
        'https://lh3.googleusercontent.com/aida-public/AB6AXuA6ve1ZBjarZKkbXA-CwLjIwEt0-QItx3W0wGsP1ZpW91AJ08CZGQ_Kd8lbnO9q6Lak6RT6yNKnArQJ-m96bvLTLboVGrLHGhcKuaB_evR57FC_6VY7ZM1-RszaoEs6LlfTvR4D6WuOwl5t9YTViz4OwlvyvoGC6J9gHh3m71BQW7iIjoyUYKCxPb1c6lzgQZGFkVQWfaEazQoS-7XZGEMMsAkrBo8hCW_gKcca_gfGheL_qyjLnLo',
      glow: 'from-primary to-primary-container',
      icon: 'brush',
      statusClass: 'bg-primary/10 text-primary',
      indicatorClass: 'bg-primary animate-ping',
      bio: 'Passionate about React state management, dark-mode design systems, and responsive layouts. Built the core feed and Reddit-style reaction system.',
      skills: ['ReactJS', 'Tailwind', 'Figma', 'UI Design'],
      socials: [
        { icon: 'code', label: 'GitHub', url: 'https://github.com' },
        { icon: 'groups', label: 'LinkedIn', url: 'https://linkedin.com' },
        { icon: 'language', label: 'Portfolio', url: '#' },
      ],
    },
    {
      name: 'Sophia Chen',
      role: 'Gamification & Logic Engineer',
      badge: 'Logic Master',
      status: 'Engine Architect',
      level: 21,
      avatar:
        'https://lh3.googleusercontent.com/aida-public/AB6AXuCvffBTdJ4j_xz-OQwWXWhxUa8JLbYmZW0w3WvAyk6hvgF2AbOmN9jCb1-mIuSEwWDLpgBugGh6_uH-kPoHGSlEywRClk2w-JlmD9TFVBgN__huLFLEw8kjb7_soQNwQhafutJrJt_Bh6urQI4dVNpguzPruhkW9XU64g75V0IN17ZhFXg43nKKJLt6nMqGdjkFRNjoQZ6WRsGbYyrikSOBkL9yElhswZPsMQ-dD4gIb4OzcsCKTLc',
      glow: 'from-secondary to-secondary-container',
      icon: 'psychology',
      statusClass: 'bg-secondary/10 text-secondary',
      indicatorClass: 'bg-secondary animate-pulse',
      bio: 'Architected the Aura calculation engine, Discord-style leveling tiers, streak multipliers, and local storage state persistence.',
      skills: ['JavaScript', 'State Management', 'Gamification', 'CSS Grid'],
      socials: [
        { icon: 'code', label: 'GitHub', url: 'https://github.com' },
        { icon: 'groups', label: 'LinkedIn', url: 'https://linkedin.com' },
        { icon: 'share', label: 'Twitter', url: 'https://twitter.com' },
      ],
    },
    {
      name: 'Marcus Vance',
      role: 'Component Architect & QA',
      badge: 'Component Wizard',
      status: 'Systems & QA',
      level: 19,
      avatar:
        'https://lh3.googleusercontent.com/aida-public/AB6AXuBKricJ7OiRr4WK7fqIAs74_m9wJhxY8qgRReixhSOCl2FsHBQnh8paCwtNeIOZmBmXrdSGMiYK27Wqy8tMIcpe9WH6iKN5C5NwDCKjmWlWfhOm-G0mEhgz1Y9-O9Zsj4Z5jAhJDhWQr6Ac8HUidLTn4amu56p4fbvl0MDL58mbp0xRki_-13AG2zSQG_4ew6hpxHnJgPgHn4pkFbuy7uPKN5dVPRXQ03SsPypBD9s1cO8mJTNX-BQ',
      glow: 'from-primary-fixed to-primary-container',
      icon: 'extension',
      statusClass: 'bg-tertiary-container/15 text-tertiary',
      indicatorClass: 'bg-tertiary',
      bio: 'Designed reusable card components, accessibility standards, responsive breakpoints, and authentication mock workflows.',
      skills: ['React Router', 'CSS Modules', 'Testing', 'Accessibility'],
      socials: [
        { icon: 'code', label: 'GitHub', url: 'https://github.com' },
        { icon: 'groups', label: 'LinkedIn', url: 'https://linkedin.com' },
        { icon: 'forum', label: 'Discord', url: 'https://discord.com' },
      ],
    },
  ];

  return (
    <div className="w-full">
      {/* Dynamic Backdrop Glow Accents */}
      <div className="relative w-full overflow-hidden">
        <div className="absolute -top-32 left-1/4 w-96 h-96 bg-primary-container/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-48 right-10 w-80 h-80 bg-secondary/10 rounded-full blur-3xl pointer-events-none" />

        {/* Editorial Header Section */}
        <div className="w-full max-w-7xl mx-auto px-4 lg:px-6 pt-8 pb-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div className="space-y-2 max-w-2xl">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-high text-secondary font-['JetBrains_Mono'] text-xs uppercase tracking-wider shadow-sm">
                <span className="material-symbols-outlined text-[15px] text-secondary animate-pulse">terminal</span>
                CORE DEV SQUAD • CS302 CAPSTONE
              </div>
              <h1 className="font-['Plus_Jakarta_Sans'] font-extrabold text-3xl sm:text-4xl text-on-surface tracking-tight">
                Meet the{' '}
                <span className="bg-gradient-to-r from-primary via-primary-container to-secondary bg-clip-text text-transparent">
                  Creators
                </span>
              </h1>
              <p className="font-['Inter'] text-sm sm:text-base text-on-surface-variant leading-relaxed">
                The student developers and designers behind the AuraMeme React project. Building high-cadence internet culture interfaces for the modern web.
              </p>
            </div>

            {/* Metric counters */}
            <div className="flex items-center gap-4 shrink-0 bg-surface-container-low p-2 rounded-xl shadow-md border border-surface-container-highest/30">
              <div className="px-3 py-1 text-center">
                <div className="font-['Plus_Jakarta_Sans'] font-bold text-base text-primary">14.2k</div>
                <div className="font-['Inter'] text-[11px] text-outline uppercase tracking-wider">Aura Forged</div>
              </div>
              <div className="w-px h-8 bg-surface-container-highest" />
              <div className="px-3 py-1 text-center">
                <div className="font-['Plus_Jakarta_Sans'] font-bold text-base text-secondary">128+</div>
                <div className="font-['Inter'] text-[11px] text-outline uppercase tracking-wider">Commits</div>
              </div>
              <div className="w-px h-8 bg-surface-container-highest" />
              <div className="px-3 py-1 text-center">
                <div className="font-['Plus_Jakarta_Sans'] font-bold text-base text-tertiary">3 Tiers</div>
                <div className="font-['Inter'] text-[11px] text-outline uppercase tracking-wider">Game Logic</div>
              </div>
            </div>
          </div>
        </div>

        {/* Team Cards Grid */}
        <div className="w-full max-w-7xl mx-auto px-4 lg:px-6 py-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {teamMembers.map((member) => (
              <div
                key={member.name}
                className="group relative flex flex-col justify-between rounded-xl bg-surface-container-low p-6 transition-all duration-300 hover:-translate-y-1.5 shadow-xl hover:shadow-[0_8px_30px_rgba(160,120,255,0.18)] border border-surface-container-highest/30"
              >
                <div>
                  {/* Top Status & Aura Badge */}
                  <div className="flex items-center justify-between mb-6">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-['JetBrains_Mono'] text-xs ${member.statusClass}`}
                    >
                      <span className={`w-2 h-2 rounded-full ${member.indicatorClass}`} />
                      {member.status}
                    </span>
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-surface-container-high text-secondary font-['Inter'] text-xs font-bold shadow-sm">
                      <span className="material-symbols-outlined text-[13px] text-secondary">bolt</span>
                      ⚡ Level {member.level}
                    </span>
                  </div>

                  {/* Avatar with Ring Glow */}
                  <div className="relative w-28 h-28 mx-auto mb-4">
                    <div
                      className={`absolute -inset-1 rounded-full bg-gradient-to-r ${member.glow} opacity-70 blur-md group-hover:opacity-100 transition-opacity`}
                    />
                    <img
                      className="relative w-full h-full object-cover rounded-full shadow-md border-2 border-surface-container-lowest"
                      src={member.avatar}
                      alt={member.name}
                    />
                    <span
                      className="absolute bottom-1 right-1 w-6 h-6 rounded-full bg-surface-container-lowest flex items-center justify-center text-primary shadow-sm"
                      title={member.badge}
                    >
                      <span className="material-symbols-outlined text-[14px]">{member.icon}</span>
                    </span>
                  </div>

                  {/* Identity & Role */}
                  <div className="text-center space-y-1">
                    <h3 className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-on-surface group-hover:text-primary transition-colors">
                      {member.name}
                    </h3>
                    <p className="font-['Inter'] font-semibold text-xs text-secondary">{member.role}</p>
                    <div className="inline-block px-2.5 py-0.5 rounded bg-surface-container text-on-surface-variant font-['Inter'] text-[11px] font-semibold tracking-wide uppercase">
                      {member.badge}
                    </div>
                  </div>

                  {/* Bio */}
                  <p className="mt-4 font-['Inter'] text-xs text-on-surface-variant text-center leading-relaxed">
                    {member.bio}
                  </p>

                  {/* Skill Tags */}
                  <div className="mt-6 flex flex-wrap items-center justify-center gap-1.5">
                    {member.skills.map((skill) => (
                      <span
                        key={skill}
                        className="px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface font-['JetBrains_Mono'] text-xs hover:bg-primary-container hover:text-on-primary transition-colors cursor-default"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Social Links Footer */}
                <div className="mt-8 pt-3 border-0 bg-surface-container/60 -mx-6 -mb-6 px-6 py-3 rounded-b-xl flex items-center justify-between border-t border-surface-container-highest/20">
                  <span className="font-['Inter'] text-[11px] font-bold text-outline uppercase tracking-wider">
                    Connect
                  </span>
                  <div className="flex items-center gap-1.5">
                    {member.socials.map((s, idx) => (
                      <a
                        key={idx}
                        href={s.url}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={s.label}
                        className="w-8 h-8 rounded-lg bg-surface-container-high text-on-surface hover:text-primary hover:bg-surface-bright flex items-center justify-center transition-all shadow-sm cursor-pointer"
                      >
                        <span className="material-symbols-outlined text-[17px]">{s.icon}</span>
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* University Project Overview Bento Panel */}
        <div className="w-full max-w-7xl mx-auto px-4 lg:px-6 py-8">
          <div className="relative overflow-hidden rounded-xl bg-surface-container-low p-6 md:p-8 shadow-xl border border-surface-container-highest/30">
            <div className="absolute -right-16 -bottom-16 w-64 h-64 bg-primary-container/10 rounded-full blur-2xl pointer-events-none" />
            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Text and Meta */}
              <div className="lg:col-span-8 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full bg-surface-container-highest text-primary font-['JetBrains_Mono'] text-xs">
                    ACADEMIC SUBMISSION
                  </span>
                  <span className="text-outline">•</span>
                  <span className="text-on-surface-variant font-['JetBrains_Mono'] text-xs">
                    Spring 2025 Release
                  </span>
                </div>
                <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-2xl text-on-surface">
                  University Project Overview
                </h2>
                <p className="font-['Inter'] text-xs sm:text-sm text-on-surface-variant max-w-3xl leading-relaxed">
                  AuraMeme is built for <strong className="text-on-surface font-semibold">CS302 Web Development</strong> under the guidance of faculty advisor{' '}
                  <strong className="text-on-surface font-semibold">Dr. Evelyn Harper</strong>. Designed as a real-time responsive Single Page Application showcasing modern component architectures, reactive state coordination, and gamified social interaction patterns.
                </p>
                {/* Specification Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <div className="font-['Inter'] text-[11px] text-outline uppercase font-semibold">Course</div>
                    <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface">CS302</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <div className="font-['Inter'] text-[11px] text-outline uppercase font-semibold">Semester</div>
                    <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-secondary">Spring &apos;25</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <div className="font-['Inter'] text-[11px] text-outline uppercase font-semibold">Advisor</div>
                    <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface truncate">Dr. E. Harper</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-surface-container border border-surface-container-highest/20">
                    <div className="font-['Inter'] text-[11px] text-outline uppercase font-semibold">Status</div>
                    <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-primary">Final Stage</div>
                  </div>
                </div>
              </div>

              {/* Actions / GitHub Repo Block */}
              <div className="lg:col-span-4 flex flex-col sm:flex-row lg:flex-col items-stretch lg:items-end gap-3 justify-center">
                <a
                  href="https://github.com/lebaokhang123/aura_meme"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-primary-container via-inverse-primary to-primary text-on-primary font-['Plus_Jakarta_Sans'] font-bold text-sm shadow-[0_0_20px_rgba(160,120,255,0.4)] hover:shadow-[0_0_28px_rgba(160,120,255,0.6)] hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[20px]">code</span>
                  <span>View Source on GitHub</span>
                </a>
                <div className="flex items-center justify-center gap-3 font-['JetBrains_Mono'] text-xs text-outline">
                  <span className="inline-flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px] text-secondary">verified</span> MIT Licensed
                  </span>
                  <span>•</span>
                  <span className="inline-flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px] text-primary">star</span> 34 Stars
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Easter Egg / Community Aura Score Bar */}
        <div className="w-full max-w-7xl mx-auto px-4 lg:px-6 pb-8">
          <div className="p-4 rounded-xl bg-surface-container flex flex-col md:flex-row items-center justify-between gap-4 border border-surface-container-highest/30">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center text-primary shrink-0">
                <span className="material-symbols-outlined text-[22px]">military_tech</span>
              </div>
              <div>
                <div className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface">Community Team Aura Total</div>
                <div className="font-['Inter'] text-xs text-on-surface-variant">Combined student creator score for this academic semester</div>
              </div>
            </div>

            <div className="flex items-center gap-4 w-full md:w-auto">
              <div className="flex-1 md:w-48">
                <div className="flex justify-between font-['JetBrains_Mono'] text-xs mb-1">
                  <span className="text-secondary">Progress</span>
                  <span className="text-on-surface">88% to Tier 8</span>
                </div>
                <div className="h-2 w-full bg-surface-container-high rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-primary to-secondary rounded-full" style={{ width: '88%' }} />
                </div>
              </div>
              <button
                onClick={handleBoost}
                className={`shrink-0 px-3.5 py-2 rounded-lg font-['Inter'] font-semibold text-xs flex items-center gap-1 transition-all active:scale-95 cursor-pointer ${
                  boostEffect
                    ? 'bg-secondary text-on-secondary scale-105'
                    : 'bg-surface-container-high hover:bg-surface-bright text-secondary'
                }`}
                type="button"
              >
                <span className="material-symbols-outlined text-[16px]">volunteer_activism</span>
                <span>+{communityTeamAura} Boost Team</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
