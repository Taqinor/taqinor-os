// W112 — endpoint /api/capture-lead : valide le lead, joint le repère (roofPoint),
// le contour (roofOutline) et la consommation (billKwh) au record transmis, et —
// comme le flux existant — ne transmet RIEN sous le seuil (lead non qualifié).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// cloudflare:workers est un module virtuel (fourni par l'adaptateur au build) :
// on le mocke pour exposer un `env` configurable (webhook activé) + waitUntil.
const mockEnv: Record<string, string> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));

import { resetRateLimit } from '../src/lib/rateLimit';

function makeRequest(body: unknown): Request {
  return new Request('http://localhost/api/capture-lead', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function call(body: unknown) {
  const { POST } = await import('../src/pages/api/capture-lead');
  const res = await POST({ request: makeRequest(body) } as unknown as Parameters<typeof POST>[0]);
  const json = (await (res as Response).json()) as Record<string, unknown>;
  return { status: (res as Response).status, json };
}

/** Lead QUALIFIÉ valide (tranche ≥ 1 000 → transmis au CRM). */
const qualified = {
  fullName: 'Reda K.',
  phone: '0612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

/** Lead VALIDE mais SOUS le seuil (lt800 → jamais transmis). */
const belowThreshold = { ...qualified, billRange: 'lt800' };

describe('W112 — /api/capture-lead joint le repère au record transmis', () => {
  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = 'https://crm.example/hook';
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
    mockEnv.CAPI_URL = 'https://capi.example/events';
  });
  afterEach(() => vi.unstubAllGlobals());

  it('transmet le record AVEC roofPoint / roofOutline / billKwh', async () => {
    let forwarded: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: { body?: string }) => {
        if (String(url).includes('crm.example/hook') && init?.body) forwarded = JSON.parse(init.body);
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    const { status, json } = await call({
      ...qualified,
      roofPoint: { lat: 33.57, lng: -7.6 },
      roofOutline: [
        [33.57, -7.6],
        [33.571, -7.6],
        [33.571, -7.599],
      ],
      billKwh: 9000,
    });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(forwarded).not.toBeNull();
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec.roofPoint).toEqual({ lat: 33.57, lng: -7.6 });
    expect(Array.isArray(rec.roofOutline)).toBe(true);
    expect((rec.roofOutline as unknown[]).length).toBe(3);
    expect(rec.billKwh).toBe(9000);
    // le contact validé est bien là (mirroir de preview-lead)
    expect(rec.city).toBe('Casablanca');
  });

  it('un repère NUMÉRIQUEMENT invalide n\'est PAS joint (record propre)', async () => {
    let forwarded: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: { body?: string }) => {
        if (init?.body) forwarded = JSON.parse(init.body);
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    await call({ ...qualified, roofPoint: { lat: 'x', lng: null }, roofOutline: [[1]], billKwh: -3 });
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec).not.toHaveProperty('roofPoint');
    expect(rec).not.toHaveProperty('roofOutline');
    expect(rec).not.toHaveProperty('billKwh');
  });

  it('ne transmet RIEN sous le seuil (lead non qualifié) — même comportement que le flux existant', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status, json } = await call({ ...belowThreshold, roofPoint: { lat: 33.5, lng: -7.6 } });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    // aucun POST vers le webhook CRM (forwardLead court-circuite un lead non qualifié)
    const hookCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes('crm.example/hook'));
    expect(hookCalls.length).toBe(0);
  });

  it('rejette un lead invalide (400) sans rien transmettre', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status, json } = await call({ fullName: 'X', consent: false });
    expect(status).toBe(400);
    expect(json.ok).toBe(false);
    expect(fetchMock.mock.calls.filter((c) => String(c[0]).includes('crm.example/hook')).length).toBe(0);
  });

  it('limite le débit (429) après trop de tentatives', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response));
    let last = { status: 200 };
    for (let i = 0; i < 12; i++) last = await call(qualified);
    expect(last.status).toBe(429);
  });
});

// WJ110 — /devis/mon-toit est le CTA principal du site, mais capture-lead ne
// déclenchait JAMAIS le Meta CAPI (contrairement à simulate.ts et
// preview-lead.ts) : Meta optimisait donc les campagnes sur une tranche non
// représentative du trafic. Preuve : une soumission QUALIFIÉE déclenche
// fireCapi exactement une fois ; une soumission NON qualifiée ne le déclenche
// jamais (même gating que forwardLead, miroir du test simulate/preview-lead).
describe('WJ110 — /api/capture-lead déclenche le Meta CAPI', () => {
  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = 'https://crm.example/hook';
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
    mockEnv.CAPI_URL = 'https://capi.example/events';
  });
  afterEach(() => vi.unstubAllGlobals());

  it('une soumission QUALIFIÉE déclenche fireCapi exactement une fois', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status, json } = await call(qualified);
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    const capiCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes('capi.example/events'));
    expect(capiCalls.length).toBe(1);
  });

  it('une soumission NON qualifiée (sous le seuil) ne déclenche PAS fireCapi', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status, json } = await call(belowThreshold);
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    const capiCalls = fetchMock.mock.calls.filter((c) => String(c[0]).includes('capi.example/events'));
    expect(capiCalls.length).toBe(0);
  });
});
