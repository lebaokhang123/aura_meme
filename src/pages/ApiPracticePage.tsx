import { useEffect, useState, type FormEvent } from 'react';
import axios from 'axios';
import { createPost, deletePost, getPost, getPosts, updatePost, type BlogPost, type PostInput } from '../services/postApi';

const emptyForm: PostInput = { title: '', content: '', author: '' };

function errorMessage(error: unknown): string {
  if (axios.isAxiosError<{ errors?: Record<string, string[]> }>(error)) {
    if (error.response?.data.errors) return Object.values(error.response.data.errors).flat().join(' ');
    if (error.response?.status === 404) return 'Bài viết không còn tồn tại. Hãy tải lại danh sách.';
    if (error.response) return `API trả về lỗi ${error.response.status}. Vui lòng thử lại.`;
  }
  return 'Không kết nối được API. Kiểm tra backend đang chạy tại http://localhost:5080.';
}

export function ApiPracticePage() {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [form, setForm] = useState<PostInput>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    getPosts(controller.signal)
      .then(data => { if (!controller.signal.aborted) setPosts(data); })
      .catch(reason => { if (!controller.signal.aborted) setError(errorMessage(reason)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  async function reload() {
    setLoading(true);
    setError('');
    setMessage('');
    try { setPosts(await getPosts()); }
    catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = { title: form.title.trim(), content: form.content.trim(), author: form.author.trim() };
    if (!data.title || !data.content || !data.author) {
      setError('Vui lòng nhập đủ tiêu đề, nội dung và tác giả.');
      return;
    }
    setLoading(true);
    setError('');
    setMessage('');
    try {
      if (editingId === null) await createPost(data);
      else await updatePost(editingId, data);
      setMessage(editingId === null ? 'POST thành công: đã thêm bài viết.' : 'PUT thành công: đã cập nhật bài viết.');
      resetForm();
      setPosts(await getPosts());
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }

  async function edit(id: number) {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const post = await getPost(id);
      setForm({ title: post.title, content: post.content, author: post.author });
      setEditingId(post.id);
      setMessage(`GET /api/posts/${id} thành công. Có thể sửa bài trong form.`);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }

  async function remove(post: BlogPost) {
    if (!window.confirm(`Xóa bài "${post.title}"?`)) return;
    setLoading(true);
    setError('');
    setMessage('');
    try {
      await deletePost(post.id);
      if (editingId === post.id) resetForm();
      setMessage('DELETE thành công: đã xóa bài viết.');
      setPosts(await getPosts());
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }

  const inputClass = 'w-full rounded-lg border border-outline-variant bg-surface-container p-3 text-on-surface';
  const buttonClass = 'rounded-lg bg-surface-container-high px-4 py-2 hover:bg-surface-container-highest disabled:opacity-50';

  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-8 space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-primary">Thực hành ASP.NET Core API</h1>
        <p className="mt-2 text-sm text-on-surface-variant">React → Axios → PostsController → EF Core → SQLite</p>
        <p className="mt-1 text-sm text-on-surface-variant">Trang CRUD riêng cho bài nộp; Home vẫn dùng dữ liệu prototype.</p>
      </div>

      {error && <p role="alert" className="rounded-lg border border-error p-3 text-error">{error}</p>}
      {message && <p role="status" className="rounded-lg bg-surface-container p-3 text-secondary">{message}</p>}
      {loading && <p role="status">Đang gửi request đến backend…</p>}

      <form onSubmit={submit} className="rounded-xl bg-surface-container-low p-5">
        <h2 className="mb-4 text-lg font-semibold">{editingId === null ? 'Thêm bài viết (POST)' : `Sửa bài #${editingId} (PUT)`}</h2>
        <fieldset disabled={loading} className="space-y-4">
          <div>
            <label htmlFor="post-title" className="mb-1 block">Tiêu đề</label>
            <input id="post-title" className={inputClass} required maxLength={200} value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} />
          </div>
          <div>
            <label htmlFor="post-author" className="mb-1 block">Tác giả</label>
            <input id="post-author" className={inputClass} required maxLength={80} value={form.author} onChange={event => setForm({ ...form, author: event.target.value })} />
          </div>
          <div>
            <label htmlFor="post-content" className="mb-1 block">Nội dung</label>
            <textarea id="post-content" className={inputClass} required maxLength={10000} rows={4} value={form.content} onChange={event => setForm({ ...form, content: event.target.value })} />
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="submit" className="rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary disabled:opacity-50">{editingId === null ? 'Thêm bài viết' : 'Lưu thay đổi'}</button>
            {editingId !== null && <button type="button" className={buttonClass} onClick={resetForm}>Hủy sửa</button>}
          </div>
        </fieldset>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Danh sách bài viết ({posts.length})</h2>
        <button type="button" disabled={loading} onClick={reload} className={buttonClass}>Tải lại (GET)</button>
      </div>
      {!loading && !error && posts.length === 0 && <p>Chưa có bài viết. Hãy thêm bài đầu tiên.</p>}
      <div aria-busy={loading} className="space-y-3">
        {posts.map(post => (
          <article key={post.id} className="rounded-xl bg-surface-container-low p-5 space-y-3">
            <h3 className="break-words text-lg font-semibold">#{post.id} — {post.title}</h3>
            <p className="whitespace-pre-wrap break-words">{post.content}</p>
            <p className="text-sm text-on-surface-variant">{post.author} · {new Date(post.createdAt).toLocaleString('vi-VN')}</p>
            <div className="flex flex-wrap gap-3">
              <button type="button" disabled={loading} className={buttonClass} onClick={() => edit(post.id)}>Sửa bài #{post.id}</button>
              <button type="button" disabled={loading} className={`${buttonClass} text-error`} onClick={() => remove(post)}>Xóa bài #{post.id}</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
