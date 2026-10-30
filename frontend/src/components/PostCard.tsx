import { useUI } from '../context/UIContext';
import { formatAuraNumber } from '../utils/format';
import type { DemoPost } from '../types';

export function PostCard({ post }: { post: DemoPost }) {
  const { showToast, setSelectedCategory } = useUI();
  return (
    <article className="meme-card bg-surface-container-low rounded-xl p-5 shadow-md border border-surface-container-highest/30 transition-all duration-200 hover:shadow-xl hover:border-surface-container-highest/60 min-w-0">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className={`creator-avatar w-10 h-10 rounded-full grid place-items-center shrink-0 font-bold text-sm ${post.author.avatarBg}`}
          >
            {post.author.initials}
          </div>
          <div className="min-w-0">
            <span className="font-['Plus_Jakarta_Sans'] font-bold text-sm break-words">
              {post.author.username}
            </span>
            <div className="flex flex-wrap gap-1.5 text-xs text-outline mt-1">
              <button
                type="button"
                onClick={() => setSelectedCategory(post.category)}
                className="text-secondary hover:underline"
              >
                #{post.category}
              </button>
              <span>· Sample creator</span>
            </div>
          </div>
        </div>
        <span className="demo-tag text-[10px] text-primary bg-primary/10 rounded-full px-2 py-1 shrink-0">
          DEMO
        </span>
      </div>
      <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-lg leading-snug mb-3">{post.title}</h2>
      <div className="post-media relative aspect-[4/3] rounded-lg overflow-hidden bg-surface-container-lowest mb-4">
        <img
          src={post.imageUrl}
          alt={post.imageAlt ?? 'Abstract demo illustration'}
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-surface-container-lowest to-transparent">
          <span className="text-xs font-mono text-secondary">{post.captionBadge}</span>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1.5 flex-wrap">
          {(['like', 'laugh', 'fire'] as const).map((reaction, index) => (
            <button
              key={reaction}
              type="button"
              aria-label={`${reaction} preview; ${post.reactions[reaction]} sample reactions`}
              onClick={() => showToast('Reactions are a preview only. No reaction or Aura was recorded.')}
              className="min-h-11 px-3 rounded-full bg-surface-container hover:bg-surface-container-high text-xs transition-colors active:scale-95"
            >
              <span aria-hidden="true">{['👍', '🤣', '🔥'][index]}</span>{' '}
              <span className="font-mono">{formatAuraNumber(post.reactions[reaction], true)}</span>
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Comments preview"
            onClick={() => showToast('Comments are not connected yet. Nothing was posted.')}
            className="min-h-11 px-3 rounded-lg bg-surface-container text-xs text-on-surface-variant"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[16px] align-middle mr-1">
              chat_bubble
            </span>
            {post.commentsCount}
          </button>
          <button
            type="button"
            aria-label="Bookmark preview"
            onClick={() => showToast('Bookmarks are a preview only. No bookmark was saved.')}
            className="w-11 h-11 grid place-items-center rounded-lg bg-surface-container text-outline hover:text-primary"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[18px]">
              bookmark
            </span>
          </button>
        </div>
      </div>
      <p className="text-[10px] text-outline mt-3">Sample counts · original illustration</p>
    </article>
  );
}
