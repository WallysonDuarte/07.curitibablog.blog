import type { PostBlock, Section } from './types';

export function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('pt-BR', {
    day: '2-digit', month: 'long', year: 'numeric',
  });
}

export function toSlug(name: string): string {
  return name.toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '').trim()
    .replace(/\s+/g, '-').replace(/-+/g, '-');
}

export function buildSections(content: string, blocks: PostBlock[]): Section[] {
  const parts = content.split(/(?=<h3)/i);
  const blocksBySectionIdx: Record<number, PostBlock[]> = {};
  const floatingBlocks: PostBlock[] = [];

  blocks.forEach((block) => {
    const insertAfter = block.data?.insertAfterSection;
    if (typeof insertAfter === 'number') {
      if (!blocksBySectionIdx[insertAfter]) blocksBySectionIdx[insertAfter] = [];
      blocksBySectionIdx[insertAfter].push(block);
    } else {
      floatingBlocks.push(block);
    }
  });

  const total = parts.length;
  const adPositions = new Set(
    [Math.floor(total / 3), Math.floor(2 * total / 3)].filter(p => p > 0 && p < total)
  );

  const sections: Section[] = parts.map((sectionContent, sectionIdx) => {
    const inlineBlocks = blocksBySectionIdx[sectionIdx] || [];
    const showAd = adPositions.has(sectionIdx) && inlineBlocks.length === 0 && sectionIdx < total - 1;
    return { content: sectionContent, inlineBlocks, sectionIdx, showAd };
  });

  if (floatingBlocks.length > 0) {
    sections.push({ content: '', inlineBlocks: floatingBlocks, sectionIdx: -1, showAd: false });
  }

  return sections;
}

export function getPostCategories(post: { categories?: string[]; category: string }): string[] {
  return post.categories?.length ? post.categories : (post.category ? [post.category] : []);
}
