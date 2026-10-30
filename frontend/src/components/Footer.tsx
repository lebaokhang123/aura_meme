import { Link } from 'react-router-dom';

export function Footer() {
  return (
    <footer className="w-full bg-[#0d0e15] border-t border-[#292932]/50 mt-auto">
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 pb-8">
          <div className="lg:col-span-2 flex flex-col gap-3 items-start">
            <Link to="/" className="flex items-center gap-2">
              <img alt="" className="h-8 w-8 rounded-lg" src="/assets/illustrations/brand-placeholder.svg" />
              <span className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-primary">AuraMeme</span>
            </Link>
            <p className="text-xs text-on-surface-variant max-w-sm leading-relaxed">
              A home for memes, conversations and a little more personality. Explore the interface while our
              community features take shape.
            </p>
            <span className="text-xs font-mono px-3 py-1.5 rounded-full bg-surface-container text-secondary">
              Community frontend preview
            </span>
          </div>
          <div>
            <h2 className="text-xs uppercase font-semibold tracking-wider mb-3">Explore</h2>
            <nav
              aria-label="Footer navigation"
              className="flex flex-col gap-3 text-xs text-on-surface-variant"
            >
              <Link to="/">Home</Link>
              <Link to="/explore">Explore memes</Link>
              <Link to="/about">About AuraMeme</Link>
              <Link to="/about#team">Meet the team</Link>
            </nav>
          </div>
          <div>
            <h2 className="text-xs uppercase font-semibold tracking-wider mb-3">Connect</h2>
            <nav aria-label="Community links" className="flex flex-col gap-3 text-xs text-on-surface-variant">
              <Link to="/contact">Contact preview</Link>
              <a href="https://github.com/lebaokhang123/aura_meme" target="_blank" rel="noreferrer">
                GitHub repository <span className="sr-only">(opens in a new tab)</span>
              </a>
              <Link to="/login">Login preview</Link>
              <Link to="/register">Registration preview</Link>
            </nav>
          </div>
        </div>
        <div className="border-t border-surface-container-highest/40 pt-6 flex flex-col sm:flex-row justify-between gap-3 text-xs text-outline">
          <span>AuraMeme · Khang & Kiên</span>
          <span>No live accounts, rewards or payments in this preview.</span>
        </div>
      </div>
    </footer>
  );
}
