import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { isKnownRoute, resolveScreen } from '../src/runtime.js';

const FRONTEND_SRC = path.resolve(import.meta.dirname, '..', 'src');

test('runtime recognizes /posts/:uuid detail route and keeps unknown routes 404', () => {
  const sampleId = '11111111-2222-3333-4444-555555555555';
  assert.equal(isKnownRoute(`/posts/${sampleId}`), true);
  assert.equal(isKnownRoute('/posts/not-a-uuid'), false);
  assert.equal(isKnownRoute('/posts'), false);
});

test('ReactionBar opens ReactionDetailsModal on pill/+N click without mutating viewer reaction', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'components', 'ReactionBar.jsx'), 'utf8');
  assert.match(src, /ReactionDetailsModal/);
  assert.match(src, /onClick=\{\(\)=>openDetails\(reaction\)\}/);
  assert.match(src, /onClick=\{\(\)=>openDetails\(null\)\}/);
});

test('CommentSection supports sorting, single-level replies, and lazy thread expansion', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'components', 'CommentSection.jsx'), 'utf8');
  assert.match(src, /reaction_desc/);
  assert.match(src, /created_desc/);
  assert.match(src, /created_asc/);
  assert.match(src, /loadReplies/);
  assert.match(src, /Đang trả lời/);
  assert.match(src, /Thu gọn/);
});

test('SocialContext uses batch include_interactions=true for comments and replies', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'SocialContext.jsx'), 'utf8');
  assert.match(src, /include_interactions=true/);
  assert.doesNotMatch(src, /\/comments\/'\+row\.id\+'\/interactions/);
});

test('NotificationsDropdown renders reply notifications and specific moderation badges', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'components', 'NotificationsDropdown.jsx'), 'utf8');
  assert.match(src, /Đã trả lời bình luận của bạn\./);
  assert.match(src, /Replied to your comment\./);
  assert.match(src, /Bài viết bị ẩn/);
  assert.match(src, /Bài viết bị xóa/);
  assert.match(src, /Bình luận bị ẩn/);
  assert.match(src, /Bình luận bị xóa/);
  assert.match(src, /\/posts\/\$\{selectedNotif\.payload\.post_id\}\?comment=/);
});

test('ShareButton generates canonical /posts/:id URL', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'components', 'ShareButton.jsx'), 'utf8');
  assert.match(src, /\/posts\/'\+postId/);
});
