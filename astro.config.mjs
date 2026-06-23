// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: process.env.PUBLIC_SITE_URL || 'https://curitibablog.com.br',
  integrations: [sitemap({ filter: (page) => !page.includes('/tag/') })],
  output: 'static',
  build: { inlineStylesheets: 'always' },
});
