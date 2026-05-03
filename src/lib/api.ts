import type { BlogPost, BlogCategory, Advertisement } from './types';

const API_URL = 'https://api.curitibasoftware.com.br';
const SITE_ID = 'blogdudu';

function sanitizePost(post: BlogPost): BlogPost {
  return {
    ...post,
    content:    post.content    ?? '',
    summary:    post.summary    ?? '',
    tags:       Array.isArray(post.tags)       ? post.tags       : [],
    categories: Array.isArray(post.categories) ? post.categories : [],
    faqs:       Array.isArray(post.faqs)       ? post.faqs       : [],
    blocks:     Array.isArray(post.blocks)     ? post.blocks     : [],
  };
}

async function apiFetch<T>(path: string, params?: Record<string, string | number>): Promise<T | null> {
  try {
    const url = new URL(`${API_URL}${path}`);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
    }
    const res = await fetch(url.toString(), { signal: AbortSignal.timeout(15000) });
    if (!res.ok) return null;
    const data = await res.json();
    return data.success ? data.data : null;
  } catch (err) {
    console.error(`[api] fetchError ${path}:`, err);
    return null;
  }
}

export async function fetchAllPosts(): Promise<BlogPost[]> {
  let page = 1;
  const pageSize = 100;
  const all: BlogPost[] = [];

  while (true) {
    const data = await apiFetch<{ items: BlogPost[]; total: number }>(
      '/api/blog/posts', { page, pageSize, site: SITE_ID }
    );
    if (!data?.items?.length) break;
    all.push(...data.items.map(sanitizePost));
    if (data.items.length < pageSize) break;
    page++;
  }

  return all.filter(p => p.isPublished);
}

export async function fetchCategories(): Promise<BlogCategory[]> {
  return (await apiFetch<BlogCategory[]>('/api/blog/categories')) ?? [];
}

export async function fetchAds(position: string): Promise<Advertisement[]> {
  return (await apiFetch<Advertisement[]>(`/api/advertisement/active/${position}`)) ?? [];
}

export async function fetchRelatedPosts(postId: string): Promise<BlogPost[]> {
  return (await apiFetch<BlogPost[]>(`/api/blog/posts/${postId}/related`)) ?? [];
}
