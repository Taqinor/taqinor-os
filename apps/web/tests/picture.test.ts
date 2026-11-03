import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { intrinsicHeight, largestWidth, photoSrcset } from '../src/lib/picture';

describe('photoSrcset', () => {
  it('construit un srcset trié par largeur croissante', () => {
    expect(photoSrcset('hero-skyline', [2000, 480, 1280], 'avif')).toBe(
      '/photos/hero-skyline-480.avif 480w, /photos/hero-skyline-1280.avif 1280w, /photos/hero-skyline-2000.avif 2000w',
    );
  });

  it('respecte le format demandé', () => {
    expect(photoSrcset('villa-zellige', [640], 'webp')).toBe('/photos/villa-zellige-640.webp 640w');
  });
});

describe('largestWidth', () => {
  it('retourne la plus grande largeur quelle que soit l’entrée', () => {
    expect(largestWidth([640, 1600, 1024])).toBe(1600);
  });
});

describe('intrinsicHeight', () => {
  it('calcule la hauteur 16/9', () => {
    expect(intrinsicHeight(1600, 16 / 9)).toBe(900);
  });
  it('calcule la hauteur 4/3', () => {
    expect(intrinsicHeight(1024, 4 / 3)).toBe(768);
  });
  it('reste exacte pour un cadrage carré', () => {
    expect(intrinsicHeight(640, 1)).toBe(640);
  });
});

describe('WAUD29 — LCP de l’accueil', () => {
  const src = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
  const ACCUEILS = ['../src/pages/index.astro', '../src/pages/en/index.astro', '../src/pages/ar/index.astro'];

  it('la vidéo cachée ne télécharge plus d’affiche avant le LCP', () => {
    expect(src('../src/components/VideoChantier.astro')).not.toContain('poster="/videos/chantier-poster.webp"');
  });

  it('police préchargée en priorité basse, affiche héros en priorité haute', () => {
    const layout = src('../src/layouts/Layout.astro');
    expect(layout).toMatch(/archivo-latin\.woff2" fetchpriority="low"/);
    expect(layout).toMatch(/as="image"\s+type="image\/avif"\s+fetchpriority="high"/);
    expect(src('../src/components/blocs/ArIndexPicture8B05.astro')).toContain('fetchpriority="high"');
  });

  it('galerie : variante 768w réelle et sizes qui tient compte du padding', () => {
    for (const page of ACCUEILS) {
      const code = src(page);
      expect(code).toContain('calc(100vw - 2rem)');
      const bloc = code.slice(code.indexOf('const galleryRaw = ['), code.indexOf('const gallery = buildGallery'));
      const noms = [...bloc.matchAll(/name: '([^']+)'[^\n]*widths: \[([^\]]+)\]/g)];
      expect(noms.length).toBeGreaterThan(0);
      for (const [, nom, largeurs] of noms) {
        expect(largeurs.split(',').map(Number)).toContain(768);
        for (const ext of ['avif', 'webp']) {
          expect(existsSync(fileURLToPath(new URL(`../public/photos/${nom}-768.${ext}`, import.meta.url)))).toBe(true);
        }
      }
    }
  });
});
