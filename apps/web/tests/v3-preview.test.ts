// Garde-fous de la prévisualisation privée v3 (probe mouvement photo) :
// noindex + exclusion sitemap + couche de mouvement isolée (ni /v2 ni le
// public ne sont touchés).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('prévisualisation v3 — confidentialité', () => {
  it('la page /v3 existe et est en noindex', () => {
    const src = read('../src/pages/v3/index.astro');
    expect(src).toContain('noindex');
  });

  it('le filtre sitemap exclut les routes /v3', () => {
    const config = read('../astro.config.mjs');
    expect(config).toContain('/v3');
    // La règle reste celle d'un préfixe de route (\/v3(\/|$)), comme pour v2.
    expect(config).toMatch(/\\\/v3\(\\\/\|\$\)/);
  });
});

describe('prévisualisation v3 — mouvement isolé', () => {
  it("réutilise le moteur de mouvement v2 (V2Enhance) et n'ajoute que la couche delta v3", () => {
    const src = read('../src/pages/v3/index.astro');
    expect(src).toContain('V2Enhance');
    expect(src).toContain('v3-photo-motion.css');
  });

  it('la couche v3 ne bouge que sous JS ET hors prefers-reduced-motion', () => {
    const css = read('../src/styles/v3-photo-motion.css');
    // Les deux règles de mouvement (Ken Burns + montée d'échelle) sont gated.
    expect(css).toContain('prefers-reduced-motion: no-preference');
    expect(css).toContain('.v2-js .v2-hero-media');
    expect(css).toContain('.v2-js .v3-photo');
    // Mouvement par transform/opacity uniquement (zéro CLS, pas de propriété
    // déclenchant un reflow).
    expect(css).not.toMatch(/\b(top|left|width|height|margin)\s*:/);
  });
});
