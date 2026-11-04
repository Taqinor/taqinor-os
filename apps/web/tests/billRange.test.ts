import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RETOUR_PAR_SEGMENT } from '../src/lib/billRange';
import { describe, expect, it } from 'vitest';
import { BILL_RANGES, isBillRangeId, libelleBandeLocale, localEstimateBand, qualifiesForCrm } from '../src/lib/billRange';
import { formatMAD } from '../src/lib/format';

describe('seuil CRM — les factures sous 1 000 MAD ne sont jamais qualifiées', () => {
  it('disqualifie lt800 et 800-1000', () => {
    expect(qualifiesForCrm('lt800')).toBe(false);
    expect(qualifiesForCrm('800-1000')).toBe(false);
  });

  it('qualifie toutes les tranches à partir de 1 000 MAD', () => {
    for (const id of ['1000-1500', '1500-3000', '3000-5000', '5000-10000', 'gt10000'] as const) {
      expect(qualifiesForCrm(id)).toBe(true);
    }
  });

  it('couvre les 7 tranches du brief (800, 1 000, 1 500, 3 000, 5 000, 10 000+)', () => {
    expect(BILL_RANGES).toHaveLength(7);
  });
});

describe('isBillRangeId', () => {
  it('accepte les ids connus et rejette le reste', () => {
    expect(isBillRangeId('1500-3000')).toBe(true);
    expect(isBillRangeId('9999')).toBe(false);
    expect(isBillRangeId(null)).toBe(false);
  });
});

describe('localEstimateBand', () => {
  it('retourne une bande locale pour chaque tranche', () => {
    for (const r of BILL_RANGES) {
      const band = localEstimateBand(r.id);
      expect(band.source).toBe('local');
      expect(band.kwcLabel.length).toBeGreaterThan(0);
      expect(band.paybackLabel.length).toBeGreaterThan(0);
      expect(band.kwcMax).toBeGreaterThanOrEqual(band.kwcMin);
    }
  });
});

describe('formatMAD', () => {
  it('formate avec séparateur de milliers espace et devise après', () => {
    expect(formatMAD(12500)).toBe('12 500 MAD');
    expect(formatMAD(800)).toBe('800 MAD');
    expect(formatMAD(1000000)).toBe('1 000 000 MAD');
    expect(formatMAD(-2500)).toBe('-2 500 MAD');
  });
});

describe('WAUD39 — retour : constante unique, affichée seulement avec une source datée', () => {
  const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../src/${p}`, import.meta.url)), 'utf-8');
  const PAGES = ['index', 'financement', 'résidentiel', 'prix-panneaux-solaires-maroc'].flatMap((p) => [p, `en/${p}`, `ar/${p}`]);
  it('aucune source datée au 03/11/2026 : constante vide', () => {
    expect(RETOUR_PAR_SEGMENT.residentiel).toBeNull();
    expect(RETOUR_PAR_SEGMENT.professionnel).toBeNull();
  });
  it.each(PAGES)('%s : aucune fourchette littérale, constante importée', (p) => {
    const s = lire(`pages/${p}.astro`);
    const rendu = s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    expect(rendu).not.toMatch(/\b[3-5]\s*(–|-|à|to)\s*[5-7][- ](ans|years|year)\b/);
    expect(rendu).not.toMatch(/\d\s*(–|إلى)\s*\d\s*سنوات/);
    expect(rendu).not.toMatch(/dir="ltr">[3-5]<\/span> إلى <span dir="ltr">[5-7] سنوات/);
    if (!p.includes('prix') ) expect(s).toContain('RETOUR_PAR_SEGMENT');
  });
  it('pages ville : stat et nuance suivent la constante', () => {
    expect(lire('components/CityPageBody.astro')).toContain('RETOUR_PAR_SEGMENT.residentiel &&');
    for (const p of ['', 'en/', 'ar/']) expect(lire(`pages/${p}installation-solaire-[city].astro`)).toContain('RETOUR_PAR_SEGMENT');
  });
  it('tableau facture → puissance de /résidentiel : la bande de retour (non sourcée) n’est plus affichée', () => {
    expect(lire('components/blocs/ResidentielDiv9D1E.astro')).not.toContain('b.payback');
    expect(lire('pages/ar/résidentiel.astro')).not.toContain('b.payback');
    expect(lire('pages/résidentiel.astro')).not.toMatch(/<span>Retour<\/span>|dépasse le plus souvent 7 ans/);
    expect(lire('pages/en/résidentiel.astro')).not.toMatch(/<span>Payback<\/span>|exceeds 7 years/);
  });
});

describe('WAUD31 — bandes dans la langue de la page, à l’affichage seulement', () => {
  it('EN et AR, jamais de « à » ni de « ans » ; FR inchangé', () => {
    expect(libelleBandeLocale('3 à 5 kWc', 'en')).toBe('3 to 5 kWc');
    expect(libelleBandeLocale('4 à 6 ans', 'en')).toBe('4 to 6 years');
    expect(libelleBandeLocale('4 à 6 ans', 'ar')).toBe('4 إلى 6 سنوات');
    expect(libelleBandeLocale('30 kWc et plus (étude dédiée)', 'en')).toBe('30 kWc and above (dedicated study)');
    expect(libelleBandeLocale('4 à 6 ans', 'fr')).toBe('4 à 6 ans');
  });

  it('le corps du lead garde le libellé français de la bande', () => {
    expect(localEstimateBand('1500-3000').paybackLabel).toBe('4 à 6 ans');
    expect(localEstimateBand('1500-3000').kwcLabel).toBe('5 à 9 kWc');
  });
});
