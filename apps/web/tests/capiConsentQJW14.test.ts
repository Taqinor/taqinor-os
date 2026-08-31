/**
 * QJW14 — « Refuser » sur la bannière de consentement bloque le beacon Meta
 * CAPI, et RIEN D'AUTRE.
 *
 * Avant : `fireCapi` ne lisait jamais `tq_consent` ; un visiteur qui cliquait
 * « Refuser » puis soumettait le formulaire voyait quand même partir chez Meta
 * son téléphone, sa ville et son e-mail hachés.
 *
 * Ce que cette garde épingle, dans les deux sens :
 *  - refus explicite → AUCUN appel au CAPI, mais le lead part quand même au CRM
 *    (le contrat webhook n'est jamais gaté par ce signal) ;
 *  - pas de réponse à la bannière → comportement INCHANGÉ (le beacon part) :
 *    c'est la moitié « documentée » de la décision, épinglée pour qu'un
 *    changement d'avis du fondateur soit un choix visible, pas une dérive.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockEnv: Record<string, string> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));

import { adsConsentFromBody, buildLeadRecord, fireCapi, validateLead } from '../src/lib/lead';
import { resetRateLimit } from '../src/lib/rateLimit';

const CRM = 'https://crm.example/hook';
const CAPI = 'https://capi.example/events';

/** Lead qualifié (tranche ≥ 1 000 MAD) — celui qui atteint CRM *et* CAPI. */
const qualifie = {
  fullName: 'Reda K.',
  phone: '0612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

function makeRequest(route: string, body: unknown): Request {
  return new Request(`http://localhost/api/${route}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** Appelle un endpoint et renvoie les URL réellement contactées. */
async function call(route: 'simulate' | 'capture-lead' | 'preview-lead', body: unknown) {
  const urls: string[] = [];
  const bodies: Record<string, string> = {};
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: { body?: string }) => {
      urls.push(String(url));
      if (init?.body) bodies[String(url)] = init.body;
      return { ok: true, json: async () => ({}) } as unknown as Response;
    }),
  );
  // Imports STATIQUES (un `import()` à variable ferait râler vite:dynamic-import-vars).
  const mod =
    route === 'simulate'
      ? await import('../src/pages/api/simulate')
      : route === 'preview-lead'
        ? await import('../src/pages/api/preview-lead')
        : await import('../src/pages/api/capture-lead');
  const res = (await mod.POST({ request: makeRequest(route, body) } as never)) as Response;
  return { status: res.status, json: (await res.json()) as Record<string, unknown>, urls, bodies };
}

describe('QJW14 — lecture du signal de consentement', () => {
  it('ne retient que les deux valeurs réelles de tq_consent, jamais une supposition', () => {
    expect(adsConsentFromBody({ adsConsent: 'denied' })).toBe('denied');
    expect(adsConsentFromBody({ adsConsent: 'granted' })).toBe('granted');
    expect(adsConsentFromBody({})).toBe('unset');
    expect(adsConsentFromBody({ adsConsent: 'oui' })).toBe('unset');
    expect(adsConsentFromBody(null)).toBe('unset');
  });
});

describe('QJW14 — fireCapi respecte un refus explicite', () => {
  it('n’émet AUCUNE requête quand le visiteur a refusé', async () => {
    const v = validateLead(qualifie);
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    const record = buildLeadRecord(v.lead, { kwcMin: 8, kwcMax: 16, kwcLabel: '8 à 16 kWc', paybackLabel: '5 à 7 ans', source: 'local' }, new Date());
    expect(record.qualified).toBe(true);

    const fetchFn = vi.fn(async () => ({ ok: true }) as unknown as Response) as unknown as typeof fetch;
    const out = await fireCapi(record, { CAPI_URL: CAPI }, fetchFn, { adsConsent: 'denied' });
    expect(out.sent).toBe(false);
    expect(out.reason).toBe('consent-denied');
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('part normalement quand le visiteur a accepté, ou n’a pas répondu', async () => {
    const v = validateLead(qualifie);
    if (!v.ok) return;
    const record = buildLeadRecord(v.lead, { kwcMin: 8, kwcMax: 16, kwcLabel: '8 à 16 kWc', paybackLabel: '5 à 7 ans', source: 'local' }, new Date());
    for (const adsConsent of ['granted', 'unset'] as const) {
      const fetchFn = vi.fn(async () => ({ ok: true }) as unknown as Response) as unknown as typeof fetch;
      const out = await fireCapi(record, { CAPI_URL: CAPI }, fetchFn, { adsConsent });
      expect(out.sent, adsConsent).toBe(true);
      expect(fetchFn).toHaveBeenCalledOnce();
    }
    // Appel HISTORIQUE sans option : comportement strictement inchangé.
    const fetchFn = vi.fn(async () => ({ ok: true }) as unknown as Response) as unknown as typeof fetch;
    expect((await fireCapi(record, { CAPI_URL: CAPI }, fetchFn)).sent).toBe(true);
  });
});

describe('QJW14 — « Refuser » puis soumettre, de bout en bout', () => {
  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = CRM;
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
    mockEnv.CAPI_URL = CAPI;
  });
  afterEach(() => vi.unstubAllGlobals());

  it('/api/simulate — le lead part au CRM, le beacon Meta ne part PAS', async () => {
    const { status, json, urls, bodies } = await call('simulate', { ...qualifie, adsConsent: 'denied' });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    // Contrat webhook intact : le lead est capturé et transmis quoi qu'il arrive.
    expect(urls).toContain(CRM);
    const forwarded = JSON.parse(bodies[CRM]);
    expect(forwarded.phoneE164).toBe('+212612345678');
    expect(forwarded.consent).toBe(true);
    // Seul le beacon publicitaire est bloqué.
    expect(urls).not.toContain(CAPI);
    // Et le champ de consentement n'a pas fui dans le corps webhook (il n'est
    // pas dans la liste blanche de validateOptionalFields).
    expect(forwarded.adsConsent).toBeUndefined();
  });

  it('/api/simulate — sans réponse à la bannière, le beacon part (comportement documenté)', async () => {
    const { urls } = await call('simulate', qualifie);
    expect(urls).toContain(CRM);
    expect(urls).toContain(CAPI);
  });

  it('/api/preview-lead — même gate (miroir strict)', async () => {
    const refus = await call('preview-lead', { ...qualifie, adsConsent: 'denied' });
    expect(refus.urls).toContain(CRM);
    expect(refus.urls).not.toContain(CAPI);

    resetRateLimit();
    const accepte = await call('preview-lead', { ...qualifie, adsConsent: 'granted' });
    expect(accepte.urls).toContain(CAPI);
  });

  it('/api/capture-lead — même gate sur le CTA principal du tunnel', async () => {
    const refus = await call('capture-lead', { ...qualifie, adsConsent: 'denied' });
    expect(refus.urls).toContain(CRM);
    expect(refus.urls).not.toContain(CAPI);

    resetRateLimit();
    const sansReponse = await call('capture-lead', qualifie);
    expect(sansReponse.urls).toContain(CAPI);
  });
});
