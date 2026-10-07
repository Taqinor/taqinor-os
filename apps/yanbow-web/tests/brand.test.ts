import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { libelleProduit, MARQUE, PRODUITS, SLOGAN, VALEURS_PRODUIT } from '../src/lib/brand';
import { pagesRendues } from './builtHtml';

const SRC = fileURLToPath(new URL('../src/', import.meta.url));
const NOMS = /yanbow|solarbow|marketingbow/i;
/** Seuls endroits autorisés à écrire un nom : la constante, les dictionnaires, le registre des affirmations. */
const EXEMPTES = (rel: string) => rel === 'lib/brand.ts' || rel.startsWith('i18n/') || rel === 'lib/claims.ts';

function fichiers(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? fichiers(p) : [p];
  });
}

/** Les noms trouvés hors exemptions. */
export function nomsLitteraux(fichiersSrc: { rel: string; contenu: string }[]): string[] {
  return fichiersSrc.filter((f) => !EXEMPTES(f.rel) && NOMS.test(f.contenu)).map((f) => f.rel);
}

describe('YBW19 — noms depuis UNE constante', () => {
  it('les noms exacts', () => {
    expect(MARQUE).toBe('YanBow');
    expect(PRODUITS.solarbow.nom).toBe('SolarBow');
    expect(PRODUITS.marketingbow.nom).toBe('MarketingBow');
    expect(SLOGAN.fr).toBe('Your Arrow Needs 1Bow');
    expect(VALEURS_PRODUIT).toEqual(['solarbow', 'marketingbow', 'sur_mesure']);
    expect(libelleProduit('solarbow', 'en')).toBe('SolarBow');
  });

  it('cas négatif : un nom écrit en dur dans un composant est détecté', () => {
    expect(nomsLitteraux([{ rel: 'components/Header.astro', contenu: '<a>SolarBow</a>' }])).toEqual(['components/Header.astro']);
    expect(nomsLitteraux([{ rel: 'i18n/pages/x.fr.ts', contenu: "t: 'SolarBow'" }])).toEqual([]);
  });

  it('aucun nom produit littéral dans src/ hors brand.ts, dictionnaires et registre', () => {
    const src = fichiers(SRC).map((p) => ({ rel: relative(SRC, p).split(sep).join('/'), contenu: readFileSync(p, 'utf-8') }));
    expect(nomsLitteraux(src)).toEqual([]);
  });

  it('aucun ™ ni ® dans brand.ts', () => {
    for (const v of [MARQUE, ...Object.values(PRODUITS).map((p) => p.nom), ...Object.values(SLOGAN)]) {
      expect(v).not.toMatch(/[™®]/);
    }
  });
});

describe('YBW19 — HTML rendu', () => {
  for (const p of pagesRendues()) {
    it(`${p.url} : aucun ™/®, aucune graphie fautive des noms`, () => {
      expect(p.html).not.toMatch(/[™®]|&trade;|&reg;/);
      const texte = p.document.documentElement.textContent ?? '';
      for (const m of texte.match(/\b(yanbow|solarbow|marketingbow)\b/gi) ?? []) {
        expect(['YanBow', 'SolarBow', 'MarketingBow']).toContain(m);
      }
    });
  }
});
