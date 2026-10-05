// CIW405 (D-CIQ-8) — étape « Affiner » FACULTATIVE après la porte de contact.
//
// 1. Le proxy same-origin POST /api/lead-affiner (fetch mocké, aucun réseau) :
//    garde cross-site, 404 du CRM → { ok:false }, jeton → URL /questionnaire/<jeton>,
//    clé mal formée → 400 sans appel amont, jamais LEAD_WEBHOOK_URL.
// 2. Les TROIS tunnels (FR/EN/AR, lus en SOURCE comme monToitTunnel.test.ts) : le
//    bouton « Affiner » n'existe que dans le bloc de succès qualifié, n'est
//    activé que pour commercial/industriel et n'est jamais demandé avant l'envoi.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resetRateLimit } from '../src/lib/rateLimit';

vi.mock('cloudflare:workers', () => ({ env: {} }));

const KEY = 'idem-ciw405-key-01';

function post(body: unknown, headers: Record<string, string> = {}): Request {
  return new Request('http://localhost/api/lead-affiner', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'cf-connecting-ip': '9.9.9.9', ...headers },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

async function call(request: Request) {
  const { POST } = await import('../src/pages/api/lead-affiner');
  const res = (await POST({ request } as unknown as Parameters<typeof POST>[0])) as Response;
  const json = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  return { status: res.status, json };
}

beforeEach(() => resetRateLimit());
afterEach(() => {
  resetRateLimit();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('POST /api/lead-affiner — garde et validation', () => {
  it('un appel cross-site est refusé (403), aucun appel amont', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await call(post({ key: KEY }, { 'sec-fetch-site': 'cross-site' }));
    expect(status).toBe(403);
    expect(fn).not.toHaveBeenCalled();
  });

  it('un Origin étranger est refusé (403)', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    const { status } = await call(post({ key: KEY }, { origin: 'https://evil.example' }));
    expect(status).toBe(403);
    expect(fn).not.toHaveBeenCalled();
  });

  it('clé absente, mal formée ou corps illisible → 400, aucun appel amont', async () => {
    const fn = vi.fn();
    vi.stubGlobal('fetch', fn);
    expect((await call(post({}))).status).toBe(400);
    expect((await call(post({ key: 'abc' }))).status).toBe(400);
    expect((await call(post('pas du json'))).status).toBe(400);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('POST /api/lead-affiner — relais au CRM', () => {
  it('jeton reçu → { ok:true, url:/questionnaire/<jeton> }, POST vers la route publique, sans corps', async () => {
    const fn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ questionnaire_token: 'pQ7xAbCdEf12' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fn);
    const { status, json } = await call(post({ key: KEY }));
    expect(status).toBe(200);
    expect(json).toEqual({ ok: true, token: 'pQ7xAbCdEf12', url: '/questionnaire/pQ7xAbCdEf12' });
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`https://api.taqinor.ma/api/django/crm/public/lead-affiner/${KEY}/`);
    expect(init.method).toBe('POST');
    expect(init.body).toBeUndefined();
  });

  it('404 opaque du CRM → 404 { ok:false }', async () => {
    const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Introuvable.' }), { status: 404 }));
    vi.stubGlobal('fetch', fn);
    const { status, json } = await call(post({ key: KEY }));
    expect(status).toBe(404);
    expect(json).toEqual({ ok: false });
  });

  it('backend injoignable → 502 { ok:false }, jamais une erreur brute', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')));
    const { status, json } = await call(post({ key: KEY }));
    expect(status).toBe(502);
    expect(json).toEqual({ ok: false });
  });

  it('jeton inexploitable (chemin, espaces) → { ok:false }', async () => {
    const fn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ questionnaire_token: '../admin' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fn);
    const { json } = await call(post({ key: KEY }));
    expect(json).toEqual({ ok: false });
  });

  it('PUBLIC_API_BASE (runtime) déplace la cible, jamais LEAD_WEBHOOK_URL', async () => {
    vi.doMock('cloudflare:workers', () => ({
      env: { PUBLIC_API_BASE: 'https://staging.example', LEAD_WEBHOOK_URL: 'https://hook.example/x' },
    }));
    const fn = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ questionnaire_token: 'tok12345678' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fn);
    await call(post({ key: KEY }));
    const [url] = fn.mock.calls[0] as [string];
    expect(url).toBe(`https://staging.example/api/django/crm/public/lead-affiner/${KEY}/`);
    expect(url).not.toContain('hook.example');
  });

  it('le proxy ne référence jamais LEAD_WEBHOOK_URL (code, hors commentaires)', () => {
    const src = readFileSync(fileURLToPath(new URL('../src/pages/api/lead-affiner.ts', import.meta.url)), 'utf-8');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    expect(code).not.toContain('LEAD_WEBHOOK_URL');
  });
});

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];
const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe.each(LOCALES)('tunnel %s — bouton « Affiner »', (_l, rel) => {
  const src = read(rel);

  it("le bouton n'existe que dans le bloc de succès qualifié (#mt-success)", () => {
    const html = src.replace(/<!--[\s\S]*?-->/g, '');
    expect(html.match(/id="mt-affiner"/g)?.length).toBe(1);
    const a = html.indexOf('id="mt-success"');
    const b = html.indexOf('id="mt-belowthreshold"');
    const at = html.indexOf('id="mt-affiner"');
    expect(a).toBeGreaterThan(-1);
    expect(at).toBeGreaterThan(a);
    expect(at).toBeLessThan(b);
    // caché par défaut : rien n'est proposé avant la porte de contact
    expect(html.slice(at - 40, at + 80)).toMatch(/hidden/);
  });

  it("n'est activé que pour commercial / industriel, via le proxy avec l'idempotencyKey", () => {
    expect(src).toContain("fetch('/api/lead-affiner'");
    expect(src).toMatch(/mode !== 'commercial' && mode !== 'industriel'/);
    expect(src).toContain('setupAffiner(getOrCreateDedupTokens().idempotencyKey)');
    expect(src).toContain('JSON.stringify({ key: idempotencyKey })');
  });

  it('un échec retire le bouton sans message ; succès ouvre /questionnaire/<jeton>', () => {
    const start = src.indexOf('function setupAffiner');
    const fn = src.slice(start, src.indexOf('btn.hidden = true; //', start) + 40);
    expect(fn).toContain("startsWith('/questionnaire/')");
    expect(fn).toContain('btn.hidden = true');
    expect(fn).not.toMatch(/errEl|alert\(/);
  });

  it("n'appelle setupAffiner qu'après un succès (pas avant l'envoi)", () => {
    const calls = src.match(/setupAffiner\(/g) ?? [];
    expect(calls.length).toBe(2); // définition + UN appel
    expect(src.indexOf('setupAffiner(getOrCreateDedupTokens')).toBeGreaterThan(src.indexOf("fetch('/api/capture-lead'"));
  });
});
