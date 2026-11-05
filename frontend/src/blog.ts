export interface Category { id: string; name: string; slug: string; status: string }
export interface Author { id: string; username: string; display_name: string }
export interface Post {
  id: string; title: string; content: string; author: Author; category: Category; media_url: string | null;
  status: 'draft' | 'published' | 'hidden' | 'deleted'; created_at: string; updated_at: string;
}
export interface Comment { id: string; post_id: string; author: Author; body: string; created_at: string }
export interface OwnPost extends Post { media_id: string | null }
export interface Page<T> { items: T[]; pagination: { page: number; page_size: number; total: number; total_pages: number } }
