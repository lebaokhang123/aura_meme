import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError, errorMessage } from '../api';
import type { Comment, Page, Post } from '../blog';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';
import { useResource } from '../hooks/useResource';
import { Pagination } from '../components/Pagination';

function Comments({ postId }: { postId: string }) {
  const { user, refresh } = useAuth();
  const { showToast } = useUI();
  const [page, setPage] = useState(1);
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const resource = useResource<Page<Comment>>('/posts/' + postId + '/comments?page=' + page + '&page_size=20');
  const fail = async (fault: unknown) => { setError(errorMessage(fault)); if (fault instanceof ApiError && fault.status === 401) await refresh(); };
  return <section className="mt-8" aria-labelledby="comments-heading">
    <h2 id="comments-heading" className="text-2xl font-bold">Comments</h2>
    {error && <p role="alert" className="mt-4">{error}</p>}
    {user ? <form className="my-5 grid gap-3" onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      if (!body.trim()) { setError('Write a comment first.'); return; }
      setBusy(true); setError('');
      try { await api('/posts/' + postId + '/comments', { method: 'POST', body: { body } }); setBody(''); resource.reload(); showToast('Comment posted.'); }
      catch (fault) { await fail(fault); } finally { setBusy(false); }
    }}><label>Write a comment<textarea className="block w-full mt-2 bg-surface-container-lowest rounded-lg border border-surface-container-highest p-3" required maxLength={4000} rows={3} value={body} onChange={event => setBody(event.target.value)} /></label>
      <button disabled={busy} className="min-h-11 px-4 py-3 rounded-lg bg-primary text-on-primary justify-self-start">{busy ? 'Posting…' : 'Post comment'}</button>
    </form> : <p className="my-4 text-sm"><Link className="text-secondary underline" to="/login">Sign in</Link> to comment.</p>}
    {resource.pending ? <p role="status">Loading comments…</p> : resource.error ? <div><p role="alert">{resource.error}</p><button className="min-h-11 underline" onClick={resource.reload}>Retry comments</button></div> : resource.data && <>
      {resource.data.items.length ? resource.data.items.map(comment => <article key={comment.id} className="surface-panel bg-surface-container-low rounded-xl p-5 my-4">
        <Link className="font-bold text-sm break-words" to={'/profile/' + comment.author.username}>{comment.author.display_name}</Link>
        <p className="mt-3 whitespace-pre-wrap break-words">{comment.body}</p>
        {comment.author.id === user?.id && <button className="text-primary underline min-h-11 mt-2" disabled={busy} onClick={async () => {
          if (busy || !window.confirm('Delete your comment?')) return;
          setBusy(true); setError('');
          try { await api('/comments/' + comment.id, { method: 'DELETE' }); resource.reload(); showToast('Comment deleted.'); }
          catch (fault) { await fail(fault); } finally { setBusy(false); }
        }}>Delete comment</button>}
      </article>) : <p className="my-5 text-on-surface-variant">No comments yet.</p>}
      <Pagination value={resource.data.pagination} onPage={setPage} />
    </>}
  </section>;
}

export function PostDetailPage() {
  const { postId } = useParams();
  const { user } = useAuth();
  const resource = useResource<Post>('/posts/' + encodeURIComponent(postId ?? ''));
  const post = resource.data;
  return <section className="w-full max-w-3xl mx-auto px-4 py-10">
    <h1 className="text-3xl font-bold break-words">{post?.title ?? 'Post discussion'}</h1>
    {resource.pending ? <p role="status">Loading post…</p> : resource.error ? <div className="mt-5"><p role="alert">{resource.error}</p><button className="min-h-11 underline" onClick={resource.reload}>Retry post</button></div> : post && <>
      <div className="my-5 flex flex-wrap gap-4 text-sm"><Link className="text-secondary break-words" to={'/profile/' + post.author.username}>{post.author.display_name}</Link><Link className="text-primary" to={'/explore?category=' + encodeURIComponent(post.category.slug)}>#{post.category.name}</Link>
        {post.author.id === user?.id && <Link className="underline" to={'/my-posts/' + post.id}>Edit post</Link>}
      </div>
      <div className="post-media relative aspect-[16/9] bg-surface-container-lowest rounded-xl overflow-hidden">
        <img src="/assets/illustrations/meme-1.svg" alt="" className="w-full h-full object-cover" /><p className="absolute bottom-0 inset-x-0 p-3 bg-surface-container-lowest/90 text-secondary text-xs">Decorative illustration · media display unavailable</p>
      </div>
      <p className="my-6 whitespace-pre-wrap break-words text-on-surface-variant leading-relaxed">{post.content}</p>
      <Comments key={post.id} postId={post.id} />
    </>}
  </section>;
}
