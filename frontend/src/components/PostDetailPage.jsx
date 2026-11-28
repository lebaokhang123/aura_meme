import React, { useEffect, useState } from 'react';
import { auth, MOCK_AUTH } from '../auth.js';
import { useLocalized } from '../localize.jsx';
import { usePreferences } from '../PreferencesContext.jsx';
import { useSocial } from '../SocialContext.jsx';
import { apiId, apiPost } from '../social-api.js';
import ErrorPage from './ErrorPage.jsx';
import { PostCard } from './PostCard.jsx';
import { icon } from './social-ui.jsx';

export default function PostDetailPage() {
  const render = useLocalized();
  const { language } = usePreferences();
  const t = (vi, en) => (language === 'en' ? en : vi);
  const { readInteraction, injectComment, injectPost, posts } = useSocial();

  const match = /^\/posts\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i.exec(location.pathname);
  const postId = match?.[1] || null;
  const commentParam = new URLSearchParams(location.search).get('comment');

  const [postLoaded, setPostLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [errorStatus, setErrorStatus] = useState(null);
  const [locate, setLocate] = useState(null);
  const [commentUnavailable, setCommentUnavailable] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!postId || MOCK_AUTH) {
      setErrorStatus(404);
      setLoading(false);
      return;
    }
    let active = true;
    setPostLoaded(false);
    setLoading(true);
    setErrorStatus(null);
    setCommentUnavailable(false);
    setLocate(null);

    Promise.all([
      auth.read('/posts/' + apiId(postId)),
      readInteraction('post', postId),
    ])
      .then(async ([rawPost]) => {
        if (!active) return;
        const mapped = apiPost(rawPost);
        injectPost(mapped);
        setPostLoaded(true);
        if (commentParam && /^[0-9a-f-]{36}$/i.test(commentParam)) {
          try {
            const loc = await auth.read(`/posts/${apiId(postId)}/comments/${apiId(commentParam)}/locate`);
            if (active) {
              if (loc?.root_comment) injectComment(loc.root_comment);
              if (loc?.target_comment) injectComment(loc.target_comment);
              setLocate(loc);
            }
          } catch (e) {
            if (active && e.status === 404) setCommentUnavailable(true);
          }
        }
      })
      .catch((err) => {
        if (!active) return;
        setErrorStatus(err?.status === 404 ? 404 : 503);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [postId, commentParam, revision]);

  const post = posts.find(p => p.id === postId) || null;
  // Keep local post synced if edited or deleted via SocialContext
  const deletedInSession = postLoaded && !loading && !errorStatus && !post;

  if (errorStatus === 404 || deletedInSession) return <ErrorPage status={404} />;
  if (errorStatus) return <ErrorPage status={503} onRetry={() => setRevision(n => n + 1)} />;

  return render(
    <main className="max-w-3xl mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface text-sm font-medium border border-outline-variant/50"
          onClick={() => {
            if (history.length > 1) history.back();
            else location.assign('/');
          }}
        >
          {icon('arrow_back', 18)}
          <span>{t('Quay lại', 'Back')}</span>
        </button>
      </div>

      {commentUnavailable && (
        <div role="status" className="p-3 rounded-xl bg-surface-container-high border border-outline-variant text-sm text-on-surface-variant">
          {t('Bình luận hoặc phản hồi được liên kết không còn khả dụng.', 'The linked comment or reply is no longer available.')}
        </div>
      )}

      {loading || !post ? (
        <div className="p-8 rounded-xl bg-surface-container-low text-center text-sm text-outline" role="status">
          {t('Đang tải bài viết...', 'Loading post...')}
        </div>
      ) : (
        <PostCard
          post={post}
          detail
          highlightCommentId={locate?.comment_id || null}
          expandRootId={locate?.is_reply ? locate.root_comment_id : null}
        />
      )}
    </main>
  );
}
