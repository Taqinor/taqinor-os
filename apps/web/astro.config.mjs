// @ts-check
import { defineConfig } from 'astro/config';

import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://taqinor.ma',
  adapter: cloudflare(),

  vite: {
    plugins: [tailwindcss()]
  },

  integrations: [
    sitemap({
      // Pages de travail privées (comparatifs typo/média) — jamais indexées
      filter: (page) => !page.includes('type-test') && !page.includes('media-test')
    })
  ]
});