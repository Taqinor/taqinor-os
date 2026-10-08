/**
 * YBW40 — motif « trajectoire de flèche » : mesures relues dans le pack logo,
 * rendu décoratif (aria-hidden), aucune couleur hors jetons, animation coupée
 * sous prefers-reduced-motion et absente par défaut.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import TraitFleche from '../src/components/motif/TraitFleche.astro';
import ArcTrajectoire from '../src/components/motif/ArcTrajectoire.astro';
import { MESURES, RAPPORTS } from '../src/components/motif/mesures';
import { boiteDuTrace } from '../scripts/derive-logo-variants.mjs';

const PACK = fileURLToPath(new URL('../src/brand/svg/', import.meta.url));
const CSS = readFileSync(fileURLToPath(new URL('../src/components/motif/motif.css', import.meta.url)), 'utf-8');
const symbole = readFileSync(PACK + readdirSync(PACK).find((n) => n.endsWith('-symbol-colour.svg'))!, 'utf-8');
const trace = (couleur: string) => new RegExp(`fill="${couleur}" d="([^"]+)"`).exec(symbole)![1];
const COULEUR_BRUTE = /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/;

async function rendre(composant: Parameters<AstroContainer['renderToString']>[0], props: Record<string, unknown> = {}): Promise<Document> {
  const c = await AstroContainer.create();
  return new JSDOM(`<body>${await c.renderToString(composant, { props })}</body>`).window.document;
}

describe('YBW40 — mesures relues sur les tracés du logo', () => {
  it('fût de 36 (y 380 → 416), de x 97 à 423,46', () => {
    const fleche = trace('#C8762B');
    expect(fleche).toContain('L97 380L97 416L423.46 416');
    expect(fleche).toContain('423.46 380');
    expect(MESURES.fut).toEqual({ x0: 97, x1: 423.46, y0: 380, y1: 416, epaisseur: 36 });
  });

  it('pointe et B : boîtes englobantes exactes = mesures', () => {
    const b = boiteDuTrace(trace('#C8762B'));
    expect(b.x1).toBeCloseTo(MESURES.pointe.sommet, 1);
    expect(b.y0).toBeCloseTo(MESURES.pointe.y0, 1);
    expect(b.y1).toBeCloseTo(MESURES.pointe.y1, 1);
    const B = boiteDuTrace(trace('#1B1B1B'));
    expect(B.y1 - B.y0).toBeCloseTo(MESURES.hauteurB, 1);
    expect(trace('#1B1B1B')).toContain('L250 760C303.97 760');
    expect(trace('#1B1B1B')).toContain('453.5 556.5');
  });
});

describe('YBW40 — rendu', () => {
  it('trait de flèche : aria-hidden, non focalisable, proportions du logo, aucune couleur brute', async () => {
    const doc = await rendre(TraitFleche);
    const svg = doc.querySelector('svg[data-motif="trait-fleche"]')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('focusable')).toBe('false');
    expect(doc.querySelector('.motif-trait')?.getAttribute('stroke-width')).toBe('36');
    const [, , w, h] = svg.getAttribute('viewBox')!.split(' ').map(Number);
    expect(w).toBeCloseTo(9 * 36 + RAPPORTS.pointeSurFut * 36, 1);
    expect(h).toBeCloseTo(RAPPORTS.dosSurFut * 36, 1);
    expect(doc.body.innerHTML).not.toMatch(COULEUR_BRUTE);
    expect(svg.classList.contains('motif-anime')).toBe(false);
  });

  it('arc : aria-hidden, rayon = panse du B, aucune couleur brute', async () => {
    const doc = await rendre(ArcTrajectoire, { angle: 60 });
    const svg = doc.querySelector('svg[data-motif="arc"]')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(doc.querySelector('.motif-arc')?.getAttribute('d')).toContain(`A${RAPPORTS.panseSurFut * 36} ${RAPPORTS.panseSurFut * 36}`);
    expect(doc.body.innerHTML).not.toMatch(COULEUR_BRUTE);
  });

  it('animation seulement si demandée', async () => {
    const doc = await rendre(TraitFleche, { anime: true });
    expect(doc.querySelector('svg')?.classList.contains('motif-anime')).toBe(true);
  });

  it('angle hors bornes : erreur', async () => {
    await expect(rendre(ArcTrajectoire, { angle: 0 })).rejects.toThrow(/angle/);
  });
});

describe('YBW40 — feuille du motif', () => {
  it('aucune couleur hors jetons (var() / currentColor seulement)', () => {
    expect(CSS.replace(/\/\*[\s\S]*?\*\//g, '')).not.toMatch(COULEUR_BRUTE);
    expect(CSS).toMatch(/color: var\(--accent-graphique\)/);
  });

  it('prefers-reduced-motion : animation coupée, dessin complet', () => {
    const bloc = /@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/.exec(CSS)?.[1] ?? '';
    expect(bloc).toMatch(/animation: none/);
    expect(bloc).toMatch(/stroke-dashoffset: 0/);
  });
});
