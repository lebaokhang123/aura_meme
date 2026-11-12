import { test } from 'node:test';
import assert from 'node:assert/strict';
import { POSTS, CATEGORIES, readFilters, selectPosts } from '../src/feed-data.js';

test('three original posts: New defaults to source recency, Hot totals existing reactions', () => {
  assert.equal(POSTS.length, 3);
  assert.equal(CATEGORIES.length, 5);
  assert.deepEqual(selectPosts(readFilters('')).map(p => p.id), ['khang', 'kien', 'gigachad']);
  assert.deepEqual(selectPosts(readFilters('?sort=hot')).map(p => p.id), ['gigachad', 'kien', 'khang']);
  assert.deepEqual(POSTS.map(p => p.reactions.reduce((a, b) => a + b, 0)), [732, 818, 960]);
});
test('combined filters search only post content, normalize Vietnamese and handle empty/invalid input', () => {
  assert.deepEqual(selectPosts(readFilters('?category=Gaming&q=production&sort=hot')).map(p => p.id), ['khang']);
  assert.equal(selectPosts(readFilters('?category=Anime&q=production')).length, 0);
  assert.equal(selectPosts(readFilters('?category=Random')).length, 0);
  assert.deepEqual(CATEGORIES.map(c => selectPosts(readFilters(`?category=${c.id}`)).length), [1, 1, 1, 0, 0]);
  assert.equal(selectPosts(readFilters('?q=cuoc%20doi%20lap%20trinh')).length, 1);
  assert.equal(selectPosts(readFilters('?q=Khang%20Dev')).length, 0);
  assert.deepEqual(readFilters('?category=invalid&sort=top'), { category: '', q: '', sort: 'new' });
});
