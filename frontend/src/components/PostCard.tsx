import { Link } from 'react-router-dom';
import type { Post } from '../blog';

export function PostCard({ post }: { post: Post }) {
  return <article className="meme-card bg-surface-container-low rounded-xl p-5 shadow-md border border-surface-container-highest/30 transition-all duration-200 hover:shadow-xl hover:border-surface-container-highest/60 min-w-0">
    <div className="flex items-center gap-3 mb-3 min-w-0">
      <span aria-hidden="true" className="creator-avatar w-10 h-10 grid place-items-center rounded-full bg-primary/15 text-primary font-bold shrink-0">{post.author.display_name.slice(0, 2)}</span>
      <div className="min-w-0"><Link to={'/profile/' + post.author.username} className="font-bold text-sm break-words">{post.author.display_name}</Link>
        <p className="text-xs text-secondary mt-1"><Link to={'/explore?category=' + encodeURIComponent(post.category.slug)}>#{post.category.name}</Link></p></div>
    </div>
    <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-lg leading-snug mb-3 break-words"><Link to={'/posts/' + post.id}>{post.title}</Link></h2>
    <div className="post-media relative aspect-[4/3] rounded-lg overflow-hidden bg-surface-container-lowest mb-4">
      <img src="/assets/illustrations/meme-1.svg" alt="" className="w-full h-full object-cover" />
      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-surface-container-lowest to-surface-container-lowest/70 text-xs text-secondary">Decorative illustration · media display unavailable</div>
    </div>
    <p className="text-sm text-on-surface-variant whitespace-pre-wrap break-words line-clamp-4">{post.content}</p>
    <div className="mt-4 flex flex-wrap gap-2 items-center justify-between text-xs">
      <Link to={'/posts/' + post.id} className="min-h-11 inline-flex items-center px-3 rounded-lg bg-surface-container text-secondary">Read discussion</Link>
      <span className="text-outline">{new Date(post.created_at).toLocaleDateString()}</span>
    </div>
    <div className="mt-3 flex flex-wrap gap-2 text-xs text-outline">
      <button disabled className="min-h-11 px-3 rounded-full bg-surface-container opacity-60">👍 Reactions unavailable</button>
      <button disabled className="min-h-11 px-3 rounded-lg bg-surface-container opacity-60">Bookmark unavailable</button>
    </div>
  </article>;
}
