import axios from 'axios';

export interface BlogPost {
  id: number;
  title: string;
  content: string;
  author: string;
  createdAt: string;
}

export type PostInput = Pick<BlogPost, 'title' | 'content' | 'author'>;

const api = axios.create({ baseURL: 'http://localhost:5080/api/posts', timeout: 10000 });

export async function getPosts(signal?: AbortSignal): Promise<BlogPost[]> {
  const response = await api.get<BlogPost[]>('', { signal });
  return response.data;
}

export async function getPost(id: number): Promise<BlogPost> {
  const response = await api.get<BlogPost>(`/${id}`);
  return response.data;
}

export async function createPost(data: PostInput): Promise<BlogPost> {
  const response = await api.post<BlogPost>('', data);
  return response.data;
}

export async function updatePost(id: number, data: PostInput): Promise<void> {
  await api.put(`/${id}`, data);
}

export async function deletePost(id: number): Promise<void> {
  await api.delete(`/${id}`);
}
