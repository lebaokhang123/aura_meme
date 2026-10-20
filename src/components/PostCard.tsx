import { useUI } from '../context/UIContext';
import { formatAuraNumber } from '../utils/format';
import type { MemePost } from '../types';

export function PostCard({ post }: { post: MemePost }) {
  const { toggleReaction, awardAuraToPost, toggleBookmark, showToast, setSelectedCategory } = useUI();
  return (
                <article

                  className="bg-surface-container-low rounded-xl p-5 shadow-md border border-surface-container-highest/30 transition-all duration-200 hover:shadow-xl hover:border-surface-container-highest/60"
                >
                  {/* Author Header */}
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="relative">
                        <div
                          className={`w-10 h-10 rounded-full flex items-center justify-center font-bold font-['Plus_Jakarta_Sans'] text-sm ${post.author.avatarBg}`}
                        >
                          {post.author.initials}
                        </div>
                        <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-secondary ring-2 ring-surface-container-low" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-['Plus_Jakarta_Sans'] font-bold text-sm text-on-surface hover:underline cursor-pointer">
                            {post.author.username}
                          </span>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-container/20 text-primary font-['Inter'] text-[10px] font-semibold">
                            <span className="material-symbols-outlined text-[12px]">bolt</span> Level {post.author.level} • {post.author.rankTitle}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 font-['Inter'] text-xs text-outline">
                          <button
                            onClick={() => setSelectedCategory(post.category)}
                            className="text-secondary font-medium hover:underline cursor-pointer"
                          >
                            #{post.category}
                          </button>
                          <span>•</span>
                          <span>{post.timeAgo}</span>
                        </div>
                      </div>
                    </div>
                    {/* Actions */}
                    <button
                      aria-label="Post options"
                      onClick={() => showToast(`Post options for ${post.id}`)}
                      className="p-1 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container transition-colors cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-[20px]">more_horiz</span>
                    </button>
                  </div>

                  {/* Post Title */}
                  <h2 className="font-['Plus_Jakarta_Sans'] font-bold text-lg text-on-surface mb-3 leading-snug">
                    {post.title}
                  </h2>

                  {/* Meme Media Box */}
                  <div className="relative w-full rounded-xl overflow-hidden bg-surface-container-lowest mb-3 flex flex-col items-center justify-center p-3 border border-surface-container-highest/20">
                    <div className="w-full max-w-xl aspect-[16/10] rounded-lg overflow-hidden relative shadow-lg bg-black">
                      <img
                        className="w-full h-full object-cover"
                        src={post.imageUrl}
                        alt={post.imageAlt || post.title}
                      />
                      {/* Caption Scrim */}
                      <div className="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-surface-container-lowest via-surface-container-lowest/80 to-transparent flex items-center justify-between">
                        <span className="font-['JetBrains_Mono'] text-xs text-secondary font-semibold">
                          {post.captionBadge || 'Exit Code 0: Godmode Activated'}
                        </span>
                        <span className="px-2 py-0.5 rounded bg-surface-container font-['JetBrains_Mono'] text-[10px] text-outline">
                          {post.buildMeta || '0.04s build'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Reactions Dock */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                    {/* Emoji Reaction buttons */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      <button
                        onClick={() => toggleReaction()}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full font-['Inter'] text-xs transition-all cursor-pointer active:scale-95 ${
                          post.userReactions.like
                            ? 'bg-surface-container-high text-primary ring-1 ring-primary/40'
                            : 'bg-surface-container hover:bg-surface-container-high text-on-surface'
                        }`}
                        type="button"
                      >
                        <span>👍</span>
                        <span className="font-['JetBrains_Mono']">{formatAuraNumber(post.reactions.like)}</span>
                      </button>

                      <button
                        onClick={() => toggleReaction()}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full font-['Inter'] text-xs transition-all cursor-pointer active:scale-95 ${
                          post.userReactions.laugh
                            ? 'bg-surface-container-high text-secondary ring-1 ring-secondary/40 shadow-[0_0_8px_rgba(76,215,246,0.2)]'
                            : 'bg-surface-container hover:bg-surface-container-high text-on-surface'
                        }`}
                        type="button"
                      >
                        <span>🤣</span>
                        <span className="font-['JetBrains_Mono'] font-semibold text-secondary">
                          {formatAuraNumber(post.reactions.laugh, true)}
                        </span>
                      </button>

                      <button
                        onClick={() => toggleReaction()}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full font-['Inter'] text-xs transition-all cursor-pointer active:scale-95 ${
                          post.userReactions.fire
                            ? 'bg-surface-container-high text-amber-400 ring-1 ring-amber-400/40'
                            : 'bg-surface-container hover:bg-surface-container-high text-on-surface'
                        }`}
                        type="button"
                      >
                        <span>🔥</span>
                        <span className="font-['JetBrains_Mono']">{formatAuraNumber(post.reactions.fire)}</span>
                      </button>

                      <button
                        onClick={() => toggleReaction()}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-full font-['Inter'] text-xs transition-all cursor-pointer active:scale-95 ${
                          post.userReactions.clown
                            ? 'bg-surface-container-high text-outline ring-1 ring-outline'
                            : 'bg-surface-container hover:bg-surface-container-high text-on-surface'
                        }`}
                        type="button"
                      >
                        <span>🤡</span>
                        <span className="font-['JetBrains_Mono'] text-outline">{post.reactions.clown}</span>
                      </button>
                    </div>

                    {/* Action Hub & Aura Award Button */}
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => showToast(`Opening ${post.commentsCount} comments...`)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface font-['Inter'] text-xs transition-colors cursor-pointer"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[16px]">chat_bubble</span>
                        <span>{post.commentsCount}</span>
                      </button>

                      <button
                        onClick={() => {
                          showToast('Share is a UI preview only.');
                        }}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface font-['Inter'] text-xs transition-colors cursor-pointer"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[16px]">share</span>
                        <span className="hidden sm:inline">Share</span>
                      </button>

                      <button
                        onClick={() => toggleBookmark()}
                        className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                          post.isBookmarked
                            ? 'bg-surface-container-high text-primary'
                            : 'bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface'
                        }`}
                        title="Bookmark" aria-label="Bookmark"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[16px]">bookmark</span>
                      </button>

                      <button
                        onClick={() => awardAuraToPost()}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gradient-to-r from-primary-container to-secondary-container text-on-primary font-['Inter'] font-semibold text-xs shadow-[0_0_12px_rgba(160,120,255,0.3)] hover:opacity-90 active:scale-95 transition-all cursor-pointer"
                        type="button"
                      >
                        <span className="material-symbols-outlined text-[15px]">stars</span>
                        <span>+50 Aura</span>
                      </button>
                    </div>
                  </div>
                </article>
  );
}
