import { test, expect } from '@playwright/test';

const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const now = '2026-11-20T10:00:00Z';

async function setupAdminMockApi(context) {
  const users = [
    { id: id(1), username: 'admin_qa', display_name: 'Admin QA', roles: ['USER', 'ADMIN'], status: 'active', email: 'admin@example.com' },
    { id: id(2), username: 'member_one', display_name: 'Member One', roles: ['USER'], status: 'active', email: 'member@example.com' }
  ];

  const rows = {
    users,
    posts: [
      { id: id(10), title: 'Cyberpunk Cultivation Masterpiece', content: 'Nội dung bài viết tu tiên cyberpunk cực chất.', status: 'published', author: users[1], created_at: now, media_url: '/api/v1/media/' + id(70) },
      { id: id(11), title: 'Hidden spam post', content: 'Bài viết quảng cáo vi phạm đã bị ẩn.', status: 'hidden', author: users[1], created_at: now, media_url: null },
      { id: id(12), title: 'Deleted post', content: 'Bài viết đã xóa hoàn toàn.', status: 'deleted', author: users[1], created_at: now, media_url: null }
    ],
    comments: [
      { id: id(20), post_id: id(10), post_title: 'Cyberpunk Cultivation Masterpiece', body: 'Bình luận thảo luận về đan dược cyberpunk.', status: 'visible', author: users[1], created_at: now },
      { id: id(21), post_id: id(10), post_title: 'Cyberpunk Cultivation Masterpiece', body: 'Bình luận tục tĩu đã bị ẩn.', status: 'hidden', author: users[1], created_at: now }
    ],
    categories: [
      { id: id(30), name: 'Tu Tiên Meme', slug: 'tu-tien-meme', status: 'active' }
    ],
    contacts: [
      { id: id(40), name: 'Nguyễn Văn Hỗ Trợ', email: 'support-user@example.com', subject: 'Cần hỗ trợ về tài khoản Aura', body: 'Xin chào AuraMeme,\nTôi không nhận được Aura sau khi điểm danh ngày hôm qua.\nNhờ ban quản trị kiểm tra giúp.\nXin cảm ơn!', status: 'new', created_at: now }
    ],
    'audit-logs': [
      { id: id(50), actor_id: id(1), action: 'post.update', target_type: 'post', target_id: id(10), created_at: now },
      { id: id(51), actor_id: id(1), action: 'contact.update', target_type: 'contact', target_id: id(40), created_at: now },
      { id: id(52), actor_id: id(1), action: 'announcement.publish', target_type: 'announcement', target_id: id(70), created_at: now }
    ],
    assets: [
      { id: id(60), slug: 'cyber-sword', kind: 'avatar', rarity: 'S', active: true, review_status: 'approved' }
    ],
    announcements: [
      { id: id(70), title: 'Bảo trì hệ thống định kỳ', body: 'Hệ thống sẽ bảo trì vào 02:00 sáng mai.', status: 'published', actor_id: id(1), actor_username: 'admin_qa', created_at: now, published_at: now, recipients_count: 150 },
      { id: id(71), title: 'Sự kiện Meme Cyberpunk Mùa Mới', body: 'Bản nháp thông báo sự kiện mùa đông...', status: 'draft', actor_id: id(1), actor_username: 'admin_qa', created_at: now },
      { id: id(72), title: 'Thông báo nâng cấp máy chủ cũ', body: 'Thông báo này đã được thu hồi.', status: 'withdrawn', actor_id: id(1), actor_username: 'admin_qa', created_at: now }
    ]
  };

  const requests = [];

  await context.route('**/api/v1/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.slice('/api/v1'.length);
    const method = request.method();
    let body;
    try { body = request.postDataJSON(); } catch {}
    requests.push({ path, method, body, url: request.url() });

    const send = (status, data) => route.fulfill({ status, contentType: 'application/json', body: status === 204 ? '' : JSON.stringify(data) });
    const page = items => ({ items, pagination: { page: 1, page_size: 10, total: items.length, total_pages: 1 } });

    if (path === '/users/me') return send(200, users[0]);
    if (path === '/auth/csrf') return send(200, { csrf_token: 'server-csrf-token' });
    if (path === '/notifications/unread-count') return send(200, { unread_count: 1 });
    if (path === '/notifications') {
      return send(200, {
        items: [
          {
            id: id(80),
            type: 'announcement',
            actor: { id: id(1), username: 'admin_qa', display_name: 'Admin Tổng Chủ' },
            payload: { title: 'Chào mừng thành viên mới', body: 'AuraMeme hân hạnh chào đón các tu tiên giả gia nhập đấu trường meme cyberpunk đỉnh cao.' },
            is_read: false,
            created_at: now
          },
          {
            id: id(81),
            type: 'comment',
            actor: { id: id(2), username: 'member_01', display_name: 'Hắc Ám Đạo Nhân' },
            payload: { post_title: 'Meme tu tiên hài hước', comment_text: 'Đạo hữu tu vi thâm hậu quá!' },
            is_read: true,
            created_at: now
          }
        ],
        pagination: { page: 1, page_size: 20, total: 2, total_pages: 1 },
        unread_count: 1
      });
    }

    const parts = path.split('/').filter(Boolean);
    if (parts[0] !== 'admin') return send(200, page([]));

    const resource = parts[1];
    const ident = parts[2];

    if (method === 'GET') {
      const items = rows[resource] || [];
      return send(200, page(items));
    }

    if (method === 'PATCH' || method === 'PUT') {
      const item = (rows[resource] || []).find(r => r.id === ident);
      if (item) Object.assign(item, body);
      return send(200, item || {});
    }

    return send(200, {});
  });

  return { rows, requests };
}

test.describe('Task 2 — Admin Workspace UX Refinement', () => {
  test('Subtask E: Admin workspace brand displays approved guardian icon', async ({ page, context }) => {
    await setupAdminMockApi(context);
    await page.goto('/admin');
    await expect(page.getByRole('heading', { name: 'Không gian quản trị', exact: true })).toBeVisible();

    const guardianLogo = page.locator('.admin-brand-mark img.admin-brand-logo-img');
    await expect(guardianLogo).toBeVisible();
    await expect(guardianLogo).toHaveAttribute('src', '/assets/brand/04_admin_guardian-circle-48.png');
    await expect(guardianLogo).toHaveAttribute('alt', 'AuraMeme Guardian');
    const box = await guardianLogo.boundingBox();
    expect(box.width).toBeCloseTo(40, 1);
    expect(box.height).toBeCloseTo(40, 1);
  });

  test('Subtask A: Content management uses 4 action icons and read-only preview modal', async ({ page, context }) => {
    await setupAdminMockApi(context);
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Nội dung' }).click();
    await expect(page.getByRole('heading', { name: 'Bài viết', exact: true })).toBeVisible();

    // Verify details summary tag is gone from row main
    const publishedRow = page.locator(`[data-admin-id="${id(10)}"]`);
    await expect(publishedRow.locator('details')).toHaveCount(0);
    await expect(publishedRow.locator('.admin-content-snippet')).toBeVisible();

    // Verify 4 action icons in published row
    const actionIcons = publishedRow.locator('.admin-action-icons');
    await expect(actionIcons).toBeVisible();
    const previewBtn = actionIcons.getByRole('button', { name: 'Xem chi tiết bài viết' });
    const hideBtn = actionIcons.getByRole('button', { name: 'Ẩn nội dung' });
    const deleteBtn = actionIcons.getByRole('button', { name: 'Xóa nội dung' });
    const openLink = actionIcons.getByRole('link', { name: 'Mở bài viết trên trang cộng đồng' });

    await expect(previewBtn).toBeEnabled();
    await expect(hideBtn).toBeEnabled();
    await expect(deleteBtn).toBeEnabled();
    await expect(openLink).toHaveAttribute('href', `/#post-${id(10)}`);
    await expect(openLink).toHaveAttribute('target', '_blank');

    // Click preview icon to open read-only modal
    await previewBtn.click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Chi tiết bài viết' })).toBeVisible();
    await expect(dialog.locator('.admin-content-preview-author')).toHaveText('@member_one');
    await expect(dialog.locator('.admin-content-preview-title')).toHaveText('Cyberpunk Cultivation Masterpiece');
    await expect(dialog.locator('.admin-content-preview-body')).toContainText('Nội dung bài viết tu tiên cyberpunk');
    await expect(dialog.locator('.admin-content-preview-media img')).toBeVisible();

    // Verify no social/mutation buttons in preview
    await expect(dialog.getByRole('button', { name: 'Like' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Thích' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Bình luận' })).toHaveCount(0);

    // Close preview
    await dialog.locator('.workspace-dialog-actions').getByRole('button', { name: 'Đóng' }).click();
    await expect(dialog).toBeHidden();

    // Verify disabled open_in_new on hidden row
    const hiddenRow = page.locator(`[data-admin-id="${id(11)}"]`);
    const hiddenOpenBtn = hiddenRow.locator('.admin-action-icons button.is-disabled');
    await expect(hiddenOpenBtn).toBeDisabled();
    await expect(hiddenOpenBtn).toHaveAttribute('title', 'Không thể mở nội dung đã ẩn hoặc đã xóa');
  });

  test('Subtask B: Contact management modal presents structured hierarchy', async ({ page, context }) => {
    await setupAdminMockApi(context);
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Liên hệ' }).click();
    await expect(page.getByRole('heading', { name: 'Hộp thư liên hệ', exact: true })).toBeVisible();

    const contactRow = page.locator(`[data-admin-id="${id(40)}"]`);
    await contactRow.getByRole('button', { name: 'Xem và xử lý' }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Chi tiết & Xử lý liên hệ' })).toBeVisible();

    // Header info card
    await expect(dialog.locator('.admin-contact-sender-name')).toHaveText('Nguyễn Văn Hỗ Trợ');
    await expect(dialog.locator('.admin-contact-subject')).toHaveText('Cần hỗ trợ về tài khoản Aura');

    // Distinct scrollable body box
    const bodyBox = dialog.locator('.admin-contact-body-box');
    await expect(bodyBox).toBeVisible();
    await expect(bodyBox).toContainText('Tôi không nhận được Aura sau khi điểm danh');

    // Status selection & actions
    const statusSelect = dialog.locator('#admin-contact-status-select');
    await expect(statusSelect).toBeVisible();
    await statusSelect.selectOption('in_review');

    const saveBtn = dialog.locator('.workspace-dialog-actions').getByRole('button', { name: 'Lưu trạng thái' });
    await expect(saveBtn).toBeVisible();
    await saveBtn.click();
    await expect(dialog).toBeHidden();
  });

  test('Subtask C: Audit activity humanizes actions and provides technical ID copy', async ({ page, context }) => {
    await setupAdminMockApi(context);
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Kiểm duyệt' }).click();
    await expect(page.getByRole('heading', { name: 'Nhật ký quản trị', exact: true })).toBeVisible();
    await expect(page.locator('.admin-list-note')).toContainText('Ghi lại các thay đổi do quản trị viên thực hiện');

    const auditEntry = page.locator('.admin-audit-entry').first();
    await expect(auditEntry).toBeVisible();
    await expect(auditEntry.locator('.admin-audit-title')).toHaveText('Cập nhật bài viết');
    await expect(auditEntry.locator('.admin-audit-sub')).toContainText('Bài viết');

    // Collapsible technical details with copy button
    const details = auditEntry.locator('.admin-audit-tech-details');
    await expect(details.locator('summary')).toHaveText('Chi tiết kỹ thuật');
    await details.locator('summary').click();
    const copyBtn = details.locator('.admin-copy-btn');
    await expect(copyBtn).toBeVisible();
    await expect(copyBtn).toContainText('Sao chép');
  });

  test('Subtask D: System announcement composer microcopy polish', async ({ page, context }) => {
    await setupAdminMockApi(context);
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Thông báo' }).click();
    await expect(page.getByRole('heading', { name: 'Thông báo hệ thống', exact: true })).toBeVisible();

    await page.locator('.admin-broadcast-btn').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('#admin-dialog-title')).toContainText('Soạn thông báo hệ thống');
    await expect(dialog.locator('.workspace-meta')).toHaveText('Thông báo sẽ được gửi tới tất cả thành viên đang hoạt động.');

    const eyeBtn = dialog.locator('#admin-preview-eye-btn');
    await expect(eyeBtn).toBeVisible();
    await expect(eyeBtn.locator('.material-symbols-outlined')).toHaveCount(1);
    await expect(eyeBtn).not.toContainText('Giữ để xem trước');
    await expect(eyeBtn).not.toContainText('Hold to preview');
    await expect(eyeBtn).toHaveAttribute('title', 'Giữ để xem trước');
    await dialog.getByRole('button', { name: 'Hủy' }).click();
  });

  test('Subtask F: API requests use page_size 10', async ({ page, context }) => {
    const { requests } = await setupAdminMockApi(context);
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Nội dung' }).click();

    const getRequests = requests.filter(r => r.method === 'GET' && r.path.startsWith('/admin/'));
    expect(getRequests.length).toBeGreaterThan(0);
    for (const req of getRequests) {
      expect(req.url).toContain('page_size=10');
    }
  });

  test('Capture Visual QA Screenshots across Desktop, Tablet, and Mobile', async ({ page, context }) => {
    await setupAdminMockApi(context);
    const artifactDir = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';

    // 1. Desktop Viewport (1440x900)
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Nội dung' }).click();
    await expect(page.locator(`[data-admin-id="${id(10)}"]`)).toBeVisible();
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_desktop.png`, fullPage: true });

    // 2. Desktop Content Preview Modal
    await page.locator(`[data-admin-id="${id(10)}"] .admin-action-icons`).getByRole('button', { name: 'Xem chi tiết bài viết' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_content_preview.png` });
    await page.getByRole('dialog').locator('.workspace-dialog-actions').getByRole('button', { name: 'Đóng' }).click();

    // 3. Desktop Contact Management Modal
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Liên hệ' }).click();
    await page.locator(`[data-admin-id="${id(40)}"]`).getByRole('button', { name: 'Xem và xử lý' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_contact_modal.png` });
    await page.getByRole('dialog').getByRole('button', { name: 'Hủy' }).click();

    // 4. Desktop Audit Activity Tab
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Kiểm duyệt' }).click();
    await expect(page.locator('.admin-audit-entry').first()).toBeVisible();
    await page.locator('.admin-audit-entry').first().locator('summary').click();
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_audit_activity.png` });

    // 5. Tablet Viewport (768x1024)
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Nội dung' }).click();
    await expect(page.locator(`[data-admin-id="${id(10)}"]`)).toBeVisible();
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_tablet.png`, fullPage: true });

    // 6. Mobile Viewport (375x812)
    await page.setViewportSize({ width: 375, height: 812 });
    await expect(page.locator(`[data-admin-id="${id(10)}"]`)).toBeVisible();
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_mobile.png`, fullPage: true });
  });

  test('Task 2 Final Polish: Personal notification card displays 4 distinct lines with ellipsis', async ({ page, context }) => {
    await setupAdminMockApi(context);
    const artifactDir = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';
    await page.goto('/admin');
    await page.locator('.notification-trigger').click();
    await expect(page.locator('.notifications-dropdown')).toBeVisible();

    const firstItem = page.locator('.notification-item').first();
    await expect(firstItem.locator('.notification-card-actor')).toHaveText('Admin Tổng Chủ');
    await expect(firstItem.locator('.notification-card-title')).toHaveText('Chào mừng thành viên mới');
    await expect(firstItem.locator('.notification-card-snippet')).toContainText('AuraMeme hân hạnh chào đón');
    await expect(firstItem.locator('.notification-card-time')).toBeVisible();

    // Verify CSS ellipsis on snippet
    const snippetStyle = await firstItem.locator('.notification-card-snippet').evaluate(el => {
      const s = window.getComputedStyle(el);
      return { textOverflow: s.textOverflow, whiteSpace: s.whiteSpace, overflow: s.overflow };
    });
    expect(snippetStyle.textOverflow).toBe('ellipsis');
    expect(snippetStyle.whiteSpace).toBe('nowrap');
    expect(snippetStyle.overflow).toBe('hidden');

    await page.screenshot({ path: `${artifactDir}/notification_dropdown_4lines.png` });
  });

  test('Task 2 Final Polish: Announcement table uses snippet and normalized 40px action icon buttons', async ({ page, context }) => {
    await setupAdminMockApi(context);
    const artifactDir = 'C:/Users/sammy/.gemini/antigravity/brain/cc803197-d415-4eaf-80c2-1173a22c12aa';
    await page.goto('/admin');
    await page.locator('.admin-sidebar').getByRole('button', { name: 'Thông báo' }).click();

    // 1. Verify <details> removed and replaced by .admin-content-snippet
    await expect(page.locator('[data-resource="announcements"] details')).toHaveCount(0);
    const publishedRow = page.locator(`[data-admin-id="${id(70)}"]`);
    await expect(publishedRow.locator('.admin-content-snippet')).toBeVisible();

    // 2. Verify normalized 40px icon button dimensions
    const iconBtn = publishedRow.locator('.admin-icon-btn').first();
    const btnBox = await iconBtn.boundingBox();
    expect(Math.round(btnBox.width)).toBe(40);
    expect(Math.round(btnBox.height)).toBe(40);

    // 3. Verify action icons for Published: visibility, undo (rectify button removed per Owner specification)
    await expect(publishedRow.locator('.admin-action-icons .admin-icon-btn')).toHaveCount(2);
    await expect(publishedRow.locator('.admin-action-icons [aria-label="Xem chi tiết thông báo"]')).toBeVisible();
    await expect(publishedRow.locator('.admin-action-icons [aria-label="Đính chính thông báo"]')).toHaveCount(0);
    await expect(publishedRow.locator('.admin-action-icons [aria-label="Thu hồi thông báo"]')).toBeVisible();

    // 4. Verify action icons for Draft: visibility, edit, send, delete
    const draftRow = page.locator(`[data-admin-id="${id(71)}"]`);
    await expect(draftRow.locator('.admin-action-icons .admin-icon-btn')).toHaveCount(4);
    await expect(draftRow.locator('.admin-action-icons [aria-label="Xem chi tiết thông báo"]')).toBeVisible();
    await expect(draftRow.locator('.admin-action-icons [aria-label="Sửa bản nháp"]')).toBeVisible();
    await expect(draftRow.locator('.admin-action-icons [aria-label="Phát thông báo ngay"]')).toBeVisible();
    await expect(draftRow.locator('.admin-action-icons [aria-label="Xóa bản nháp"]')).toBeVisible();

    // 5. Verify action icons for Withdrawn: visibility only
    const withdrawnRow = page.locator(`[data-admin-id="${id(72)}"]`);
    await expect(withdrawnRow.locator('.admin-action-icons .admin-icon-btn')).toHaveCount(1);
    await expect(withdrawnRow.locator('.admin-action-icons [aria-label="Xem chi tiết thông báo"]')).toBeVisible();

    // 6. Screenshot announcements table
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_announcements.png` });

    // 7. Click visibility on published announcement -> opens preview modal
    await publishedRow.locator('.admin-action-icons [aria-label="Xem chi tiết thông báo"]').click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('#admin-dialog-title')).toHaveText('Chi tiết thông báo hệ thống');
    await expect(dialog.locator('.admin-content-preview-author')).toHaveText('@admin_qa');
    await expect(dialog.locator('.admin-content-preview-title')).toHaveText('Bảo trì hệ thống định kỳ');
    await expect(dialog.locator('.admin-content-preview-body')).toContainText('Hệ thống sẽ bảo trì vào 02:00 sáng mai.');

    // Screenshot announcement preview modal
    await page.screenshot({ path: `${artifactDir}/admin_qa_task2_announcement_preview.png` });
    await dialog.locator('.workspace-dialog-actions').getByRole('button', { name: 'Đóng' }).click();
    await expect(dialog).toHaveCount(0);
  });
});
