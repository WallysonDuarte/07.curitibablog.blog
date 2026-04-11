import rss from '@astrojs/rss';
import { fetchAllPosts } from '../lib/api';

export async function GET(context) {
  const posts = await fetchAllPosts();
  const sorted = posts.sort(
    (a, b) => new Date(b.publishedAt || b.createdAt).getTime() - new Date(a.publishedAt || a.createdAt).getTime()
  );

  return rss({
    title: 'CuritibaBlog',
    description: 'Guias sobre parques, turismo, gastronomia e tudo o que fazer em Curitiba.',
    site: context.site,
    items: sorted.slice(0, 50).map(post => ({
      title: post.title,
      pubDate: new Date(post.publishedAt || post.createdAt),
      description: post.summary,
      link: `/${post.slug}`,
      categories: post.categories?.length ? post.categories : [post.category],
    })),
    customData: '<language>pt-BR</language>',
  });
}
