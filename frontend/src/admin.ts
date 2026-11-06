import type { Author, Category } from './blog';

export type AdminTab = 'users' | 'posts' | 'categories' | 'contacts' | 'audit-logs';
export interface AdminRow {
  id: string; username?: string; email?: string; display_name?: string; roles?: ('USER' | 'ADMIN')[];
  status?: string; title?: string; content?: string; author?: Author; category?: Category;
  name?: string; slug?: string; subject?: string; body?: string; created_at?: string;
  actor_id?: string; action?: string; target_type?: string; target_id?: string;
}
