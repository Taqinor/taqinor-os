// Garde-fous du lot d'hygiène W61 : format téléphone international affiché
// (cible tel: inchangée), suppression des décomptes/tournures rabaissantes,
// nouvel endpoint /sitemap.xml (sitemapindex → sitemap-0.xml), robots.txt.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { NAP } from '../src/lib/nap';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('W61(b) — téléphone affiché en format international, tel: inchangé', () => {
  it('phoneDisplayIntl vaut bien « +212 6 61 85 04 10 »', () => {
    expect(NAP.phoneDisplayIntl).toBe('+212 6 61 85 04 10');
  });

  it('mentions-legales.astro affiche phoneDisplayIntl (pas le format brut)', () => {
    const src = read('../src/pages/mentions-legales.astro');
    expect(src).toContain('NAP.phoneDisplayIntl');
    expect(src).not.toContain('NAP.phoneDisplay}'); // plus de phoneDisplay brut
  });

  it('contact.astro affiche phoneDisplayIntl et garde le lien tel:${NAP.phone}', () => {
    const src = read('../src/pages/contact.astro');
    expect(src).toContain('{NAP.phoneDisplayIntl}');
    expect(src).toContain('tel:${NAP.phone}');
    // Le format GBP brut ne doit plus être rendu sur cette page.
    expect(src).not.toContain('{NAP.phoneDisplay}');
  });
});

describe('W61(c) — aucune annonce d’asset manquant sur maintenance-monitoring', () => {
  const src = read('../src/pages/maintenance-monitoring.astro');
  it('plus de placeholder « à venir » du tableau de bord Deye Cloud', () => {
    expect(src).not.toContain('à venir');
    expect(src).not.toContain('Captures du tableau de bord Deye Cloud');
  });
  it('la copie monitoring réelle reste complète', () => {
    expect(src).toContain('Ce que dit le compteur, pas la plaquette');
    expect(src).toContain('Voir nos garanties écrites');
  });
});

describe('W61(d) — plus de décompte ni de tournure rabaissante', () => {
  it('caseStudies.ts : ni « petite installation » ni « format est modeste » ni « Petit chantier »', () => {
    const src = read('../src/lib/caseStudies.ts');
    expect(src).not.toContain('petite installation');
    expect(src).not.toContain('format est modeste');
    expect(src).not.toContain('Petit chantier');
  });
  it('realisations.ts : plus de « petite installation »', () => {
    const src = read('../src/lib/realisations.ts');
    expect(src).not.toContain('petite installation');
  });
  it('VideoChantier.astro : plus de décompte « 3 installations »', () => {
    const src = read('../src/components/VideoChantier.astro');
    expect(src).not.toContain('3 installations');
  });
});

describe('W61(a) — /sitemap.xml renvoie un sitemapindex, robots.txt le référence', () => {
  it('l’endpoint sitemap.xml.ts existe, exporte un GET et un sitemapindex vers sitemap-0.xml', () => {
    const src = read('../src/pages/sitemap.xml.ts');
    expect(src).toContain('export const GET');
    expect(src).toContain('export const prerender = true');
    expect(src).toContain('<sitemapindex');
    // L'endpoint compose la <loc> via la constante SITE — on vérifie l'hôte
    // canonique et la cible sitemap-0.xml plutôt qu'un littéral concaténé.
    expect(src).toContain('sitemap-0.xml');
    expect(src).toMatch(/https:\/\/taqinor\.ma/);
  });
  it('robots.txt référence /sitemap.xml', () => {
    const robots = read('../public/robots.txt');
    expect(robots).toContain('Sitemap: https://taqinor.ma/sitemap.xml');
  });
});
