import posts from './feed-posts.json' with { type: 'json' };

export const POSTS = posts;
export const CATEGORIES = [
  { id: 'Gaming', label: 'Gaming', icon: 'sports_esports' },
  { id: 'Anime', label: 'Anime', icon: 'movie_filter' },
  { id: 'CongNghe', label: 'Công nghệ', icon: 'terminal' },
  { id: 'TruongHoc', label: 'Trường học', icon: 'school' },
  { id: 'Random', label: 'Random', icon: 'casino' },
];
export function readFilters(search) {
  const params = new URLSearchParams(search);
  return { category: CATEGORIES.some(c => c.id === params.get('category')) ? params.get('category') : '',
    q: (params.get('q') || '').trim(), sort: params.get('sort') === 'hot' ? 'hot' : 'new' };
}
const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();
export function selectPosts({ category, q, sort }, posts = POSTS) {
  const query = normalize(q);
  const total = post => post.reactions.reduce((sum, count) => sum + count, 0);
  return posts.filter(post => (!category || post.category === category) && normalize(`${post.title} ${post.content}`).includes(query))
    .sort((a, b) => (sort === 'hot' ? total(b) - total(a) : 0) || a.ageMinutes - b.ageMinutes || a.id.localeCompare(b.id));
}
export function filterUrl(path, filters, hash = '') {
  const url = new URL(path, location.origin);
  for (const key of ['category', 'q', 'sort']) {
    if (filters[key] && !(key === 'sort' && filters[key] === 'new')) url.searchParams.set(key, filters[key]);
    else url.searchParams.delete(key);
  }
  url.hash = hash;
  return url.pathname + url.search + url.hash;
}
