import { describe, expect, it } from 'vitest';
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
