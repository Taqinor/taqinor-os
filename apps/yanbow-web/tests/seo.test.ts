import { describe, expect, it } from 'vitest';
import { construireSitemap, entreesSitemap } from '../src/pages/sitemap.xml';
import { PAGES } from '../src/i18n/pages';
import { creerWorker } from '../worker/pipeline.mjs';
import { pagesRendues } from './builtHtml';

const ORIGINE = 'https://exemple-domaine.test';
const TOUTES = ['/mentions-legales', '/en/legal', '/confidentialite', '/en/privacy'];

describe('YBW75 — sitemap généré depuis pages.ts', () => {
  it('aucun domaine posé : pas de sitemap (aucune URL inventée)', () => {
    expect(construireSitemap({ origine: null })).toBeNull();
  });

  it('FR+EN actifs, pages juridiques complètes : toutes les URL, hreflang réciproques', () => {
    const e = entreesSitemap({ origine: ORIGINE, locales: ['fr', 'en'], juridiquesCompletes: TOUTES });
    expect(e).toHaveLength(Object.keys(PAGES).length * 2);
    const parLoc = new Map(e.map((x) => [x.loc, x]));
    for (const entree of e) {
      expect(entree.alternates.map((a) => a.hreflang).sort()).toEqual(['en', 'fr', 'x-default']);
      for (const a of entree.alternates) {
        const autre = parLoc.get(a.href);
        expect(autre, a.href).toBeDefined();
        expect(autre!.alternates).toEqual(entree.alternates);
      }
    }
  });

  it('pages juridiques incomplètes : absentes du sitemap', () => {
    const e = entreesSitemap({ origine: ORIGINE, locales: ['fr', 'en'], juridiquesCompletes: [] });
    const locs = e.map((x) => new URL(x.loc).pathname.replace(/\/$/, ''));
    for (const j of TOUTES) expect(locs).not.toContain(j);
    expect(locs).toContain('/solarbow');
  });

  it('anglais inactif : aucune URL /en/ ni hreflang, aucune date', () => {
    const opt = { origine: ORIGINE, locales: ['fr'] as const, juridiquesCompletes: TOUTES };
    const e = entreesSitemap(opt);
    expect(e.every((x) => !new URL(x.loc).pathname.startsWith('/en/') && x.alternates.length === 0)).toBe(true);
    const xml = construireSitemap(opt)!;
    expect(xml).not.toContain('/en/');
    expect(xml).not.toContain('lastmod');
  });

  it('aucune page noindex ni utilitaire dans le sitemap (sur le HTML rendu)', () => {
    const listees = new Set(
      entreesSitemap({ origine: ORIGINE, locales: ['fr', 'en'], juridiquesCompletes: TOUTES }).map((x) => new URL(x.loc).pathname),
    );
    for (const p of pagesRendues()) {
      if (p.document.querySelector('meta[name="robots"][content*="noindex"]')) expect(listees.has(p.url), p.url).toBe(false);
    }
    for (const u of listees) expect(u.startsWith('/_')).toBe(false);
  });

  it('site FERMÉ : le Worker répond 404 au sitemap ; ouvert, il passe', async () => {
    const app = { fetch: () => new Response('<urlset/>', { headers: { 'content-type': 'application/xml' } }) };
    const worker = creerWorker(app, { CANONICAL_ORIGIN: null, CSP_SOURCES: {}, ROUTES_JURIDIQUES_COMPLETES: [] });
    const ctx = { waitUntil() {} };
    const ferme = await worker.fetch(new Request('https://x.workers.dev/sitemap.xml'), {}, ctx);
    expect(ferme.status).toBe(404);
    const ouvert = await worker.fetch(new Request('https://x.workers.dev/sitemap.xml'), { SITE_PUBLIC: '1' }, ctx);
    expect(ouvert.status).toBe(200);
  });
});

describe('YBW75 — titres et descriptions uniques par page et par langue (HTML rendu)', () => {
  const pages = pagesRendues().filter((p) => !p.url.startsWith('/_') && p.url !== '/404.html');

  for (const langue of ['fr', 'en'] as const) {
    it(`${langue} : titre et description présents et uniques`, () => {
      const deLangue = pages.filter((p) => p.langueUrl === langue);
      const titres = deLangue.map((p) => p.document.querySelector('title')?.textContent?.trim() ?? '');
      const descs = deLangue.map((p) => p.document.querySelector('meta[name="description"]')?.getAttribute('content')?.trim() ?? '');
      for (const [i, p] of deLangue.entries()) {
        expect(titres[i], `titre ${p.url}`).not.toBe('');
        expect(descs[i], `description ${p.url}`).not.toBe('');
      }
      expect(new Set(titres).size, 'titres uniques').toBe(titres.length);
      expect(new Set(descs).size, 'descriptions uniques').toBe(descs.length);
    });
  }

  it('aucune date inventée dans le JSON-LD', () => {
    for (const p of pages) {
      const ld = p.document.querySelector('script[type="application/ld+json"]')?.textContent ?? '{}';
      expect(ld).not.toMatch(/datePublished|dateCreated|foundingDate/);
    }
  });
});
