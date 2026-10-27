import assert from 'node:assert/strict';
import { getPosts, getPost, createPost, updatePost, deletePost } from '../../src/services/postApi.ts';

// Run with Node 22.12+ against the running API. Removes only its own record.
let id: number | undefined;
try {
  assert.ok(Array.isArray(await getPosts()), 'GET list must return an array');
  const created = await createPost({ title: 'Axios smoke test', content: 'Created through Axios', author: 'Test' });
  id = created.id;
  assert.equal((await getPost(id)).content, 'Created through Axios');
  await updatePost(id, { title: 'Updated via Axios', content: 'Updated content', author: 'Test' });
  assert.equal((await getPost(id)).title, 'Updated via Axios');
  await deletePost(id);
  await assert.rejects(() => getPost(id!), (error: { response?: { status: number } }) => error.response?.status === 404);
  console.log('PASS Axios GET list / POST / GET detail / PUT / DELETE against SQLite API');
} finally {
  if (id !== undefined) {
    try { await deletePost(id); } catch (error) {
      if ((error as { response?: { status: number } }).response?.status !== 404) throw error;
    }
  }
}
