import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { auth, MOCK_AUTH } from '../auth.js';
import { useLocalized } from '../localize.jsx';
import { usePreferences } from '../PreferencesContext.jsx';
import { REACTIONS } from '../social-model.js';
import { apiAuthor, apiId, apiPage, vaultAsset } from '../social-api.js';
import { icon } from './social-ui.jsx';
import UserAvatar from './UserAvatar.jsx';
import { LevelPill, TitleBadge } from './RealmBadges.jsx';

const REACTION_MAP = Object.fromEntries(REACTIONS.map(r => [r.id, r]));

export function ReactionDetailsModal({
  target = 'post',
  id,
  initialType = 'all',
  initialMemeId = null,
  onClose,
}) {
  const render = useLocalized();
  const { language } = usePreferences();
  const t = (vi, en) => (language === 'en' ? en : vi);

  const [tab, setTab] = useState(initialType || 'all');
  const [memeId, setMemeId] = useState(initialMemeId || null);
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [counts, setCounts] = useState(null);
  const [memeSummary, setMemeSummary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);

  const modalRef = useRef(null);
  const closeBtnRef = useRef(null);
  const generationRef = useRef(0);

  useEffect(() => {
    const prevFocus = document.activeElement;
    closeBtnRef.current?.focus({ preventScroll: true });
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      if (prevFocus && typeof prevFocus.focus === 'function') {
        prevFocus.focus();
      }
    };
  }, [onClose]);

  const fetchPage = async (nextPage = 1, append = false) => {
    if (MOCK_AUTH) {
      setItems([]);
      setPagination({ page: 1, page_size: 20, total: 0, total_pages: 0 });
      setLoading(false);
      return;
    }
    const token = ++generationRef.current;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ page: String(nextPage), page_size: '20' });
      if (tab !== 'all') params.set('reaction_type', tab);
      if (tab === 'meme' && memeId) params.set('meme_asset_id', apiId(memeId));
      const base = target === 'post' ? 'posts' : 'comments';
      const raw = await auth.read(`/${base}/${apiId(id)}/reactions?${params}`);
      if (token !== generationRef.current) return;
      const pageData = apiPage(raw);
      const mapped = pageData.items.map(row => ({
        user: apiAuthor(row.user),
        reactionType: row.reaction_type,
        memeAsset: row.meme_asset ? vaultAsset(row.meme_asset) : null,
        updatedAt: row.updated_at,
      }));
      setItems(prev => (append ? [...prev, ...mapped] : mapped));
      setPagination(pageData.pagination);
      if (raw.reaction_counts) setCounts(raw.reaction_counts);
      if (Array.isArray(raw.meme_reactions)) {
        setMemeSummary(
          raw.meme_reactions.map(m => ({ asset: vaultAsset(m.asset), count: m.count }))
        );
      }
    } catch (err) {
      if (token !== generationRef.current) return;
      setError(err?.message || t('Không tải được danh sách biểu cảm.', 'Failed to load reactions.'));
    } finally {
      if (token === generationRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    void fetchPage(1, false);
    return () => {
      generationRef.current++;
    };
  }, [target, id, tab, memeId, revision]);

  const totalStd = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  const totalMeme = memeSummary.reduce((a, b) => a + b.count, 0);
  const totalAll = totalStd + totalMeme;

  return createPortal(
    render(
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) onClose?.();
        }}
      >
        <div
          ref={modalRef}
          role="dialog"
          aria-modal="true"
          aria-label={t('Biểu cảm', 'Reactions')}
          className="w-full max-w-md max-h-[82vh] flex flex-col rounded-2xl bg-surface-container border border-outline-variant shadow-2xl text-on-surface overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-outline-variant/60">
            <h3 className="font-title-md text-title-md font-bold">
              {t('Biểu cảm', 'Reactions')}
            </h3>
            <button
              ref={closeBtnRef}
              type="button"
              className="p-1.5 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container-high"
              aria-label={t('Đóng', 'Close')}
              onClick={onClose}
            >
              {icon('close', 20)}
            </button>
          </div>

          <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-outline-variant/40 overflow-x-auto" role="tablist" aria-label={t('Lọc theo biểu cảm', 'Filter by reaction')}>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'all'}
              className={`px-3 py-1 rounded-full text-xs font-semibold shrink-0 border transition-colors ${
                tab === 'all'
                  ? 'bg-secondary-container text-on-secondary-container border-secondary/40'
                  : 'bg-surface-container-high text-on-surface-variant border-transparent hover:border-outline-variant'
              }`}
              onClick={() => { setTab('all'); setMemeId(null); }}
            >
              {t('Tất cả', 'All')}{counts ? ` (${totalAll})` : ''}
            </button>
            {REACTIONS.map(r => {
              const c = counts?.[r.id] || 0;
              if (c === 0 && tab !== r.id) return null;
              return (
                <button
                  key={r.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === r.id}
                  className={`px-2.5 py-1 rounded-full text-xs font-semibold shrink-0 border transition-colors flex items-center gap-1 ${
                    tab === r.id
                      ? 'bg-secondary-container text-on-secondary-container border-secondary/40'
                      : 'bg-surface-container-high text-on-surface-variant border-transparent hover:border-outline-variant'
                  }`}
                  onClick={() => { setTab(r.id); setMemeId(null); }}
                >
                  <span>{r.emoji}</span>
                  <span>{c}</span>
                </button>
              );
            })}
            {(totalMeme > 0 || tab === 'meme') && (
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'meme'}
                className={`px-3 py-1 rounded-full text-xs font-semibold shrink-0 border transition-colors ${
                  tab === 'meme'
                    ? 'bg-secondary-container text-on-secondary-container border-secondary/40'
                    : 'bg-surface-container-high text-on-surface-variant border-transparent hover:border-outline-variant'
                }`}
                onClick={() => { setTab('meme'); setMemeId(null); }}
              >
                Meme ({totalMeme})
              </button>
            )}
          </div>

          {tab === 'meme' && memeSummary.length > 0 && (
            <div className="flex items-center gap-1.5 px-4 py-2 border-b border-outline-variant/30 overflow-x-auto bg-surface-container-low/60">
              <button
                type="button"
                className={`px-2.5 py-1 rounded-full text-xs shrink-0 border ${
                  !memeId
                    ? 'bg-secondary/20 text-secondary border-secondary/40 font-semibold'
                    : 'bg-surface-container text-on-surface-variant border-outline-variant/40'
                }`}
                onClick={() => setMemeId(null)}
              >
                {t('Mọi Meme', 'All Memes')}
              </button>
              {memeSummary.map(({ asset, count }) => (
                <button
                  key={asset.id}
                  type="button"
                  data-meme-filter={asset.id}
                  className={`px-2 py-1 rounded-full text-xs shrink-0 border flex items-center gap-1 ${
                    memeId === asset.id
                      ? 'bg-secondary/20 text-secondary border-secondary/40 font-semibold'
                      : 'bg-surface-container text-on-surface-variant border-outline-variant/40'
                  }`}
                  onClick={() => setMemeId(asset.id)}
                >
                  <img src={asset.image} alt="" className="w-4 h-4 rounded-full object-cover" />
                  <span className="max-w-[90px] truncate">{asset.display_name}</span>
                  <span>({count})</span>
                </button>
              ))}
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
            {loading && items.length === 0 ? (
              <div className="py-8 text-center text-sm text-outline" role="status">
                {t('Đang tải danh sách biểu cảm...', 'Loading reactions...')}
              </div>
            ) : error ? (
              <div className="py-6 text-center space-y-2" role="alert">
                <p className="text-sm text-error">{error}</p>
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg bg-secondary-container text-on-secondary-container text-xs font-semibold"
                  onClick={() => setRevision(n => n + 1)}
                >
                  {t('Thử lại', 'Retry')}
                </button>
              </div>
            ) : items.length === 0 ? (
              <div className="py-8 text-center text-sm text-outline">
                {t('Chưa có biểu cảm nào phù hợp.', 'No matching reactions yet.')}
              </div>
            ) : (
              <>
                {items.map(row => {
                  const profileHref = `/u/${encodeURIComponent(row.user.author)}`;
                  const std = REACTION_MAP[row.reactionType];
                  return (
                    <div
                      key={`${row.user.authorId}-${row.reactionType}-${row.memeAsset?.id || ''}`}
                      className="flex items-center justify-between gap-3 p-2 rounded-xl hover:bg-surface-container-high/70 transition-colors"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <a href={profileHref} className="shrink-0 rounded-full">
                          <UserAvatar
                            src={row.user.avatar}
                            alt={row.user.authorName}
                            tier={row.user.membershipTier}
                            size="sm"
                          />
                        </a>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <a href={profileHref} translate="no" className="text-sm font-bold text-on-surface hover:underline truncate">
                              {row.user.authorName}
                            </a>
                            <LevelPill level={row.user.level} size="sm" />
                            <TitleBadge level={row.user.level} realm={row.user.realm} title={row.user.nickname} size="sm" />
                          </div>
                          <a href={profileHref} translate="no" className="text-xs text-outline hover:underline block truncate">
                            {row.user.handle}
                          </a>
                        </div>
                      </div>
                      <div className="shrink-0 flex items-center" title={row.memeAsset?.display_name || std?.label || row.reactionType}>
                        {row.reactionType === 'meme' && row.memeAsset ? (
                          <img
                            src={row.memeAsset.image}
                            alt={row.memeAsset.display_name}
                            className="w-6 h-6 rounded-full object-cover border border-outline-variant"
                          />
                        ) : (
                          <span className="text-lg">{std?.emoji || row.reactionType}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
                {pagination && pagination.page < pagination.total_pages && (
                  <div className="pt-2 text-center">
                    <button
                      type="button"
                      disabled={loading}
                      className="px-4 py-1.5 rounded-lg bg-surface-container-high hover:bg-surface-container-highest text-secondary text-xs font-semibold"
                      onClick={() => fetchPage(pagination.page + 1, true)}
                    >
                      {loading ? t('Đang tải...', 'Loading...') : t('Xem thêm', 'Load more')}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    ),
    document.getElementById('root')
  );
}
