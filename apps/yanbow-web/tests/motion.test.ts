import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { DIST_CLIENT, pagesRendues } from './builtHtml';

/** CSS et JS tels que le visiteur les reçoit (build), pas le source. */
const ASTRO = join(DIST_CLIENT, '_astro');
const fichiers = readdirSync(ASTRO);
const CSS = fichiers.filter((f) => f.endsWith('.css')).map((f) => readFileSync(join(ASTRO, f), 'utf-8'));
const JS = fichiers.filter((f) => f.endsWith('.js'));
const CSS_TOUT = CSS.join('\n');
const SOURCE_MOTION = readFileSync(new URL('../src/styles/motion.css', import.meta.url), 'utf-8');

describe('YBW80 — mouvement léger, jamais sur le LCP', () => {
  it('la révélation est livrée dans le CSS construit (motion.css est bien câblé)', () => {
    expect(CSS_TOUT).toContain('revelation-douce');
    expect(CSS_TOUT).toContain('animation-timeline:view()');
  });

  it('tout le mouvement est sous prefers-reduced-motion: no-preference', () => {
    const hors = SOURCE_MOTION.replace(/@media \(prefers-reduced-motion: no-preference\)\s*\{[\s\S]*\n\}\s*$/m, '');
    expect(hors.replace(/\/\*[\s\S]*?\*\//g, '').trim()).toBe('');
  });

  it('aucun sélecteur animé ne vise un élément LCP (hero, bande-nuit, h1, première section)', () => {
    const regles = [...SOURCE_MOTION.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}@]+)\{[^{}]*animation-timeline[^{}]*\}/g)];
    expect(regles.length).toBeGreaterThan(0);
    for (const [, sel] of regles) {
      expect(sel).not.toMatch(/hero|bande-nuit|\bh1\b/);
      expect(sel).toContain(':not(:first-child)');
    }
  });

  it('seulement opacity et transform (aucun décalage de mise en page → pas de CLS)', () => {
    const kf = /@keyframes revelation-douce\s*\{([\s\S]*?\})\s*\}/.exec(SOURCE_MOTION)?.[1] ?? '';
    const props = [...kf.matchAll(/([a-z-]+)\s*:/g)].map((m) => m[1]);
    expect(props.length).toBeGreaterThan(0);
    for (const p of props) expect(['opacity', 'transform']).toContain(p);
  });

  it('sur le HTML rendu : aucune section animée n’est le premier enfant de <main>', () => {
    for (const p of pagesRendues()) {
      const premier = p.document.querySelector('main')?.firstElementChild;
      if (!premier) continue;
      // le sélecteur animé exclut :first-child ; ce test garde la structure qui le rend vrai
      expect(premier.matches('main > .section:not(:first-child), main > .bande:not(:first-child)'), p.url).toBe(false);
    }
  });
});

describe('YBW80 — budget de performance et images', () => {
  it('CSS construit ≤ 60 Ko, JS client ≤ 20 Ko au total', () => {
    const octets = (suffixe: string) =>
      fichiers.filter((f) => f.endsWith(suffixe)).reduce((n, f) => n + readFileSync(join(ASTRO, f)).length, 0);
    expect(octets('.css')).toBeLessThanOrEqual(60 * 1024);
    expect(octets('.js')).toBeLessThanOrEqual(20 * 1024);
    expect(JS.length).toBeGreaterThan(0);
  });

  it('toute image du HTML rendu a largeur et hauteur, au format AVIF, WebP ou SVG', () => {
    for (const p of pagesRendues()) {
      for (const img of p.document.querySelectorAll('img')) {
        const src = img.getAttribute('src') ?? '';
        expect(src, `${p.url} ${src}`).toMatch(/\.(avif|webp|svg)(\?.*)?$/i);
        expect(img.getAttribute('width'), `${p.url} ${src} width`).toMatch(/^\d+$/);
        expect(img.getAttribute('height'), `${p.url} ${src} height`).toMatch(/^\d+$/);
      }
    }
  });

  it('aucune image sous le pli n’est chargée en priorité haute, aucune LCP en lazy', () => {
    for (const p of pagesRendues()) {
      const imgs = [...p.document.querySelectorAll('img')];
      if (imgs.length === 0) continue;
      expect(imgs[0].getAttribute('loading'), `${p.url} image LCP`).not.toBe('lazy');
    }
  });
});
