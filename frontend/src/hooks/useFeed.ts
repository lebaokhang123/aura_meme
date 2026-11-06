import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { Category, Page, Post } from '../blog';
import { useResource } from './useResource';

export function useCategories(endpoint: string | null = '/categories') {
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Category[]>([]);
  const [totalPages, setTotalPages] = useState(0);
  const resource = useResource<Page<Category>>(endpoint ? endpoint + '?page=' + page + '&page_size=100' : null);
  useEffect(() => {
    if (resource.data) {
      setItems(previous => [...new Map([...previous, ...resource.data!.items].map(item => [item.id, item])).values()]);
      setTotalPages(resource.data.pagination.total_pages);
    }
  }, [resource.data]);
  return { ...resource, items, hasPages: totalPages > 1, more: page < totalPages,
    loadMore: () => { if (!resource.pending && page < totalPages) setPage(value => value + 1); } };
}

export function useFeed() {
  const [params, setParams] = useSearchParams();
  const categories = useCategories();
  const query = new URLSearchParams({ page: params.get('page') || '1', page_size: '20', sort: params.get('sort') || 'created_desc' });
  for (const key of ['search', 'category']) if (params.get(key)) query.set(key, params.get(key)!);
  const posts = useResource<Page<Post>>('/posts?' + query);
  const update = (values: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(values)) value ? next.set(key, value) : next.delete(key);
    setParams(next);
  };
  return { ...posts, categories, params, update };
}
