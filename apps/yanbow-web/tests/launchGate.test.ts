import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { creerWorker } from '../worker/pipeline.mjs';
import { sitePublic } from '../worker/launchGate.mjs';

const PAGE =
  '<!doctype html><html lang="fr"><head><link rel="canonical" href="https://domaine-final.test/"><title>x</title></head><body>ok</body></html>';

/** App factice : une page HTML (avec lien canonique), un robots.txt « ouvert », un sitemap. */
const app = {
  fetch(request: Request) {
    const p = new URL(request.url).pathname;
    if (p === '/robots.txt') return new Response('User-agent: *\nAllow: /\n', { headers: { 'content-type': 'text/plain' } });
    if (p === '/sitemap-index.xml') return new Response('<urlset/>', { headers: { 'content-type': 'application/xml' } });
    return new Response(PAGE, { headers: { 'content-type': 'text/html; charset=utf-8' } });
  },
};
const ctx = { waitUntil() {} };
const worker = creerWorker(app, { CANONICAL_ORIGIN: null, CSP_SOURCES: {}, ROUTES_JURIDIQUES_COMPLETES: [] });
const get = (path: string, env: Record<string, unknown>) => worker.fetch(new Request('https://yanbow-web.x.workers.dev' + path), env, ctx);

const ETATS_FERMES: [string, Record<string, unknown>][] = [
  ['absent', {}],
  ['vide', { SITE_PUBLIC: '' }],
  ['« 0 »', { SITE_PUBLIC: '0' }],
  ['« true »', { SITE_PUBLIC: 'true' }],
  ['« 1 » avec espace', { SITE_PUBLIC: ' 1' }],
  ['nombre 1 (non chaîne)', { SITE_PUBLIC: 1 }],
];

describe('YBW12 — porte FERMÉE (échec = fermé)', () => {
  for (const [nom, env] of ETATS_FERMES) {
    it(`SITE_PUBLIC ${nom} → fermé`, async () => {
      expect(sitePublic(env)).toBe(false);
      const page = await get('/bonjour/', env);
      expect(page.headers.get('x-robots-tag')).toBe('noindex, nofollow');
      expect(await page.text()).not.toContain('rel="canonical"');
    });
  }

  it('robots.txt servi par le Worker : Disallow: /', async () => {
    const r = await get('/robots.txt', {});
    expect(await r.text()).toBe('User-agent: *\nDisallow: /\n');
    expect(r.headers.get('x-robots-tag')).toBe('noindex, nofollow');
  });

  it('aucun sitemap', async () => {
    const r = await get('/sitemap-index.xml', {});
    expect(r.status).toBe(404);
  });

  it('chaque réponse porte X-Robots-Tag, y compris une redirection', async () => {
    const r = await get('/bonjour', {});
    expect(r.status).toBe(301);
    expect(r.headers.get('x-robots-tag')).toBe('noindex, nofollow');
  });

  it('les pages juridiques non complètes ne sont pas routables', async () => {
    for (const p of ['/confidentialite/', '/mentions-legales/', '/en/privacy/', '/en/legal/']) {
      expect((await get(p, {})).status, p).toBe(404);
    }
  });

  it('un environnement illisible (getter qui lève) = fermé', () => {
    const piege = Object.defineProperty({}, 'SITE_PUBLIC', {
      get() {
        throw new Error('illisible');
      },
    });
    expect(sitePublic(piege)).toBe(false);
  });
});

describe('YBW12 — porte OUVERTE (SITE_PUBLIC = « 1 »)', () => {
  const ouvert = { SITE_PUBLIC: '1' };

  it('aucun noindex, page intacte (canonique conservé)', async () => {
    const r = await get('/bonjour/', ouvert);
    expect(r.headers.get('x-robots-tag')).toBeNull();
    expect(await r.text()).toContain('rel="canonical"');
  });

  it('robots et sitemap réels', async () => {
    expect(await (await get('/robots.txt', ouvert)).text()).toBe('User-agent: *\nAllow: /\n');
    expect((await get('/sitemap-index.xml', ouvert)).status).toBe(200);
  });

  it('une page juridique non complète reste non routable même ouvert', async () => {
    expect((await get('/mentions-legales/', ouvert)).status).toBe(404);
  });

  it('une page juridique déclarée complète est servie', async () => {
    const w = creerWorker(app, { CANONICAL_ORIGIN: null, CSP_SOURCES: {}, ROUTES_JURIDIQUES_COMPLETES: ['/mentions-legales/'] });
    const r = await w.fetch(new Request('https://x.workers.dev/mentions-legales/'), ouvert, ctx);
    expect(r.status).toBe(200);
  });
});

describe('YBW12 — le drapeau n’est jamais dans la config versionnée', () => {
  it('wrangler.jsonc ne contient pas SITE_PUBLIC', () => {
    expect(readFileSync(new URL('../wrangler.jsonc', import.meta.url), 'utf-8')).not.toContain('SITE_PUBLIC');
  });
});
