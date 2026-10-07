/**
 * YBW36 — variantes web DÉRIVÉES du pack (aucun tracé modifié) + composant Logo.
 * Preuve visuelle : rendu raster à 180 et 120 px, le fût de la flèche est
 * mesuré (et les captures zoomées sont écrites dans test-results/, non versionné).
 */
import { mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import sharp from 'sharp';
import { describe, expect, it } from 'vitest';
import Logo from '../src/components/Logo.astro';
import { boiteDuTrace, deriver } from '../scripts/derive-logo-variants.mjs';

const SOURCE = fileURLToPath(new URL('../src/brand/svg/', import.meta.url));
const DERIVES = fileURLToPath(new URL('../src/brand/derived/', import.meta.url));
const CAPTURES = fileURLToPath(new URL('../test-results/logo/', import.meta.url));
const noms = readdirSync(SOURCE).filter((n) => n.endsWith('.svg')).sort();
const traces = (svg: string) => [...svg.matchAll(/ d="([^"]+)"/g)].map((m) => m[1]);

describe('YBW36 — dérivés fidèles au pack', () => {
  it('un dérivé par fichier du pack', () => {
    expect(readdirSync(DERIVES).filter((n) => n.endsWith('.svg')).sort()).toEqual(noms);
  });

  for (const nom of noms) {
    it(`${nom} : à jour, mêmes attributs d (même ordre), aucun rectangle`, () => {
      const source = readFileSync(SOURCE + nom, 'utf-8');
      const derive = readFileSync(DERIVES + nom, 'utf-8');
      expect(derive).toBe(deriver(source));
      expect(traces(derive)).toEqual(traces(source));
      expect(derive).not.toMatch(/<rect\b/);
      expect(derive).not.toMatch(/<text\b/);
      if (nom.includes('reversed')) expect(source).toMatch(/<rect\b/);
    });
  }

  it('la viewBox resserrée contient chaque tracé (rien n’est rogné)', () => {
    for (const nom of noms) {
      const derive = readFileSync(DERIVES + nom, 'utf-8');
      const [vx, vy, vw, vh] = /viewBox="([^"]+)"/.exec(derive)![1].split(' ').map(Number);
      const t = /translate\(([-\d.]+) ([-\d.]+)\)/.exec(derive);
      const [tx, ty] = t ? [Number(t[1]), Number(t[2])] : [0, 0];
      for (const d of traces(derive)) {
        const b = boiteDuTrace(d);
        expect(b.x0 + tx).toBeGreaterThanOrEqual(vx - 1e-9);
        expect(b.y0 + ty).toBeGreaterThanOrEqual(vy - 1e-9);
        expect(b.x1 + tx).toBeLessThanOrEqual(vx + vw + 0.011);
        expect(b.y1 + ty).toBeLessThanOrEqual(vy + vh + 0.011);
      }
    }
  });

  it('couleurs exposées : --logo-arrow sur la flèche orange, --logo-ink ailleurs', () => {
    const d = readFileSync(DERIVES + noms.find((n) => n.endsWith('wordmark-colour.svg'))!, 'utf-8');
    expect(d).toContain('style="fill:var(--logo-arrow,#C8762B)"');
    expect(d).toContain('style="fill:var(--logo-ink,#1B1B1B)"');
  });
});

/** Plus longue suite horizontale de pixels « orange » d'une image RGBA aplatie sur blanc. */
async function fut(svg: Buffer, largeur: number, capture: string): Promise<{ longueur: number; epaisseur: number }> {
  const img = sharp(svg).resize({ width: largeur }).flatten({ background: '#ffffff' });
  const { data, info } = await img.clone().raw().toBuffer({ resolveWithObject: true });
  mkdirSync(CAPTURES, { recursive: true });
  await img.clone().resize({ width: largeur * 6, kernel: 'nearest' }).png().toFile(CAPTURES + capture);
  const orange = (i: number) => data[i] - data[i + 2] > 60 && data[i] - data[i + 1] > 30;
  let longueur = 0;
  const lignes: number[] = [];
  for (let y = 0; y < info.height; y++) {
    let run = 0;
    let max = 0;
    for (let x = 0; x < info.width; x++) {
      run = orange((y * info.width + x) * info.channels) ? run + 1 : 0;
      max = Math.max(max, run);
    }
    longueur = Math.max(longueur, max);
    lignes.push(max);
  }
  const epaisseur = lignes.filter((m) => m >= longueur * 0.5).length;
  return { longueur, epaisseur };
}

describe('YBW36 — le fût de la flèche reste visible (rendu raster zoomé)', () => {
  const fichier = (suffixe: string) => readFileSync(DERIVES + noms.find((n) => n.endsWith(suffixe))!);
  for (const largeur of [180, 120]) {
    it(`nom à ${largeur} px : fût orange continu`, async () => {
      const { longueur, epaisseur } = await fut(fichier('wordmark-colour.svg'), largeur, `nom-${largeur}.png`);
      expect(longueur).toBeGreaterThanOrEqual(Math.round(largeur * 0.06));
      expect(epaisseur).toBeGreaterThanOrEqual(1);
    });
    it(`symbole à ${largeur} px : fût orange continu et épais`, async () => {
      const { longueur, epaisseur } = await fut(fichier('symbol-colour.svg'), largeur, `symbole-${largeur}.png`);
      expect(longueur).toBeGreaterThanOrEqual(Math.round(largeur * 0.4));
      expect(epaisseur).toBeGreaterThanOrEqual(3);
    });
  }
});

async function rendre(props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  return new JSDOM(`<body>${await container.renderToString(Logo, { props })}</body>`).window.document;
}

describe('YBW36 — composant Logo', () => {
  it('nom sur clair : SVG en ligne masqué aux lecteurs, nom accessible = la marque', async () => {
    const doc = await rendre({ variante: 'nom', taille: 200 });
    const svg = doc.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('data-logo-cle')).toBe('wordmark-colour');
    expect(svg.getAttribute('width')).toBe('200');
    expect(doc.querySelector('.logo-texte')?.textContent).toBe('YanBow');
  });

  it('sur fond sombre : variante reversed SANS rectangle', async () => {
    const doc = await rendre({ variante: 'nom', taille: 200, fond: 'sombre' });
    expect(doc.querySelector('svg')?.getAttribute('data-logo-cle')).toBe('wordmark-reversed');
    expect(doc.querySelector('rect')).toBeNull();
  });

  it('symbole : bascule automatique sur la coupe small sous 64 px, favicon à 32 px et moins', async () => {
    const cle = async (taille: number) => (await rendre({ variante: 'symbole', taille })).querySelector('svg')?.getAttribute('data-logo-cle');
    expect(await cle(96)).toBe('symbol-colour');
    expect(await cle(64)).toBe('symbol-colour');
    expect(await cle(63)).toBe('symbol-small-colour');
    expect(await cle(40)).toBe('symbol-small-colour');
    expect(await cle(32)).toBe('favicon16-colour');
  });

  it('slogan : texte réel dans la langue de la page', async () => {
    const doc = await rendre({ variante: 'slogan', taille: 480, locale: 'en' });
    const texte = doc.querySelector('.logo-texte')!;
    expect(texte.textContent).toBe('YanBow — Your Arrow Needs 1Bow');
    expect(texte.getAttribute('lang')).toBe('en');
  });

  it('sous le minimum : erreur (nom < 180, slogan < 420)', async () => {
    await expect(rendre({ variante: 'nom', taille: 120 })).rejects.toThrow(/180/);
    await expect(rendre({ variante: 'slogan', taille: 400 })).rejects.toThrow(/420/);
  });
});
