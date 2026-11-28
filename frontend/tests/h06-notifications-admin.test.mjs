import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const FRONTEND_SRC = path.resolve(import.meta.dirname, '..', 'src');

test('NotificationsDropdown localizes moderation actions, removes raw reaction types, and supports follow notifications', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'components', 'NotificationsDropdown.jsx'), 'utf8');

  assert.match(src, /Đã ẩn bài viết của bạn\./);
  assert.match(src, /Đã xóa bài viết của bạn\./);
  assert.match(src, /Đã ẩn bình luận của bạn\./);
  assert.match(src, /Đã xóa bình luận của bạn\./);
  assert.match(src, /Đã bắt đầu theo dõi bạn\./);
  assert.match(src, /Xem trang cá nhân/);
  assert.match(src, /\/u\/\$\{encodeURIComponent\(uname\)\}/);
  assert.match(src, /Đã thả biểu cảm vào bình luận của bạn/);
  assert.match(src, /Đã thả biểu cảm vào bài viết của bạn/);
  assert.doesNotMatch(src, /\$\{reactionType\}/);
  assert.doesNotMatch(src, /\$\{selectedNotif\.payload\?\.reaction_type/);
  assert.match(src, /selectedNotif\.type !== 'moderation'/);
});

test('AdminPage posts view includes date range filters, presets, sort, and clear filters', () => {
  const src = fs.readFileSync(path.join(FRONTEND_SRC, 'components', 'AdminPage.jsx'), 'utf8');

  assert.match(src, /date_from/);
  assert.match(src, /date_to/);
  assert.match(src, /Hôm nay/);
  assert.match(src, /7 ngày qua/);
  assert.match(src, /Tháng này/);
  assert.match(src, /created_desc/);
  assert.match(src, /created_asc/);
  assert.match(src, /Xóa bộ lọc/);
  assert.match(src, /Asia\/Ho_Chi_Minh/);
});
