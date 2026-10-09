/**
 * YBW45 — images Open Graph 1200×630 par page et par langue active (sans
 * photo), générées par `scripts/generate-og.mjs` depuis les titres PUBLIÉS.
 * Rougit si : une page construite du registre n'a pas d'image, une image est
 * périmée (titre changé depuis la génération), n'a pas la bonne taille, ou si
 * son titre sort de la zone sûre ; aucune image orpheline.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { DOSSIER_OG, dansZoneSure, empreinte, GABARIT, HAUTEUR, LARGEUR, REGISTRE_OG, taillePng, ZONE_SURE } from '../scripts/generate-og.mjs';
import { LOCALES_ACTIVES } from '../src/i18n/config';
import { PAGES } from '../src/i18n/pages';
import { pagesRendues } from './builtHtml';

interface ImageOg {
  fichier: string;
  titre: string;
  largeur: number;
  hauteur: number;
  zone: { x: number; y: number; l: number; h: number };
  tient: boolean;
}
const REGISTRE = JSON.parse(readFileSync(REGISTRE_OG, 'utf-8')) as { gabarit: string; images: Record<string, ImageOg> };

describe('YBW45 — aides', () => {
  it('zone sûre : un titre qui déborde (bas ou droite) est refusé', () => {
    expect(dansZoneSure({ x: 80, y: 300, l: 1040, h: 200 })).toBe(true);
    expect(dansZoneSure({ x: 80, y: 300, l: 1040, h: 300 })).toBe(false);
    expect(dansZoneSure({ x: 60, y: 300, l: 1040, h: 100 })).toBe(false);
    expect(dansZoneSure({ x: 80, y: 300, l: 1100, h: 100 })).toBe(false);
    expect(ZONE_SURE).toEqual({ x: 80, y: 80, l: 1040, h: 470 });
  });

  it('taillePng lit l’en-tête IHDR ; un fichier non PNG lève', () => {
    const ihdr = Buffer.alloc(24);
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(ihdr, 0);
    ihdr.write('IHDR', 12, 'latin1');
    ihdr.writeUInt32BE(1200, 16);
    ihdr.writeUInt32BE(630, 20);
    expect(taillePng(ihdr)).toEqual({ largeur: 1200, hauteur: 630 });
    expect(() => taillePng(Buffer.from('pas une image du tout'))).toThrow();
  });

  it('nom versionné : l’empreinte change avec le titre', () => {
    expect(empreinte('A')).not.toBe(empreinte('B'));
    expect(empreinte('A')).toMatch(/^[0-9a-f]{10}$/);
  });
});

describe('YBW45 — registre et fichiers', () => {
  it('gabarit courant', () => expect(REGISTRE.gabarit).toBe(GABARIT));

  for (const [cle, img] of Object.entries(REGISTRE.images)) {
    it(`${cle} : ${LARGEUR}×${HAUTEUR}, nom versionné, titre dans la zone sûre`, () => {
      const png = readFileSync(join(DOSSIER_OG, img.fichier));
      expect(taillePng(png)).toEqual({ largeur: LARGEUR, hauteur: HAUTEUR });
      expect(img.fichier).toBe(`${cle.replace('.', '-')}-${empreinte(img.titre)}.png`);
      expect(img.tient).toBe(true);
      expect(dansZoneSure(img.zone)).toBe(true);
    });
  }

  it('aucune image orpheline dans public/og', () => {
    const fichiers = existsSync(DOSSIER_OG) ? readdirSync(DOSSIER_OG).filter((f) => f.endsWith('.png')) : [];
    expect(fichiers.sort()).toEqual(
      Object.values(REGISTRE.images)
        .map((i) => i.fichier)
        .sort(),
    );
  });
});

describe('YBW45 — une image À JOUR par page construite et par langue active', () => {
  const rendues = pagesRendues();
  for (const [id, chemins] of Object.entries(PAGES)) {
    for (const langue of LOCALES_ACTIVES) {
      const page = rendues.find((p) => p.url === chemins[langue]);
      if (!page) continue; // page non construite (juridique incomplète, page à venir)
      it(`${chemins[langue]} : image présente et titre identique au og:title publié`, () => {
        const titre = page.document.querySelector('meta[property="og:title"]')?.getAttribute('content');
        expect(titre, 'og:title absent').toBeTruthy();
        const img = REGISTRE.images[`${id}.${langue}`];
        expect(img, 'aucune image — lancer node scripts/generate-og.mjs').toBeDefined();
        expect(img.titre, 'image périmée — relancer node scripts/generate-og.mjs').toBe(titre);
      });
    }
  }
});
