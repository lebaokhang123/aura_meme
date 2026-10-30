import type { DemoPost } from '../types';

// Presentation fixtures only; never a session, wallet or reward source.
export const demoPosts: DemoPost[] = [
  {
    id: 'post_1',
    author: {
      username: 'u/SyntaxSamurai',
      initials: 'SS',
      avatarBg: 'bg-primary-container text-on-primary-fixed',
    },
    title: 'When your code compiles on the first try with zero warnings and zero errors',
    imageUrl: '/assets/illustrations/meme-1.svg',
    imageAlt: 'Original illustration of a neon explorer rising through a glowing code portal',
    captionBadge: 'Exit Code 0: Godmode Activated',
    category: 'Gaming',
    reactions: {
      like: 342,
      laugh: 1200,
      fire: 890,
    },
    commentsCount: 284,
  },
  {
    id: 'post_2',
    author: {
      username: 'u/CyberNeko',
      initials: 'CN',
      avatarBg: 'bg-secondary-container text-on-secondary',
    },
    title: 'Me promising myself I will finish the React project three weeks before the exam week',
    imageUrl: '/assets/illustrations/meme-2.svg',
    imageAlt: 'Original illustration of a sleepy desk robot surrounded by monitors at night',
    captionBadge: "Git Commit: 'please work final_v4_FINAL.tsx'",
    category: 'School',
    reactions: {
      like: 512,
      laugh: 2400,
      fire: 430,
    },
    commentsCount: 419,
  },
  {
    id: 'post_3',
    author: {
      username: 'u/DevDoge',
      initials: 'DD',
      avatarBg: 'bg-gradient-to-tr from-amber-500 to-primary text-surface-container-lowest',
    },
    title: 'CSS in real life: centering a div vs fixing a flexbox overflow bug at 3 AM',
    imageUrl: '/assets/illustrations/meme-3.svg',
    imageAlt: 'Original illustration of a centered cube beside tangled neon layout panels',
    captionBadge: 'display: flex; justify-content: chaos;',
    category: 'Technology',
    reactions: {
      like: 1800,
      laugh: 3900,
      fire: 940,
    },
    commentsCount: 573,
  },
];
