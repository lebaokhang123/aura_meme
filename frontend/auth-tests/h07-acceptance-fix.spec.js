import { test, expect } from '@playwright/test';

const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

function makeUser(id, username, displayName, roles = ['USER']) {
  return {
    id,
    username,
    email: `${username}@example.com`,
    display_name: displayName,
    roles,
    status: 'active',
    avatar_url: null,
    cover_url: null,
    level: 10,
    realm: 'Trúc Cơ',
    title: 'Đạo Hữu',
    membership_tier: 'free',
    csrf_token: 'h07-fixture-csrf',
  };
}

function emptyCounts() {
  return { like: 0, love: 0, laugh: 0, fire: 0, sad: 0, angry: 0 };
}

test('H07 Comment Locate renders root and reply at position >= 11 without duplicates', async ({ page, context }) => {
  const pid = uuid(910);
  const root11Id = uuid(921);
  const reply11Id = uuid(941);
  const viewer = makeUser(uuid(1), 'owner_user', 'Owner User');
  const cat = { id: uuid(801), slug: 'random', name: 'Random', post_count: 1 };

  const page1Roots = Array.from({ length: 10 }, (_, i) => ({
    id: uuid(911 + i),
    post_id: pid,
    body: `Root comment ${i + 1}`,
    created_at: new Date(Date.now() - (20 - i) * 60000).toISOString(),
    author: viewer,
    reply_count: 0,
    interactions: { comment_id: uuid(911 + i), reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [] },
  }));

  const root11 = {
    id: root11Id,
    post_id: pid,
    body: 'Root comment 11 (outside page 1)',
    created_at: new Date().toISOString(),
    author: viewer,
    reply_count: 11,
    interactions: { comment_id: root11Id, reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [] },
  };

  const page1Replies = Array.from({ length: 10 }, (_, i) => ({
    id: uuid(931 + i),
    post_id: pid,
    parent_comment_id: root11Id,
    body: `Reply ${i + 1}`,
    created_at: new Date(Date.now() - (15 - i) * 60000).toISOString(),
    author: viewer,
    reply_to_user: { id: viewer.id, username: viewer.username, display_name: viewer.display_name },
    interactions: { comment_id: uuid(931 + i), reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [] },
  }));

  const reply11 = {
    id: reply11Id,
    post_id: pid,
    parent_comment_id: root11Id,
    body: 'Reply 11 (outside page 1)',
    created_at: new Date().toISOString(),
    author: viewer,
    reply_to_user: { id: viewer.id, username: viewer.username, display_name: viewer.display_name },
    interactions: { comment_id: reply11Id, reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [] },
  };

  await context.addInitScript(() => {
    localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'vi' }));
  });

  await context.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const p = url.pathname.replace(/^\/api\/v1/, '');
    if (p === '/users/me') return route.fulfill({ json: viewer });
    if (p === '/categories') return route.fulfill({ json: { items: [cat], pagination: { page: 1, page_size: 100, total: 1, total_pages: 1 } } });
    if (p === `/posts/${pid}`) {
      return route.fulfill({
        json: {
          id: pid,
          title: 'Locate Target Post',
          content: 'Locate Target Content',
          status: 'published',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          media_url: null,
          category: cat,
          author: viewer,
        },
      });
    }
    if (p === `/posts/${pid}/interactions`) {
      return route.fulfill({ json: { post_id: pid, reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [], comments_count: 22 } });
    }
    if (p === `/posts/${pid}/comments`) {
      return route.fulfill({ json: { items: page1Roots, pagination: { page: 1, page_size: 10, total: 11, total_pages: 2 } } });
    }
    if (p === `/comments/${root11Id}/replies`) {
      return route.fulfill({ json: { items: page1Replies, pagination: { page: 1, page_size: 10, total: 11, total_pages: 2 } } });
    }
    if (p === `/posts/${pid}/comments/${reply11Id}/locate`) {
      return route.fulfill({
        json: {
          post_id: pid,
          comment_id: reply11Id,
          root_comment_id: root11Id,
          is_reply: true,
          root_comment: root11,
          target_comment: reply11,
        },
      });
    }
    if (p.startsWith('/notifications')) return route.fulfill({ json: { items: [], unread_count: 0, pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } } });
    if (p === '/premium/status') return route.fulfill({ json: { subscription: { tier: 'free', is_active: false }, plans: [] } });
    return route.fulfill({ json: {} });
  });

  await page.goto(`/posts/${pid}?comment=${reply11Id}`);
  await expect(page.locator(`[data-comment-id="${root11Id}"]`)).toHaveCount(1);
  await expect(page.locator(`[data-comment-id="${reply11Id}"]`)).toHaveCount(1);
  await expect(page.locator(`[data-comment-id="${reply11Id}"]`)).toBeVisible();
  await expect(page.locator(`[data-comment-id="${reply11Id}"]`)).toContainText('Reply 11 (outside page 1)');
  await expect(page.locator(`[data-comment-id="${reply11Id}"]`)).toHaveClass(/ring-secondary/);
});

test('H07 Post Detail edit, owner delete, admin hide, and reply count sync work without reload', async ({ page, context }) => {
  const pid = uuid(950);
  const pidAdmin = uuid(951);
  const rootId = uuid(960);
  const replyId = uuid(961);
  const owner = makeUser(uuid(1), 'owner_user', 'Owner User');
  const admin = makeUser(uuid(2), 'admin_user', 'Admin User', ['USER', 'ADMIN']);
  const cat1 = { id: uuid(801), slug: 'random', name: 'Random', post_count: 1 };
  const cat2 = { id: uuid(802), slug: 'gaming', name: 'Gaming', post_count: 1 };

  let currentUser = owner;
  let postState = {
    id: pid,
    title: 'Original Post',
    content: 'Original post content',
    status: 'published',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    media_url: null,
    category: cat1,
    author: owner,
  };
  let adminPostState = {
    id: pidAdmin,
    title: 'Admin Target Post',
    content: 'Admin target content',
    status: 'published',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    media_url: null,
    category: cat1,
    author: owner,
  };
  let replies = [
    {
      id: replyId,
      post_id: pid,
      parent_comment_id: rootId,
      body: 'Reply to delete',
      created_at: new Date().toISOString(),
      author: owner,
      reply_to_user: { id: owner.id, username: owner.username, display_name: owner.display_name },
      interactions: { comment_id: replyId, reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [] },
    },
  ];

  await context.addInitScript(() => {
    localStorage.setItem('aurameme-ui-preferences', JSON.stringify({ theme: 'dark', language: 'vi' }));
  });

  await context.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());
    const p = url.pathname.replace(/^\/api\/v1/, '');

    if (p === '/users/me') return route.fulfill({ json: currentUser });
    if (p === '/auth/csrf') return route.fulfill({ json: { csrf_token: 'h07-fixture-csrf' } });
    if (p === '/categories') return route.fulfill({ json: { items: [cat1, cat2], pagination: { page: 1, page_size: 100, total: 2, total_pages: 1 } } });
    if (p === `/posts/${pid}` && method === 'GET') {
      return postState ? route.fulfill({ json: postState }) : route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'Not found' } } });
    }
    if (p === `/posts/${pid}` && method === 'PATCH') {
      const body = req.postDataJSON();
      const nextCat = body.category_id === cat2.id ? cat2 : cat1;
      postState = { ...postState, content: body.content, category: nextCat, updated_at: new Date().toISOString() };
      return route.fulfill({ json: postState });
    }
    if (p === `/posts/${pid}` && method === 'DELETE') {
      postState = null;
      return route.fulfill({ status: 204, body: '' });
    }
    if (p === `/posts/${pidAdmin}` && method === 'GET') {
      return adminPostState ? route.fulfill({ json: adminPostState }) : route.fulfill({ status: 404, json: { error: { code: 'NOT_FOUND', message: 'Not found' } } });
    }
    if (p === `/admin/posts/${pidAdmin}` && method === 'PATCH') {
      adminPostState = null;
      return route.fulfill({ status: 204, body: '' });
    }
    if (p === `/posts/${pid}/interactions` || p === `/posts/${pidAdmin}/interactions`) {
      return route.fulfill({ json: { post_id: p.includes(pidAdmin) ? pidAdmin : pid, reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [], comments_count: 1 + replies.length } });
    }
    if (p === `/posts/${pid}/comments` && method === 'GET') {
      return route.fulfill({
        json: {
          items: [{
            id: rootId,
            post_id: pid,
            body: 'Root comment',
            created_at: new Date().toISOString(),
            author: owner,
            reply_count: replies.length,
            interactions: { comment_id: rootId, reaction_counts: emptyCounts(), viewer_reaction: null, meme_reactions: [] },
          }],
          pagination: { page: 1, page_size: 10, total: 1, total_pages: 1 },
        },
      });
    }
    if (p === `/posts/${pidAdmin}/comments` && method === 'GET') {
      return route.fulfill({ json: { items: [], pagination: { page: 1, page_size: 10, total: 0, total_pages: 1 } } });
    }
    if (p === `/comments/${rootId}/replies` && method === 'GET') {
      return route.fulfill({ json: { items: replies, pagination: { page: 1, page_size: 10, total: replies.length, total_pages: 1 } } });
    }
    if (p === `/comments/${replyId}` && method === 'DELETE') {
      replies = [];
      return route.fulfill({ status: 204, body: '' });
    }
    if (p.startsWith('/notifications')) return route.fulfill({ json: { items: [], unread_count: 0, pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } } });
    if (p === '/premium/status') return route.fulfill({ json: { subscription: { tier: 'free', is_active: false }, plans: [] } });
    return route.fulfill({ json: {} });
  });

  // 1. Owner opens PostDetailPage, expands replies, deletes reply -> count decrements without F5
  await page.goto(`/posts/${pid}`);
  const card = page.locator(`[data-post-id="${pid}"]`);
  await expect(card).toContainText('Original post content');
  await card.getByRole('button', { name: 'Xem 1 câu trả lời' }).click();
  const replyRow = card.locator(`[data-comment-id="${replyId}"]`);
  await expect(replyRow).toBeVisible();
  await replyRow.getByRole('button', { name: 'Tùy chọn bình luận' }).click();
  await replyRow.getByRole('menuitem', { name: 'Xóa bình luận' }).click();
  await replyRow.getByRole('button', { name: 'Xác nhận xóa' }).click();
  await expect(replyRow).toHaveCount(0);
  await expect(card.getByRole('button', { name: /Xem \d+ câu trả lời/ })).toHaveCount(0);

  // 2. Owner edits post content and category -> immediately reflected without F5
  await card.getByRole('button', { name: 'Tùy chọn bài viết' }).click();
  await card.getByRole('menuitem', { name: 'Sửa bài' }).click();
  await card.getByLabel('Nội dung sửa bài').fill('Updated post content');
  await card.getByLabel('Danh mục sửa bài').selectOption('gaming');
  await card.getByRole('button', { name: 'Lưu thay đổi' }).click();
  await expect(card).toContainText('Updated post content');
  await expect(card).toContainText('#gaming');

  // 3. Owner deletes post -> immediately renders 404 without F5
  await card.getByRole('button', { name: 'Tùy chọn bài viết' }).click();
  await card.getByRole('menuitem', { name: 'Xóa bài' }).click();
  await card.getByRole('button', { name: 'Xác nhận xóa' }).click();
  await expect(card).toHaveCount(0);
  await expect(page.getByText('404')).toBeVisible();

  // 4. Admin hides post on detail page -> immediately renders 404 without F5
  currentUser = admin;
  await page.goto(`/posts/${pidAdmin}`);
  const adminCard = page.locator(`[data-post-id="${pidAdmin}"]`);
  await expect(adminCard).toContainText('Admin target content');
  await adminCard.getByRole('button', { name: 'Tùy chọn bài viết' }).click();
  await adminCard.getByRole('menuitem', { name: 'Ẩn bài (Admin)' }).click();
  await adminCard.getByLabel(/Lý do/).fill('Vi phạm quy định cộng đồng');
  await adminCard.getByRole('button', { name: 'Xác nhận' }).click();
  await expect(adminCard).toHaveCount(0);
  await expect(page.getByText('404')).toBeVisible();
});
