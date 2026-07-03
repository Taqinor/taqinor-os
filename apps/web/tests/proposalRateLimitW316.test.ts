// W316 — Rate-limit des cinq endpoints jusque-là non protégés
// (proposition-accept, proposition-contact, roof-yield, roof-production,
// roof-estimate) + le SSR de /proposition/[token] : même pattern
// (rateLimit/clientIpFromRequest) que capture-lead/preview-lead, buckets
// DISTINCTS par endpoint, tuning généreux pour les endpoints roof-* (usage
// interactif normal = plusieurs appels/minute).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resetRateLimit } from '../src/lib/rateLimit';

// cloudflare:workers est un module virtuel (fourni par l'adaptateur au build) :
// mocké au niveau module (même convention que captureLeadW112.test.ts) pour que
// proposition-accept.ts puisse résoudre `cf.env` sous vitest.
vi.mock('cloudflare:workers', () => ({
  get env() {
    return {};
  },
  waitUntil: undefined,
}));

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

function makeRequest(url: string, body: unknown, ip = '9.9.9.9'): Request {
  return new Request(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'cf-connecting-ip': ip },
    body: JSON.stringify(body),
  });
}

beforeEach(() => resetRateLimit());
afterEach(() => {
  resetRateLimit();
  vi.unstubAllGlobals();
});

describe('W316 — /api/roof-yield rate-limit (60/min, généreux)', () => {
  it('bloque au-delà de 60 requêtes/min depuis la même IP', async () => {
    const { POST } = await import('../src/pages/api/roof-yield');
    const body = { lat: 33.5, lon: -7.6, legs: [{ kwc: 3, tiltDeg: 15, aspect: 0 }] };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })));
    let last: Response | null = null;
    for (let i = 0; i < 61; i++) {
      last = (await POST({ request: makeRequest('http://localhost/api/roof-yield', body) } as unknown as Parameters<
        typeof POST
      >[0])) as Response;
    }
    expect(last!.status).toBe(429);
  });

  it('une IP différente n’est pas affectée par le bucket épuisé d’une autre', async () => {
    const { POST } = await import('../src/pages/api/roof-yield');
    const body = { lat: 33.5, lon: -7.6, legs: [{ kwc: 3, tiltDeg: 15, aspect: 0 }] };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })));
    for (let i = 0; i < 61; i++) {
      await POST({ request: makeRequest('http://localhost/api/roof-yield', body, '1.1.1.1') } as unknown as Parameters<
        typeof POST
      >[0]);
    }
    const other = (await POST({
      request: makeRequest('http://localhost/api/roof-yield', body, '2.2.2.2'),
    } as unknown as Parameters<typeof POST>[0])) as Response;
    expect(other.status).not.toBe(429);
  });
});

describe('W316 — /api/roof-production rate-limit (60/min)', () => {
  it('bloque au-delà de 60 requêtes/min', async () => {
    const { POST } = await import('../src/pages/api/roof-production');
    const body = { lat: 33.5, lon: -7.6, tiltDeg: 15, aspect: 0, placedPanels: 10 };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })));
    let last: Response | null = null;
    for (let i = 0; i < 61; i++) {
      last = (await POST({
        request: makeRequest('http://localhost/api/roof-production', body),
      } as unknown as Parameters<typeof POST>[0])) as Response;
    }
    expect(last!.status).toBe(429);
  });
});

describe('W316 — /api/roof-estimate rate-limit (60/min)', () => {
  it('bloque au-delà de 60 requêtes/min', async () => {
    const { POST } = await import('../src/pages/api/roof-estimate');
    const body = { lat: 33.5, lon: -7.6, kwc: 3, orientation: 'sud' };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })));
    let last: Response | null = null;
    for (let i = 0; i < 61; i++) {
      last = (await POST({
        request: makeRequest('http://localhost/api/roof-estimate', body),
      } as unknown as Parameters<typeof POST>[0])) as Response;
    }
    expect(last!.status).toBe(429);
  });
});

describe('W316 — /api/proposition-accept rate-limit (10/min, plus serré)', () => {
  it('bloque au-delà de 10 requêtes/min', async () => {
    const { POST } = await import('../src/pages/api/proposition-accept');
    const body = { token: 'tok', nom: 'Reda K.' };
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })));
    let last: Response | null = null;
    for (let i = 0; i < 11; i++) {
      last = (await POST({
        request: makeRequest('http://localhost/api/proposition-accept', body),
      } as unknown as Parameters<typeof POST>[0])) as Response;
    }
    expect(last!.status).toBe(429);
  });
});

describe('W316 — /api/proposition-contact rate-limit (10/min)', () => {
  it('bloque au-delà de 10 requêtes/min, jamais un état bloquant côté client (toujours JSON dégradé)', async () => {
    const { POST } = await import('../src/pages/api/proposition-contact');
    const body = { token: 'tok', channel: 'rappel' };
    let last: Response | null = null;
    for (let i = 0; i < 11; i++) {
      last = (await POST({
        request: makeRequest('http://localhost/api/proposition-contact', body),
      } as unknown as Parameters<typeof POST>[0])) as Response;
    }
    expect(last!.status).toBe(429);
    const payload = (await last!.json()) as { ok: boolean; degraded: boolean };
    expect(payload.ok).toBe(false);
    expect(payload.degraded).toBe(true);
  });
});

describe('W316 — buckets DISTINCTS par endpoint (une IP épuisant roof-yield ne bloque pas roof-estimate)', () => {
  it('roof-estimate reste disponible après épuisement de roof-yield pour la même IP', async () => {
    const yieldRoute = await import('../src/pages/api/roof-yield');
    const estimateRoute = await import('../src/pages/api/roof-estimate');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}), { status: 200 })));
    const ip = '5.5.5.5';
    for (let i = 0; i < 61; i++) {
      await yieldRoute.POST({
        request: makeRequest('http://localhost/api/roof-yield', { lat: 33.5, lon: -7.6, legs: [{ kwc: 3, tiltDeg: 15, aspect: 0 }] }, ip),
      } as unknown as Parameters<typeof yieldRoute.POST>[0]);
    }
    const res = (await estimateRoute.POST({
      request: makeRequest('http://localhost/api/roof-estimate', { lat: 33.5, lon: -7.6, kwc: 3, orientation: 'sud' }, ip),
    } as unknown as Parameters<typeof estimateRoute.POST>[0])) as Response;
    expect(res.status).not.toBe(429);
  });
});

describe('W316 — /proposition/[token] SSR : rate-limit câblé (lecture source)', () => {
  const PROPOSITION = read('../src/pages/proposition/[token].astro');

  it('importe rateLimit/clientIpFromRequest et gate le SSR AVANT le fetch backend', () => {
    expect(PROPOSITION).toContain("import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit'");
    expect(PROPOSITION).toContain('proposition-view:');
    expect(PROPOSITION).toMatch(/httpStatus = 429/);
  });

  it('le 429 reste RETRYABLE (bouton Réessayer), jamais un cul-de-sac', () => {
    expect(PROPOSITION).toContain('isTimeout || httpStatus === 429');
  });
});
