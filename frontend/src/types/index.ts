// Presentation fixtures, deliberately separate from future API/session types.
export interface DemoPost {
  id: string;
  author: { username: string; initials: string; avatarBg: string };
  title: string;
  imageUrl: string;
  imageAlt: string;
  captionBadge: string;
  category: 'Gaming' | 'Anime' | 'Technology' | 'School' | 'Random';
  reactions: { like: number; laugh: number; fire: number };
  commentsCount: number;
}
