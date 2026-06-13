// Garde-fous de l'élévation « élégance retenue » promue en production
// (2026-06-13) : les pages publiques principales montent le moteur de
// mouvement, restent indexables, et la couche photo (Ken Burns + montée
// d'échelle) reste gated mouvement/JS. Les routes de prévisualisation /v2 et
// /v3 ont été supprimées.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const pagesDir = fileURLToPath(new URL('../src/pages', import.meta.url));
const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Les 7 pages élevées (les 2 pages légales restent volontairement sobres).
const ELEVATED = [
  'index',
  'contact',
  'loi-82-21',
  'professionnel',
  'regularization-article-33',
  'résidentiel',
  'équipement',
];

describe('élévation — pages publiques', () => {
  for (const p of ELEVATED) {
    it(`/${p} monte le moteur d'élévation et reste indexable`, () => {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: V2Enhance`).toContain('V2Enhance');
      expect(src, `${p}: wrapper .v2`).toContain('class="v2"');
      // Page publique : surtout PAS de noindex (régression d'indexation).
      expect(src, `${p}: pas de noindex`).not.toContain('noindex');
    });
  }
});

describe('élévation — mouvement photo global et sûr', () => {
  it('V2Enhance importe la couche photo (active sur toute page élevée)', () => {
    const enhance = read('../src/components/V2Enhance.astro');
    expect(enhance).toContain('v3-photo-motion.css');
  });

  it('la couche photo ne bouge que sous JS ET hors prefers-reduced-motion', () => {
    const css = read('../src/styles/v3-photo-motion.css');
    expect(css).toContain('prefers-reduced-motion: no-preference');
    expect(css).toContain('.v2-js .v2-hero-media'); // Ken Burns
    expect(css).toContain('.v2-js .v2-rise > picture'); // montée d'échelle
    // transform/opacity uniquement → zéro CLS (aucune propriété de reflow).
    expect(css).not.toMatch(/\b(top|left|width|height|margin)\s*:/);
  });
});

describe('prévisualisations supprimées', () => {
  it('les dossiers /v2 et /v3 n\'existent plus', () => {
    expect(existsSync(`${pagesDir}/v2`)).toBe(false);
    expect(existsSync(`${pagesDir}/v3`)).toBe(false);
    const slugs = readdirSync(pagesDir).filter((f) => f.endsWith('.astro'));
    expect(slugs.length).toBe(9); // 7 élevées + 2 légales
  });

  it('le filtre sitemap ne référence plus /v2 ni /v3', () => {
    const config = read('../astro.config.mjs');
    const filterLine = config.split('\n').find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).not.toContain('v2');
    expect(filterLine).not.toContain('v3');
  });
});
