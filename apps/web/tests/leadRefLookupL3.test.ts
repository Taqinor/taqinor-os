// WREF2-L3 (GO fondateur 21/08/2026, option B) — relève PUBLIQUE de la vraie
// référence serveur pour l'écran de succès du tunnel.
//
// 1. Le proxy same-origin /api/lead-ref-lookup (fetch mocké, aucun réseau) :
//    validation de `key`, relais GET vers {API_BASE}/api/django/crm/public/
//    lead-ref/<key>/, reflet 200/404, panne backend → 502, rate-limit dédié.
// 2. Les TROIS variantes de langue de mon-toit.astro (FR/EN/AR) : même
//    contrat lu en SOURCE (script Astro inline, non montable en unité — même
//    méthode que monToitTunnel.test.ts) — la relève est câblée dans l'écran
//    de succès qualifié, remplace le code affiché ET reconstruit le lien
//    WhatsApp, reste silencieuse en échec.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resetRateLimit } from '../src/lib/rateLimit';

// Le proxy importe `cloudflare:workers` (cf.env) — module virtuel hors build,
// stubé avant l'import du handler (même convention que propositionAccept.test.ts).
vi.mock('cloudflare:workers', () => ({ env: {} }));

function makeRequest(url: string, ip = '9.9.9.9'): Request {
  return new Request(url, { method: 'GET', headers: { 'cf-connecting-ip': ip } });
}

async function call(url: string, ip?: string) {
  const { GET } = await import('../src/pages/api/lead-ref-lookup');
  const res = (await GET({ request: makeRequest(url, ip) } as unknown as Parameters<typeof GET>[0])) as Response;
  const json = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  return { status: res.status, json };
}

beforeEach(() => resetRateLimit());
afterEach(() => {
  resetRateLimit();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('GET /api/lead-ref-lookup — validation', () => {
  it('clé absente → 400, aucun appel backend', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await call('http://localhost/api/lead-ref-lookup');
    expect(status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });

  it('clé mal formée (trop courte) → 400, aucun appel backend', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await call('http://localhost/api/lead-ref-lookup?key=abc');
    expect(status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('GET /api/lead-ref-lookup — relais au backend', () => {
  it('succès → 200 { ok:true, client_ref }, URL backend correcte (défaut api.taqinor.ma)', async () => {
    const fn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ client_ref: 'BENALI-1' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fn);

    const { status, json } = await call('http://localhost/api/lead-ref-lookup?key=idem-l3-happy-01');
    expect(status).toBe(200);
    expect(json).toEqual({ ok: true, client_ref: 'BENALI-1' });

    expect(fn).toHaveBeenCalledTimes(1);
    const [calledUrl, calledInit] = fn.mock.calls[0] as [string, RequestInit];
    expect(calledUrl).toBe('https://api.taqinor.ma/api/django/crm/public/lead-ref/idem-l3-happy-01/');
    expect(calledInit.method).toBe('GET');
  });

  it('clé encodée dans le chemin (jamais dans une query string amont)', async () => {
    const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify({ client_ref: 'X-1' }), { status: 200 }));
    vi.stubGlobal('fetch', fn);
    await call('http://localhost/api/lead-ref-lookup?key=idem_L3-key-02');
    const [calledUrl] = fn.mock.calls[0] as [string];
    expect(calledUrl).toBe('https://api.taqinor.ma/api/django/crm/public/lead-ref/idem_L3-key-02/');
  });

  it('backend 404 (référence pas encore attribuée) → 404 { ok:false }', async () => {
    const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Introuvable.' }), { status: 404 }));
    vi.stubGlobal('fetch', fn);
    const { status, json } = await call('http://localhost/api/lead-ref-lookup?key=idem-l3-noref-03');
    expect(status).toBe(404);
    expect(json).toEqual({ ok: false });
  });

  it('backend injoignable/panne → 502 { ok:false }, jamais une erreur brute', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('network down'));
    vi.stubGlobal('fetch', fn);
    const { status, json } = await call('http://localhost/api/lead-ref-lookup?key=idem-l3-fail-04');
    expect(status).toBe(502);
    expect(json).toEqual({ ok: false });
  });

  it('réponse backend 200 sans client_ref exploitable → dégradation honnête (jamais 200 vide)', async () => {
    const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal('fetch', fn);
    const { status, json } = await call('http://localhost/api/lead-ref-lookup?key=idem-l3-empty-05');
    expect(status).toBe(502);
    expect(json).toEqual({ ok: false });
  });

  it('PUBLIC_API_BASE (runtime cf.env) déplace la cible, même chemin', async () => {
    vi.doMock('cloudflare:workers', () => ({ env: { PUBLIC_API_BASE: 'https://staging.example' } }));
    const { GET } = await import('../src/pages/api/lead-ref-lookup');
    const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify({ client_ref: 'X-1' }), { status: 200 }));
    vi.stubGlobal('fetch', fn);
    await GET({
      request: makeRequest('http://localhost/api/lead-ref-lookup?key=idem-l3-base-06'),
    } as unknown as Parameters<typeof GET>[0]);
    const [calledUrl] = fn.mock.calls[0] as [string];
    expect(calledUrl).toBe('https://staging.example/api/django/crm/public/lead-ref/idem-l3-base-06/');
  });
});

describe('GET /api/lead-ref-lookup — rate-limit dédié (20/min)', () => {
  it('bloque au-delà de 20 requêtes/min depuis la même IP', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ client_ref: 'X-1' }), { status: 200 })));
    let last: { status: number } | null = null;
    for (let i = 0; i < 21; i++) {
      last = await call('http://localhost/api/lead-ref-lookup?key=idem-l3-ratelimit-07');
    }
    expect(last!.status).toBe(429);
  });

  it('une IP différente n’est pas affectée par le bucket épuisé d’une autre', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ client_ref: 'X-1' }), { status: 200 })));
    for (let i = 0; i < 21; i++) {
      await call('http://localhost/api/lead-ref-lookup?key=idem-l3-ratelimit-08', '1.1.1.1');
    }
    const other = await call('http://localhost/api/lead-ref-lookup?key=idem-l3-ratelimit-08', '2.2.2.2');
    expect(other.status).not.toBe(429);
  });
});

// ———————————————————————————————————————————————————————————————————————————
// Source des trois variantes de mon-toit.astro — même méthode que
// monToitTunnel.test.ts : script Astro inline, non montable en unité.
const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

/** Texte entre deux bornes (bornes incluses), ou '' si l'ouverture manque. */
function slice(src: string, open: string, close: string): string {
  const a = src.indexOf(open);
  if (a < 0) return '';
  const b = src.indexOf(close, a + open.length);
  return b < 0 ? src.slice(a) : src.slice(a, b + close.length);
}

const pollFnSrc = (src: string) =>
  slice(src, 'function pollServerClientRef(idempotencyKey: string) {', '\n  }\n');

describe.each(LOCALES)('WREF2-L3 — %s mon-toit.astro : relève câblée dans l’écran de succès', (_locale, path) => {
  const src = read(path);

  it('déclare pollServerClientRef(), qui appelle /api/lead-ref-lookup avec la clé', () => {
    const fn = pollFnSrc(src);
    expect(fn).not.toBe('');
    expect(fn).toContain('/api/lead-ref-lookup?key=');
    expect(fn).toContain('encodeURIComponent(idempotencyKey)');
  });

  it('sur succès, remplace clientRef + le texte affiché + reconstruit le lien WhatsApp', () => {
    const fn = pollFnSrc(src);
    expect(fn).toMatch(/clientRef\s*=\s*data\.client_ref/);
    expect(fn).toContain("refEl.textContent = clientRef");
    expect(fn).toContain('waLink.href = buildWaUrl()');
  });

  it('silencieuse en échec (catch vide — jamais d’erreur remontée à l’utilisateur)', () => {
    const fn = pollFnSrc(src);
    expect(fn).toMatch(/}\s*catch\s*{/);
  });

  it('la soumission qualifiée appelle pollServerClientRef APRÈS avoir affiché le code provisoire', () => {
    const branch = slice(src, 'if (data.qualified) {', 'const wantsWa =');
    expect(branch).not.toBe('');
    const refIdx = branch.indexOf("refEl.textContent = getOrCreateClientRef();");
    const pollIdx = branch.indexOf('pollServerClientRef(getOrCreateDedupTokens().idempotencyKey);');
    expect(refIdx).toBeGreaterThan(-1);
    expect(pollIdx).toBeGreaterThan(refIdx);
  });

  it('ne touche jamais le chemin sous le seuil (aucune relève hors de la branche qualifiée)', () => {
    const below = slice(src, 'belowEl.hidden = false;', 'belowWa.href = waUrl;');
    expect(below).not.toBe('');
    expect(below).not.toContain('pollServerClientRef');
  });
});
