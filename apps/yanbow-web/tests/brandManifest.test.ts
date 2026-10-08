/**
 * YBW35 — le pack logo est une copie à l'octet : empreintes recalculées =
 * MANIFEST.json ; aucun `<text>` dans un SVG (contours purs, aucune police).
 */
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const BRAND = fileURLToPath(new URL('../src/brand/', import.meta.url));
interface Entree {
  sha256: string;
  octets: number;
  viewBox?: string;
  couleurs?: string[];
  largeur?: number;
  hauteur?: number;
}
const manifest = JSON.parse(readFileSync(BRAND + 'MANIFEST.json', 'utf-8')) as { fichiers: Record<string, Entree> };

const fichiersDuPack = (): string[] =>
  ['svg', 'png'].flatMap((d) => readdirSync(BRAND + d).filter((n) => n.endsWith(`.${d}`)).map((n) => `${d}/${n}`)).sort();

/** `<text>` (ou `<tspan>`/`<textPath>`) dans un SVG : interdit. */
export function contientTexte(svg: string): boolean {
  return /<(text|tspan|textPath)\b/i.test(svg);
}

describe('YBW35 — manifeste du pack', () => {
  it('17 SVG + 7 PNG, exactement les fichiers du manifeste', () => {
    const presents = fichiersDuPack();
    expect(presents.filter((f) => f.startsWith('svg/'))).toHaveLength(17);
    expect(presents.filter((f) => f.startsWith('png/'))).toHaveLength(7);
    expect(presents).toEqual(Object.keys(manifest.fichiers).sort());
  });

  for (const [fichier, e] of Object.entries(manifest.fichiers)) {
    it(`${fichier} : empreinte SHA-256 et taille identiques au manifeste`, () => {
      const buf = readFileSync(BRAND + fichier);
      expect(buf.length).toBe(e.octets);
      expect(createHash('sha256').update(buf).digest('hex')).toBe(e.sha256);
    });
  }

  it('chaque SVG : viewBox et couleurs du manifeste, aucun <text>', () => {
    for (const [fichier, e] of Object.entries(manifest.fichiers)) {
      if (!fichier.startsWith('svg/')) continue;
      const svg = readFileSync(BRAND + fichier, 'utf-8');
      expect(contientTexte(svg), fichier).toBe(false);
      expect(/viewBox="([^"]+)"/.exec(svg)?.[1]).toBe(e.viewBox);
      const couleurs = [...new Set([...svg.matchAll(/fill="(#[0-9A-Fa-f]{3,8})"/g)].map((m) => m[1].toUpperCase()))].sort();
      expect(couleurs).toEqual(e.couleurs);
      expect(couleurs.every((c) => ['#1B1B1B', '#C8762B', '#FFFFFF'].includes(c))).toBe(true);
    }
  });

  it('chaque PNG : dimensions lues dans l’en-tête = manifeste', () => {
    for (const [fichier, e] of Object.entries(manifest.fichiers)) {
      if (!fichier.startsWith('png/')) continue;
      const buf = readFileSync(BRAND + fichier);
      expect(buf.subarray(1, 4).toString('ascii')).toBe('PNG');
      expect([buf.readUInt32BE(16), buf.readUInt32BE(20)]).toEqual([e.largeur, e.hauteur]);
    }
  });

  it('cas négatif : un <text> planté est détecté', () => {
    expect(contientTexte('<svg><text x="0">YanBow</text></svg>')).toBe(true);
    expect(contientTexte('<svg><title>x</title><path d="M0 0"/></svg>')).toBe(false);
  });

  it('cas négatif : un octet modifié change l’empreinte', () => {
    const [fichier, e] = Object.entries(manifest.fichiers)[0];
    const buf = Buffer.from(readFileSync(BRAND + fichier));
    buf[buf.length - 2] ^= 1;
    expect(createHash('sha256').update(buf).digest('hex')).not.toBe(e.sha256);
  });
});
