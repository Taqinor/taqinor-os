import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { creerWorker } from '../worker/pipeline.mjs';
import { buildCsp } from '../worker/headers.mjs';
import { ORIGINE_CANONIQUE } from '../src/lib/site';
import { sourcesCsp, type SousTraitant } from '../src/lib/subprocessors';

/** App factice : renvoie une page HTML, un JSON ou un fichier selon le chemin. */
const app = {
  fetch(request: Request) {
    const p = new URL(request.url).pathname;
    if (p.startsWith('/api/')) return new Response('{"ok":true}', { headers: { 'content-type': 'application/json' } });
    if (p.startsWith('/fonts/')) return new Response('woff2', { headers: { 'content-type': 'font/woff2' } });
    return new Response('<!doctype html><html lang="fr"></html>', { headers: { 'content-type': 'text/html; charset=utf-8' } });
  },
};

const ferme = creerWorker(app, { CANONICAL_ORIGIN: null, CSP_SOURCES: {} });
const avecDomaine = creerWorker(app, { CANONICAL_ORIGIN: 'https://exemple-domaine.test', CSP_SOURCES: {} });
const env = {};
const ctx = { waitUntil() {} };

describe('YBW11 — redirection canonique', () => {
  it("ne fait RIEN tant qu'aucun domaine n'est posé (état actuel du dépôt)", async () => {
    expect(ORIGINE_CANONIQUE).toBeNull();
    const r = await ferme.fetch(new Request('https://yanbow-web.exemple.workers.dev/bonjour/'), env, ctx);
    expect(r.status).toBe(200);
    expect(r.headers.get('location')).toBeNull();
  });

  it('une fois posé : 301 en GET/HEAD, chemin et requête préservés', async () => {
    for (const method of ['GET', 'HEAD']) {
      const r = await avecDomaine.fetch(new Request('https://yanbow-web.exemple.workers.dev/solarbow/?a=1', { method }), env, ctx);
      expect(r.status).toBe(301);
      expect(r.headers.get('location')).toBe('https://exemple-domaine.test/solarbow/?a=1');
    }
  });

  it('une fois posé : 308 pour un POST (méthode et corps préservés)', async () => {
    const r = await avecDomaine.fetch(
      new Request('https://yanbow-web.exemple.workers.dev/api/rendez-vous', { method: 'POST', body: '{}' }),
      env,
      ctx,
    );
    expect(r.status).toBe(308);
    expect(r.headers.get('cache-control')).toBeNull();
  });

  it("le domaine final lui-même n'est pas redirigé", async () => {
    const r = await avecDomaine.fetch(new Request('https://exemple-domaine.test/bonjour/'), env, ctx);
    expect(r.status).toBe(200);
  });
});

describe('YBW11 — barre finale', () => {
  it('301 vers la forme avec barre pour une page', async () => {
    const r = await ferme.fetch(new Request('https://x.test/bonjour?u=1'), env, ctx);
    expect(r.status).toBe(301);
    expect(r.headers.get('location')).toBe('https://x.test/bonjour/?u=1');
  });

  it("jamais sur /api, un fichier à extension ou un POST", async () => {
    for (const [url, method] of [
      ['https://x.test/api/client-error', 'GET'],
      ['https://x.test/robots.txt', 'GET'],
      ['https://x.test/bonjour', 'POST'],
    ]) {
      const r = await ferme.fetch(new Request(url, { method, body: method === 'POST' ? '{}' : undefined }), env, ctx);
      expect(r.status).toBe(200);
    }
  });
});

describe('YBW11 — cache', () => {
  it('HTML revalidé à chaque requête', async () => {
    const r = await ferme.fetch(new Request('https://x.test/bonjour/'), env, ctx);
    expect(r.headers.get('cache-control')).toBe('public, max-age=0, must-revalidate');
  });

  it('/fonts immuable 1 an', async () => {
    const r = await ferme.fetch(new Request('https://x.test/fonts/outfit.v1.woff2'), env, ctx);
    expect(r.headers.get('cache-control')).toBe('public, max-age=31536000, immutable');
  });

  it("une réponse d'API garde son propre cache", async () => {
    const r = await ferme.fetch(new Request('https://x.test/api/x'), env, ctx);
    expect(r.headers.get('cache-control')).toBeNull();
  });
});

describe('YBW11 — en-têtes de sécurité', () => {
  it('page HTML : HSTS, nosniff, XFO DENY, Referrer/Permissions-Policy, CSP self seule', async () => {
    const r = await ferme.fetch(new Request('https://x.test/bonjour/'), env, ctx);
    expect(r.headers.get('strict-transport-security')).toContain('max-age=31536000');
    expect(r.headers.get('x-content-type-options')).toBe('nosniff');
    expect(r.headers.get('x-frame-options')).toBe('DENY');
    expect(r.headers.get('referrer-policy')).toBe('strict-origin-when-cross-origin');
    expect(r.headers.get('permissions-policy')).toContain('camera=()');
    const csp = r.headers.get('content-security-policy') ?? '';
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("worker-src 'none'");
    expect(csp).not.toMatch(/https?:\/\//); // registre vide → aucun hôte tiers
  });

  it('JSON : nosniff mais pas de CSP', async () => {
    const r = await ferme.fetch(new Request('https://x.test/api/x'), env, ctx);
    expect(r.headers.get('x-content-type-options')).toBe('nosniff');
    expect(r.headers.get('content-security-policy')).toBeNull();
  });

  it('la CSP est LUE dans le registre des sous-traitants', () => {
    const registre: SousTraitant[] = [
      { id: 'erp', nom: 'ERP', role: 'test', csp: { 'connect-src': ['https://erp.exemple.test'], 'frame-src': ['https://f.test'] } },
    ];
    const csp = buildCsp(sourcesCsp(registre));
    expect(csp).toContain("connect-src 'self' https://erp.exemple.test");
    expect(csp).toContain('frame-src https://f.test');
    expect(buildCsp(sourcesCsp())).not.toMatch(/https?:\/\//);
  });
});

describe('YBW11 — aucune trace TAQINOR dans le Worker', () => {
  it('0 occurrence de « taqinor » dans worker/', () => {
    const dir = new URL('../worker/', import.meta.url);
    for (const f of readdirSync(dir)) {
      expect(readFileSync(new URL(f, dir), 'utf-8').toLowerCase(), f).not.toContain('taqinor');
    }
  });
});
