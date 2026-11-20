import test from 'node:test';
import assert from 'node:assert/strict';

import { getNotifications, getUnreadCount, markRead, markAllRead, deleteNotification, createAnnouncement } from '../src/notifications-api.js';

function mockClient() {
  const calls = [];
  return {
    calls,
    read: async (path) => {
      calls.push({ method: 'GET', path });
      if (path.includes('/unread-count')) {
        return { unread_count: 3 };
      }
      return {
        items: [
          {
            id: '11111111-1111-1111-1111-111111111111',
            type: 'reaction',
            target_type: 'post',
            target_id: '22222222-2222-2222-2222-222222222222',
            actor: {
              id: '33333333-3333-3333-3333-333333333333',
              username: 'tester',
              display_name: 'Tester',
              avatar_url: null
            },
            payload: { reaction_type: 'fire' },
            created_at: '2026-11-19T10:00:00Z',
            read_at: null,
            is_read: false
          }
        ],
        pagination: {
          page: 1,
          page_size: 20,
          total: 1,
          total_pages: 1
        },
        unread_count: 3
      };
    },
    write: async (method, path, body) => {
      calls.push({ method, path, body });
      if (path.endsWith('/read-all')) {
        return { marked_read: 3 };
      }
      return {
        id: path.split('/')[2],
        type: 'reaction',
        target_type: 'post',
        created_at: '2026-11-19T10:00:00Z',
        read_at: '2026-11-19T10:05:00Z',
        is_read: true
      };
    }
  };
}

test('notifications API: fetch items with pagination and query parameters', async () => {
  const client = mockClient();
  const res = await getNotifications({ page: 2, pageSize: 15, unreadOnly: true, client });
  assert.equal(client.calls[0].path, '/notifications?page=2&page_size=15&unread_only=true');
  assert.equal(res.items.length, 1);
  assert.equal(res.unread_count, 3);
  assert.equal(res.pagination.page, 1);
});

test('notifications API: fetch unread count', async () => {
  const client = mockClient();
  const res = await getUnreadCount({ client });
  assert.equal(client.calls[0].path, '/notifications/unread-count');
  assert.equal(res.unread_count, 3);
});

test('notifications API: mark one notification read', async () => {
  const client = mockClient();
  const notifId = '11111111-1111-1111-1111-111111111111';
  const res = await markRead(notifId, { client });
  assert.equal(client.calls[0].method, 'PATCH');
  assert.equal(client.calls[0].path, `/notifications/${notifId}/read`);
  assert.equal(res.is_read, true);
});

test('notifications API: mark all notifications read', async () => {
  const client = mockClient();
  const res = await markAllRead({ client });
  assert.equal(client.calls[0].method, 'POST');
  assert.equal(client.calls[0].path, '/notifications/read-all');
  assert.equal(res.marked_read, 3);
});

test('notifications API: create admin announcement', async () => {
  const client = mockClient();
  client.write = async (method, path, body) => {
    client.calls.push({ method, path, body });
    return { success: true, recipients_count: 5, created_at: '2026-11-20T00:00:00Z' };
  };
  const res = await createAnnouncement({ title: 'Server Upgrade', body: 'Downtime at 00:00' }, { client });
  assert.equal(client.calls[0].method, 'POST');
  assert.equal(client.calls[0].path, '/admin/announcements');
  assert.equal(client.calls[0].body.title, 'Server Upgrade');
  assert.equal(res.success, true);
  assert.equal(res.recipients_count, 5);
});

test('notifications API: delete notification by id', async () => {
  const client = mockClient();
  const notifId = '11111111-1111-1111-1111-111111111111';
  client.write = async (method, path) => {
    client.calls.push({ method, path });
    return undefined;
  };
  await deleteNotification(notifId, { client });
  assert.equal(client.calls[0].method, 'DELETE');
  assert.equal(client.calls[0].path, `/notifications/${notifId}`);
});
