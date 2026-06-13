// Garde-fous de la prévisualisation privée v2 : noindex + exclusion sitemap.
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const v2Dir = fileURLToPath(new URL('../src/pages/v2', import.meta.url));
const pages = readdirSync(v2Dir).filter((f) => f.endsWith('.astro'));

describe('prévisualisation v2 — confidentialité', () => {
  it('les 7 pages /v2 existent et sont toutes en noindex', () => {
    expect(pages.length).toBe(7);
    for (const p of pages) {
      const src = readFileSync(`${v2Dir}/${p}`, 'utf-8');
      expect(src, p).toContain('noindex');
    }
  });

  it('le filtre sitemap exclut les routes /v2', () => {
    const config = readFileSync(fileURLToPath(new URL('../astro.config.mjs', import.meta.url)), 'utf-8');
    expect(config).toContain('/v2');
  });
});
