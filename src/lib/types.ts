export interface FaqItem {
  question: string;
  answer: string;
}

export type PostBlockType =
  | 'map' | 'gallery' | 'reviews' | 'info' | 'links'
  | 'video' | 'youtube-gallery' | 'instagram' | 'facebook';

export interface PostBlock {
  type: PostBlockType;
  label?: string;
  data: any;
}

export interface BlogPost {
  id: string;
  title: string;
  slug: string;
  summary: string;
  content: string;
  coverImageUrl?: string;
  tags: string[];
  category: string;
  categories?: string[];
  authorId: string;
  authorName: string;
  isPublished: boolean;
  publishedAt?: string;
  views: number;
  metaTitle?: string;
  metaDescription?: string;
  faqs?: FaqItem[];
  blocks?: PostBlock[];
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  podcastUrl?: string;
  youtubeVideoId?: string;
}

export interface BlogCategory {
  id: string;
  name: string;
  slug: string;
  description?: string;
  order: number;
  postCount: number;
}

export interface Advertisement {
  id: string;
  title: string;
  imageUrl?: string;
  destinationUrl: string;
  position: 'inline' | 'sidebar' | 'faq-side';
  advertiserName: string;
  startDate?: string;
  endDate?: string;
  clickCount: number;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Section {
  content: string;
  inlineBlocks: PostBlock[];
  sectionIdx: number;
  showAd: boolean;
}
