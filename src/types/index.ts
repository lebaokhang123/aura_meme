export interface UserProfile {
  id: string;
  name: string;
  username: string;
  email: string;
  avatar: string;
  auraBalance: number;
  streakDays: number;
  multiplier: number;
  isNitro: boolean;
  role: string;
  rankTitle: string;
}

export interface MemePost {
  id: string;
  author: {
    name: string;
    username: string;
    avatar?: string;
    initials: string;
    avatarBg: string;
    level: number;
    rankTitle: string;
  };
  title: string;
  imageUrl: string;
  imageAlt?: string;
  captionText?: string;
  captionBadge?: string;
  buildMeta?: string;
  category: 'Gaming' | 'Anime' | 'Technology' | 'School' | 'Random';
  timeAgo: string;
  reactions: {
    like: number;
    laugh: number;
    fire: number;
    clown: number;
  };
  userReactions: {
    like?: boolean;
    laugh?: boolean;
    fire?: boolean;
    clown?: boolean;
  };
  commentsCount: number;
  sharesCount: number;
  auraAwarded: number;
  userAwardedAura?: boolean;
  isBookmarked?: boolean;
}
