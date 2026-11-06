import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, ApiError, errorMessage } from '../api';
import type { OwnPost, Post } from '../blog';
import { useAuth } from '../context/AuthContext';
import { useUI } from '../context/UIContext';
import { useCategories } from '../hooks/useFeed';
import { useResource } from '../hooks/useResource';

function PostForm({ post, reload }: { post?: OwnPost; reload: () => void }) {
  const categories = useCategories();
  const { refresh } = useAuth();
  const { showToast } = useUI();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [uploaded, setUploaded] = useState<string | null>(null);
  const [remove, setRemove] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const fail = async (fault: unknown) => { setError(errorMessage(fault)); if (fault instanceof ApiError && fault.status === 401) await refresh(); };
  const input = 'block mt-2 w-full min-w-0 rounded-lg bg-surface-container-lowest border border-surface-container-highest p-3';
  const erase = async () => {
    if (busy || !post || !window.confirm('Delete this post? It will no longer be available.')) return;
    setBusy(true); setError('');
    try { await api('/posts/' + post.id, { method: 'DELETE' }); showToast('Post deleted.'); navigate('/my-posts'); }
    catch (fault) { await fail(fault); } finally { setBusy(false); }
  };
  if (post?.status === 'hidden') return <div className="surface-panel bg-surface-container-low rounded-xl p-6 mt-6">
    <h2 className="font-bold break-words">{post.title}</h2><p className="mt-4 whitespace-pre-wrap break-words">{post.content}</p>
    <p className="mt-4 text-secondary">This post is hidden by moderation. Editing is unavailable.</p>
    {error && <p role="alert">{error}</p>}<button className="min-h-11 underline mt-4" disabled={busy} onClick={() => void erase()}>Delete post</button>
  </div>;
  return <form className="surface-panel bg-surface-container-low rounded-xl p-5 sm:p-8 my-6 grid gap-5" onSubmit={async event => {
    event.preventDefault(); if (busy) return;
    const data = new FormData(event.currentTarget);
    const values = { title: String(data.get('title')), content: String(data.get('content')), category_id: String(data.get('category_id')), status: String(data.get('status')) };
    if (!values.content.trim() && !file && !uploaded && !(post?.media_id && !remove)) { setError('Write some text or attach an image.'); return; }
    setBusy(true); setError('');
    try {
      let media = uploaded;
      if (file && !media) {
        const upload = new FormData(); upload.set('file', file);
        const saved = await api<{ id: string }>('/media', { method: 'POST', body: upload });
        media = saved.id; setUploaded(saved.id);
      }
      const body: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(values)) {
        const previous = key === 'category_id' ? post?.category.id : post?.[key as keyof Post];
        if (!post || value !== previous) body[key] = value;
      }
      if (media) body.media_id = media;
      else if (remove) body.media_id = null;
      if (post && !Object.keys(body).length) { showToast('No changes to save.'); return; }
      const saved = await api<Post>(post ? '/posts/' + post.id : '/posts', { method: post ? 'PATCH' : 'POST', body });
      showToast(saved.status === 'draft' ? 'Draft saved.' : 'Post saved.');
      if (post) reload(); else navigate('/my-posts/' + saved.id);
    } catch (fault) { await fail(fault); } finally { setBusy(false); }
  }}>
    {error && <p role="alert" className="text-primary">{error}{uploaded && ' The upload is saved privately; retry saving this post to attach it.'}</p>}
    <fieldset disabled={busy} className="contents">
    <label>Title<input name="title" className={input} required maxLength={160} defaultValue={post?.title ?? ''} /></label>
    <label>Content<textarea name="content" className={input} rows={8} maxLength={20000} defaultValue={post?.content ?? ''} /></label>
    <label>Category<select name="category_id" className={input} required defaultValue={post?.category.id ?? ''}>
      <option value="" disabled>Choose a channel</option>
      {post && !categories.items.some(item => item.id === post.category.id) && <option value={post.category.id}>{post.category.name} (current)</option>}
      {categories.items.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
    </select></label>
    {categories.error && <p role="alert">{categories.error} <button type="button" className="underline min-h-11" onClick={categories.reload}>Retry channels</button></p>}
    {categories.hasPages && <button type="button" aria-disabled={categories.pending || !categories.more} aria-live="polite" onClick={categories.loadMore} className="text-secondary min-h-11">{categories.more || categories.pending ? "More channels" : "All channels loaded"}</button>}
    <label>Post status<select className={input} name="status" defaultValue={post?.status ?? 'draft'}><option value="draft">Draft</option><option value="published">Published</option></select></label>
    <label>Attach image (optional)<input className={input} type="file" accept="image/png,image/jpeg,image/webp,image/gif" disabled={busy} onChange={event => {
      const value = event.target.files?.[0] ?? null;
      if (value && (value.size > 5 * 1024 * 1024 || !['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(value.type))) { setFile(null); setUploaded(null); setError('Choose a JPEG, PNG, WebP or GIF up to 5 MiB.'); event.target.value = ''; return; }
      setFile(value); setUploaded(null); setRemove(false); setError('');
    }} /></label>
    {preview && <figure><img src={preview} alt="Local preview of the selected attachment" className="motion-reduce:hidden max-h-80 max-w-full rounded-lg object-contain" /><figcaption className="mt-2 text-xs text-secondary"><span className="hidden motion-reduce:inline">Preview hidden for reduced motion. Your attachment remains selected.</span> Local preview only. Server media display is not available.</figcaption></figure>}
    {post?.media_id && <label className="text-sm"><input type="checkbox" checked={remove} disabled={!!file || busy} onChange={event => setRemove(event.target.checked)} /> Remove existing private attachment</label>}
    <p className="text-xs text-on-surface-variant">Images are stored privately. An uploaded image remains saved if you leave before attaching it; keep this page open to retry a failed post save.</p>
    <div className="flex flex-wrap gap-4"><button disabled={busy} className="min-h-11 px-5 py-3 rounded-lg bg-primary text-on-primary disabled:opacity-50">{busy ? 'Saving…' : 'Save post'}</button>
      {post && <button type="button" disabled={busy} onClick={() => void erase()} className="min-h-11 underline text-primary">Delete post</button>}
      {post?.status === 'published' && !busy && <Link className="min-h-11 py-3 text-secondary" to={'/posts/' + post.id}>View discussion</Link>}
    </div>
    </fieldset>
  </form>;
}

export function PostEditorPage() {
  const { postId } = useParams();
  const resource = useResource<OwnPost>(postId ? '/users/me/posts/' + encodeURIComponent(postId) : null);
  return <section className="w-full max-w-3xl mx-auto px-4 py-10">
    <h1 className="text-3xl font-bold">{postId ? 'Edit your post' : 'Create a post'}</h1>
    <Link className="inline-flex min-h-11 py-3 text-secondary" to="/my-posts">Back to my posts</Link>
    {!postId ? <PostForm reload={resource.reload} /> : resource.pending ? <p role="status">Loading your post…</p> : resource.error ? <div><p role="alert">{resource.error}</p><button className="min-h-11 underline" onClick={resource.reload}>Retry post</button></div>
      : resource.data && <PostForm key={resource.data.updated_at} post={resource.data} reload={resource.reload} />}
  </section>;
}
