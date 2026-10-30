import { Link } from 'react-router-dom';

export function AboutPage() {
  return (
    <div className="about-page w-full">
      <section className="about-intro relative isolate overflow-hidden">
        <div
          aria-hidden="true"
          className="absolute -top-20 right-1/4 w-96 h-96 bg-secondary/10 blur-3xl rounded-full -z-10"
        />
        <div className="max-w-7xl mx-auto px-4 lg:px-6 py-8 sm:py-12">
          <div className="max-w-2xl">
            <span className="inline-flex px-3 py-1.5 rounded-full bg-surface-container-high text-secondary text-[10px] font-mono tracking-wider">
              MEMES / COMMUNITY / PERSONALITY
            </span>
            <h1 className="font-['Plus_Jakarta_Sans'] text-3xl sm:text-4xl font-extrabold mt-4">
              About{' '}
              <span className="bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                AuraMeme
              </span>
            </h1>
            <p className="text-sm sm:text-base text-on-surface-variant leading-relaxed mt-3">
              A meme blog built around good conversations and a little extra identity. A familiar feed,
              expressive profiles, and a community worth coming back to.
            </p>
          </div>
          <div className="community-art relative h-64 sm:h-96 md:h-[420px] rounded-xl overflow-hidden shadow-xl mt-8 border border-surface-container-highest/40 bg-surface-container-lowest">
            <img
              src="/assets/illustrations/community.svg"
              alt="Original illustration of a neon creative lounge with anonymous characters, not team portraits"
              className="w-full h-full object-cover"
            />
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-surface-container-lowest p-6">
              <p className="font-mono text-xs text-secondary">A place for internet artifacts.</p>
            </div>
          </div>
          <div className="mt-10">
            <h2 className="font-['Plus_Jakarta_Sans'] text-2xl font-bold">Our direction</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-5">
              {[
                {
                  icon: 'forum',
                  title: 'Start with the conversation',
                  text: 'Posts, categories and comments form the foundation of the community.',
                },
                {
                  icon: 'auto_awesome',
                  title: 'Make it feel like you',
                  text: 'Aura and collectible cosmetics are planned additions after the core blog.',
                },
                {
                  icon: 'code',
                  title: 'Build it step by step',
                  text: 'This frontend is a local preview. Accounts and community services are still to come.',
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="direction-card surface-panel rounded-xl bg-surface-container-low border border-surface-container-highest/30 p-6"
                >
                  <span aria-hidden="true" className="material-symbols-outlined text-secondary text-3xl">
                    {item.icon}
                  </span>
                  <h3 className="font-bold text-sm mt-4">{item.title}</h3>
                  <p className="text-xs leading-relaxed text-on-surface-variant mt-2">{item.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
      <section id="team" tabIndex={-1} className="max-w-7xl w-full mx-auto px-4 lg:px-6 pb-12 scroll-mt-24">
        <span className="text-xs text-secondary font-mono">THE PEOPLE BEHIND AURAMEME</span>
        <h2 className="font-['Plus_Jakarta_Sans'] text-2xl sm:text-3xl font-extrabold mt-2">Meet the team</h2>
        <p className="text-sm text-on-surface-variant mt-3">
          Two project members, one shared space for memes.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mt-6">
          {[
            { name: 'Lê Bảo Khang', initials: 'KH', glow: 'from-primary to-primary-container' },
            { name: 'Phan Trung Kiên', initials: 'KI', glow: 'from-secondary to-secondary-container' },
          ].map((member) => (
            <article
              key={member.name}
              className="team-card relative overflow-hidden bg-surface-container-low border border-surface-container-highest/30 p-8 rounded-xl shadow-xl text-center group"
            >
              <span className="inline-block text-[10px] rounded-full bg-primary/10 px-3 py-1.5 text-primary font-mono">
                PROJECT MEMBER
              </span>
              <div className="relative w-28 h-28 mx-auto mt-8">
                <div
                  aria-hidden="true"
                  className={`absolute inset-0 rounded-full bg-gradient-to-tr ${member.glow} opacity-30 blur-xl group-hover:opacity-50 transition-opacity`}
                />
                <div
                  className={`relative w-full h-full rounded-full grid place-items-center bg-gradient-to-br ${member.glow} text-on-primary font-['Plus_Jakarta_Sans'] text-3xl font-extrabold border-4 border-surface-container`}
                >
                  {member.initials}
                </div>
              </div>
              <h3 className="font-['Plus_Jakarta_Sans'] text-xl font-bold mt-6">{member.name}</h3>
              <p className="text-xs text-on-surface-variant mt-2">AuraMeme · Website blog project</p>
            </article>
          ))}
        </div>
        <div className="flex flex-wrap gap-4 mt-8">
          <a
            href="https://github.com/lebaokhang123/aura_meme"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-3 rounded-lg bg-surface-container text-primary text-sm"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
              code
            </span>
            Project repository<span className="sr-only">(opens in a new tab)</span>
          </a>
          <Link to="/contact" className="inline-flex items-center gap-2 px-4 py-3 text-sm text-secondary">
            Contact preview
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
              arrow_forward
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
