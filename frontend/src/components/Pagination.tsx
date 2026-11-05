import type { Page } from '../blog';

export function Pagination({ value, onPage }: { value: Page<unknown>['pagination']; onPage: (page: number) => void }) {
  return <nav aria-label="Pagination" className="flex flex-wrap items-center justify-center gap-4 py-5 text-sm">
    <button className="min-h-11 px-3 rounded-lg bg-surface-container disabled:opacity-40" disabled={value.page <= 1} onClick={() => onPage(value.page - 1)}>Previous page</button>
    <span>Page {value.page} · {value.total} results</span>
    <button className="min-h-11 px-3 rounded-lg bg-surface-container disabled:opacity-40" disabled={value.page >= value.total_pages} onClick={() => onPage(value.page + 1)}>Next page</button>
  </nav>;
}
