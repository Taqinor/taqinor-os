/**
 * YBW37 — favicon et icônes visibles sur onglet clair ET sombre : tuile encre
 * opaque, contraste glyphe/tuile ≥ 3:1 calculé sur les pixels, tailles lues
 * dans les en-têtes PNG, zone sûre de l'icône masquable.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { describe, expect, it } from 'vitest';
import { ICONES, MASQUABLE, SOURCE, TAILLES_FAVICON } from '../scripts/build-icons.mjs';

const PUBLIC = fileURLToPath(new URL('../public/', import.meta.url));
const PACK_PNG = fileURLToPath(new URL('../src/brand/png/', import.meta.url));
const ONGLETS = { clair: [255, 255, 255], sombre: [32, 33, 36] } as const;

const lin = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const lum = ([r, g, b]: readonly number[]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
export const contraste = (a: readonly number[], b: readonly number[]) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
const dimensions = (buf: Buffer) => [buf.readUInt32BE(16), buf.readUInt32BE(20)];

/** Pixels d'une image composée sur la couleur d'onglet ; renvoie [tuile (coin), glyphe (pixel le plus contrasté)]. */
async function tuileEtGlyphe(fichier: string, onglet: readonly number[]): Promise<{ tuile: number[]; glyphe: number[]; opaque: boolean }> {
  const brut = await sharp(fichier).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const opaque = [...Array(brut.info.width * brut.info.height).keys()].every((i) => brut.data[i * 4 + 3] === 255);
  const { data, info } = await sharp(fichier).flatten({ background: { r: onglet[0], g: onglet[1], b: onglet[2] } }).raw().toBuffer({ resolveWithObject: true });
  const px = (i: number) => [data[i * info.channels], data[i * info.channels + 1], data[i * info.channels + 2]];
  const tuile = px(0);
  let glyphe = tuile;
  for (let i = 0; i < info.width * info.height; i++) if (contraste(px(i), tuile) > contraste(glyphe, tuile)) glyphe = px(i);
  return { tuile, glyphe, opaque };
}

describe('YBW37 — source unique', () => {
  it('favicon.svg = copie à l’octet de la coupe favicon inversée (tuile encre opaque)', () => {
    const svg = readFileSync(PUBLIC + 'favicon.svg');
    expect(svg.equals(readFileSync(SOURCE))).toBe(true);
    expect(svg.toString()).toMatch(/<rect width="800" height="800" fill="#1B1B1B"\/>/);
  });
});

describe('YBW37 — tailles lues dans les en-têtes PNG', () => {
  for (const t of TAILLES_FAVICON) {
    it(`icons/icon-${t}.png : ${t}×${t}`, () => expect(dimensions(readFileSync(PUBLIC + `icons/icon-${t}.png`))).toEqual([t, t]));
  }
  for (const [nom, t] of Object.entries(ICONES)) {
    it(`icons/${nom} : ${t}×${t}`, () => expect(dimensions(readFileSync(PUBLIC + `icons/${nom}`))).toEqual([t, t]));
  }
  it(`icons/${MASQUABLE.nom} : 512×512`, () => expect(dimensions(readFileSync(PUBLIC + `icons/${MASQUABLE.nom}`))).toEqual([512, 512]));

  it('favicon.ico : trois PNG 16, 32, 48', () => {
    const ico = readFileSync(PUBLIC + 'favicon.ico');
    expect(ico.readUInt16LE(2)).toBe(1);
    expect(ico.readUInt16LE(4)).toBe(3);
    for (let i = 0; i < 3; i++) {
      const o = 6 + i * 16;
      const taille = ico.readUInt8(o);
      const debut = ico.readUInt32LE(o + 12);
      const png = ico.subarray(debut, debut + ico.readUInt32LE(o + 8));
      expect(png.subarray(1, 4).toString('ascii')).toBe('PNG');
      expect(dimensions(png)).toEqual([taille, taille]);
    }
    expect([0, 1, 2].map((i) => ico.readUInt8(6 + i * 16))).toEqual([16, 32, 48]);
  });
});

describe('YBW37 — contraste sur onglet clair ET sombre (pixels)', () => {
  for (const t of TAILLES_FAVICON) {
    for (const [onglet, couleur] of Object.entries(ONGLETS)) {
      it(`icon-${t}.png sur onglet ${onglet} : tuile opaque, glyphe/tuile ≥ 3:1`, async () => {
        const { tuile, glyphe, opaque } = await tuileEtGlyphe(PUBLIC + `icons/icon-${t}.png`, couleur);
        expect(opaque).toBe(true);
        expect(contraste(glyphe, tuile)).toBeGreaterThanOrEqual(3);
      });
    }
  }

  it('cas négatif : le PNG transparent du pack est invisible sur onglet sombre (< 3:1)', async () => {
    const { data, info } = await sharp(PACK_PNG + 'yanbow-favicon-32.png')
      .flatten({ background: { r: 32, g: 33, b: 36 } })
      .raw()
      .toBuffer({ resolveWithObject: true });
    // Le B encre du pack, posé sur un onglet sombre : contraste du pixel le plus sombre du glyphe vs onglet.
    let plusSombre = [255, 255, 255];
    for (let i = 0; i < info.width * info.height; i++) {
      const p = [data[i * info.channels], data[i * info.channels + 1], data[i * info.channels + 2]];
      if (lum(p) < lum(plusSombre)) plusSombre = p;
    }
    expect(contraste(plusSombre, ONGLETS.sombre)).toBeLessThan(3);
  });
});

describe('YBW37 — icône masquable', () => {
  it('tout pixel non encre est dans le cercle sûr (rayon 40 %)', async () => {
    const { data, info } = await sharp(PUBLIC + `icons/${MASQUABLE.nom}`).raw().toBuffer({ resolveWithObject: true });
    const c = info.width / 2;
    let horsZone = 0;
    let glyphe = 0;
    for (let y = 0; y < info.height; y++) {
      for (let x = 0; x < info.width; x++) {
        const i = (y * info.width + x) * info.channels;
        const encre = Math.abs(data[i] - 27) < 12 && Math.abs(data[i + 1] - 27) < 12 && Math.abs(data[i + 2] - 27) < 12;
        if (encre) continue;
        glyphe++;
        if (Math.hypot(x + 0.5 - c, y + 0.5 - c) > 0.4 * info.width) horsZone++;
      }
    }
    expect(glyphe).toBeGreaterThan(1000);
    expect(horsZone).toBe(0);
  });
});

describe('YBW37 — site.webmanifest', () => {
  it('nom de la marque, icônes 192/512/maskable', () => {
    const m = JSON.parse(readFileSync(PUBLIC + 'site.webmanifest', 'utf-8'));
    expect(m.name).toBe('YanBow');
    expect(m.icons.map((i: { src: string }) => i.src)).toEqual(['/icons/icon-192.png', '/icons/icon-512.png', `/icons/${MASQUABLE.nom}`]);
    expect(m.icons[2].purpose).toBe('maskable');
  });
});
