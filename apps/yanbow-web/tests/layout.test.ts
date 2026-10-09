/**
 * YBW60 — gabarit commun (Layout, en-tête, pied de page), sur le HTML RENDU
 * (API Container) et sur les pages construites qui l'utilisent.
 */
import { readFileSync } from 'node:fs';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import Layout from '../src/layouts/Layout.astro';
import { PAGES, type PageId } from '../src/i18n/pages';
import { REGISTRE_OG } from '../scripts/generate-og.mjs';
import { pagesRendues } from './builtHtml';

async function rendre(props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  const html = await container.renderToString(Layout, { props: { titre: 'Titre', description: 'Description', locale: 'fr', ...props }, slots: { default: '<h1>Corps</h1>' } });
  return new JSDOM(html).window.document;
}
const hreflangs = (doc: Document) => [...doc.querySelectorAll('link[rel="alternate"][hreflang]')].map((l) => `${l.getAttribute('hreflang')}=${l.getAttribute('href')}`);
const OG = JSON.parse(readFileSync(REGISTRE_OG, 'utf-8')) as { images: Record<string, { fichier: string }> };

describe('YBW60 — en-tête de document', () => {
  it('langue, titre, description, Open Graph et Twitter', async () => {
    const doc = await rendre({ page: 'solarbow' });
    expect(doc.documentElement.lang).toBe('fr');
    expect(doc.title).toBe('Titre');
    expect(doc.querySelector('meta[name="description"]')?.getAttribute('content')).toBe('Description');
    expect(doc.querySelector('meta[property="og:title"]')?.getAttribute('content')).toBe('Titre');
    expect(doc.querySelector('meta[property="og:locale"]')?.getAttribute('content')).toBe('fr_FR');
    expect(doc.querySelector('meta[name="twitter:title"]')?.getAttribute('content')).toBe('Titre');
  });

  it('domaine non choisi : aucun lien canonique ni og:url (porte YBW12) ; posé : absolus', async () => {
    const ferme = await rendre({ page: 'solarbow' });
    expect(ferme.querySelector('link[rel="canonical"]')).toBeNull();
    expect(ferme.querySelector('meta[property="og:url"]')).toBeNull();
    const ouvert = await rendre({ page: 'solarbow', origine: 'https://exemple.test' });
    expect(ouvert.querySelector('link[rel="canonical"]')?.getAttribute('href')).toBe('https://exemple.test/solarbow/');
  });

  it('hreflang + x-default depuis le registre quand l’anglais est actif (fixture), aucun sinon', async () => {
    expect(hreflangs(await rendre({ page: 'surMesure', locales: ['fr', 'en'] }))).toEqual([
      'fr=/sur-mesure/',
      'en=/en/custom-software/',
      'x-default=/sur-mesure/',
    ]);
    const seul = await rendre({ page: 'surMesure' });
    expect(hreflangs(seul)).toEqual([]);
    expect(seul.documentElement.outerHTML).not.toContain('/en/');
  });

  it('JSON-LD Organization sans aucun champ inventé', async () => {
    const doc = await rendre({ page: 'accueil' });
    const ld = JSON.parse(doc.querySelector('script[type="application/ld+json"]')!.textContent!);
    expect(ld).toEqual({ '@context': 'https://schema.org', '@type': 'Organization', name: 'YanBow' });
  });

  it('aucun script de suivi : seul le rapport d’erreurs client (module) et le JSON-LD', async () => {
    const doc = await rendre({ page: 'accueil' });
    for (const s of doc.querySelectorAll('script')) {
      const type = s.getAttribute('type');
      expect(['module', 'application/ld+json'], s.outerHTML.slice(0, 80)).toContain(type);
    }
    const html = doc.documentElement.outerHTML;
    expect(html).not.toMatch(/utm_|fbclid|serviceWorker|gtag|googletagmanager|fbq\(/);
  });

  it('polices critiques préchargées', async () => {
    const doc = await rendre({ page: 'accueil' });
    expect([...doc.querySelectorAll('link[rel="preload"][as="font"]')].map((l) => l.getAttribute('href'))).toEqual([
      '/fonts/outfit-latin-wght-5.3.0.woff2',
      '/fonts/instrument-sans-latin-wght-5.3.0.woff2',
    ]);
  });
});

describe('YBW60 — en-tête et pied de page', () => {
  it('logo (nom ≥ 180 px), 4 entrées, UN appel « Prendre rendez-vous », page courante marquée', async () => {
    const doc = await rendre({ page: 'marketingbow' });
    const entete = doc.querySelector('header')!;
    expect(Number(entete.querySelector('[data-logo="nom"] svg')!.getAttribute('width'))).toBeGreaterThanOrEqual(180);
    expect([...entete.querySelectorAll('.nav-bureau a')].map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['SolarBow', '/solarbow/'],
      ['MarketingBow', '/marketingbow/'],
      ['Sur mesure', '/sur-mesure/'],
      ['Société', '/societe/'],
    ]);
    expect([...entete.querySelectorAll('.entete-actions .bouton')].map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Prendre rendez-vous', '/rendez-vous/'],
    ]);
    expect(entete.querySelector('.nav-bureau a[aria-current="page"]')?.textContent).toBe('MarketingBow');
    expect(entete.querySelector('[data-logo="slogan"]')).toBeNull();
  });

  it('sélecteur de langue seulement si une autre langue est active (fixture)', async () => {
    expect((await rendre({ page: 'societe' })).querySelector('.lien-langue')).toBeNull();
    const doc = await rendre({ page: 'societe', locales: ['fr', 'en'] });
    expect(doc.querySelector('.lien-langue')?.getAttribute('href')).toBe('/en/company/');
  });

  it('pied : slogan en lockup ≥ 420 px, aucun lien juridique tant que les pages sont incomplètes', async () => {
    const doc = await rendre({ page: 'accueil' });
    const pied = doc.querySelector('footer')!;
    expect(Number(pied.querySelector('[data-logo="slogan"] svg')!.getAttribute('width'))).toBeGreaterThanOrEqual(420);
    expect(pied.querySelector('[data-liens-juridiques]')).toBeNull();
    expect(pied.querySelectorAll('.pied-nav a')).toHaveLength(5);
  });
});

describe('YBW60 — pages construites avec le gabarit', () => {
  const ids = Object.keys(PAGES) as PageId[];
  const avecGabarit = pagesRendues().filter((x) => x.document.querySelector('header.entete'));
  it('chaque page du gabarit appartient au registre des pages', () => {
    for (const p of avecGabarit) expect(ids.some((i) => PAGES[i].fr === p.url || PAGES[i].en === p.url), p.url).toBe(true);
  });
  for (const p of avecGabarit) {
    const id = ids.find((i) => PAGES[i].fr === p.url || PAGES[i].en === p.url);
    it(`${p.url} : un seul h1, contenu principal, og:image = image YBW45 de la page`, () => {
      expect(p.document.querySelectorAll('h1')).toHaveLength(1);
      expect(p.document.querySelector('main#contenu')).not.toBeNull();
      const img = OG.images[`${id}.${p.langueUrl}`];
      expect(img, `aucune image OG pour ${id}`).toBeDefined();
      expect(p.document.querySelector('meta[property="og:image"]')?.getAttribute('content')).toBe(`/og/${img.fichier}`);
    });
  }
});
