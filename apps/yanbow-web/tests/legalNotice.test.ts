/**
 * YBW28 — page Mentions légales : avec une fixture complète, chaque bloc et
 * chaque élément s'affiche (FR et EN, HTML rendu) ; avec `null`, la route
 * n'existe pas (retirée du build, absente de la liste du Worker → 404).
 */
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import Mentions from '../src/pages/mentions-legales.astro';
import { LEGAL, type Legal, mentionsLegalesCompletes, routesJuridiquesCompletes } from '../src/lib/legal';
import { creerWorker } from '../worker/pipeline.mjs';
import { LEGAL_COMPLET } from './fixtures/legal-complet';

async function rendre(props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  return new JSDOM(await container.renderToString(Mentions, { props })).window.document;
}
const valeurs = (doc: Document, bloc: string) => [...doc.querySelectorAll(`[data-bloc="${bloc}"] dd`)].map((d) => d.textContent);

describe('YBW28 — fixture complète', () => {
  it('FR : bloc éditeur, bloc SARLAU, éléments LCEN, version qui fait foi', async () => {
    const doc = await rendre({ locale: 'fr', legal: LEGAL_COMPLET });
    expect(doc.documentElement.getAttribute('lang')).toBe('fr');
    expect(doc.querySelector('h1')?.textContent).toBe('Mentions légales');
    expect(valeurs(doc, 'editeur')).toEqual(['Fixture Test Ltd', 'Angleterre et pays de Galles', 'TEST0001', '1 Test Street, Testville', 'GBTEST001']);
    expect(valeurs(doc, 'maroc')).toEqual([
      'Fixture Test',
      "SARL d’associé unique",
      'CAPITAL-TEST',
      '2 rue du Test, Testville',
      'RC-TEST',
      'ICE-TEST',
      'IF-TEST',
      'Gérant Test',
    ]);
    const commun = valeurs(doc, 'commun');
    expect(commun).toContain('test@example.invalid');
    expect(commun).toContain('Directeur Test');
    expect(commun).toContain('Hébergeur Test, 3 Test Road, +00 1');
    expect(doc.querySelector('[data-foi]')?.textContent).toMatch(/version française/);
    // Chaque libellé est résolu (aucune clé brute).
    for (const dt of doc.querySelectorAll('dt')) expect(dt.textContent?.trim()).toBeTruthy();
  });

  it('EN : même gabarit, libellés anglais, mêmes valeurs, hreflang si en active', async () => {
    const doc = await rendre({ locale: 'en', locales: ['fr', 'en'], legal: LEGAL_COMPLET });
    expect(doc.documentElement.getAttribute('lang')).toBe('en');
    expect(doc.querySelector('h1')?.textContent).toBe('Legal notice');
    expect(valeurs(doc, 'editeur')[1]).toBe('England and Wales');
    expect(doc.querySelectorAll('[data-bloc]').length).toBe(3);
    const hreflang = [...doc.querySelectorAll('link[rel="alternate"]')].map((l) => `${l.getAttribute('hreflang')}=${l.getAttribute('href')}`);
    expect(hreflang).toEqual(['fr=/mentions-legales/', 'en=/en/legal/', 'x-default=/mentions-legales/']);
    expect(doc.querySelector('[data-foi]')?.textContent).toMatch(/French version/);
  });

  it('un bloc incomplet n’est pas rendu (SARLAU absente → seul l’éditeur et le commun)', async () => {
    const sansMaroc: Legal = { ...LEGAL_COMPLET, maroc: { ...LEGAL_COMPLET.maroc, rc: null } };
    const doc = await rendre({ locale: 'fr', legal: sansMaroc });
    expect([...doc.querySelectorAll('[data-bloc]')].map((s) => s.getAttribute('data-bloc'))).toEqual(['editeur', 'commun']);
    expect(doc.body.textContent).not.toMatch(/SARL/);
  });

  it('la page complète est déclarée routable', () => {
    expect(mentionsLegalesCompletes(LEGAL_COMPLET)).toBe(true);
    expect(routesJuridiquesCompletes(LEGAL_COMPLET)).toEqual(['/mentions-legales', '/en/legal']);
  });
});

describe('YBW28 — état réel (tout null) : la route n’existe pas', () => {
  it('rendu avec null : aucun bloc, aucune forme juridique', async () => {
    const doc = await rendre({ locale: 'fr' });
    expect(doc.querySelectorAll('[data-bloc]').length).toBe(0);
    expect(doc.body.textContent).not.toMatch(/\bLtd\b|SARL|ICE/);
  });

  it('page non complète, aucune route déclarée', () => {
    expect(mentionsLegalesCompletes(LEGAL)).toBe(false);
    expect(routesJuridiquesCompletes(LEGAL)).toEqual([]);
  });

  it('build : dossier retiré, liste du Worker vide, le Worker répond 404 (fermé ET ouvert)', async () => {
    const client = fileURLToPath(new URL('../dist/client/', import.meta.url));
    const config = fileURLToPath(new URL('../dist/server/site-config.mjs', import.meta.url));
    if (!existsSync(config)) throw new Error('dist/ absent — lancer `npm run build` avant `npm test`');
    expect(existsSync(client + 'mentions-legales')).toBe(false);
    const cfg = (await import(/* @vite-ignore */ pathToFileURL(config).href)) as { ROUTES_JURIDIQUES_COMPLETES: string[] };
    expect(cfg.ROUTES_JURIDIQUES_COMPLETES).toEqual([]);
    const app = { fetch: () => new Response('<html></html>', { headers: { 'content-type': 'text/html' } }) };
    const worker = creerWorker(app, { CANONICAL_ORIGIN: null, CSP_SOURCES: {}, ROUTES_JURIDIQUES_COMPLETES: cfg.ROUTES_JURIDIQUES_COMPLETES });
    for (const env of [{}, { SITE_PUBLIC: '1' }]) {
      expect((await worker.fetch(new Request('https://x.test/mentions-legales/'), env, {})).status).toBe(404);
    }
  });
});
