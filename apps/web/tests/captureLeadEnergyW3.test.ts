// W3 — /api/capture-lead joint le PROFIL ÉNERGÉTIQUE (facture hiver/été, été
// différent, raccordement) + l'adresse géocodée inverse + le GPS du repère au
// record transmis. Prouve aussi le contrat clé : été non différent ⇒ factureEte null.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

/** Capture le record JSON transmis au webhook CRM. */
function stubForward(): { get: () => Record<string, unknown> | null } {
  let forwarded: Record<string, unknown> | null = null;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: { body?: string }) => {
      if (String(url).includes('crm.example/hook') && init?.body) forwarded = JSON.parse(init.body);
      return { ok: true, json: async () => ({}) } as unknown as Response;
    }),
  );
  return { get: () => forwarded };
}

describe('W3 — /api/capture-lead joint le profil énergétique + adresse/GPS', () => {
  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = 'https://crm.example/hook';
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
  });
  afterEach(() => vi.unstubAllGlobals());

  it('transmet factureHiver, factureEte, eteDifferente, raccordement, adresse, gpsLat/Lng', async () => {
    const fwd = stubForward();
    const { status, json } = await call({
      ...qualified,
      factureHiver: 1200,
      factureEte: 2500,
      eteDifferente: true,
      raccordement: 'triphase',
      adresse: 'Maârif, Casablanca, Maroc',
      gpsLat: 33.5731,
      gpsLng: -7.6298,
    });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    const rec = fwd.get() as Record<string, unknown>;
    expect(rec).not.toBeNull();
    expect(rec.factureHiver).toBe(1200);
    expect(rec.factureEte).toBe(2500);
    expect(rec.eteDifferente).toBe(true);
    expect(rec.raccordement).toBe('triphase');
    expect(rec.adresse).toBe('Maârif, Casablanca, Maroc');
    expect(rec.gpsLat).toBe(33.5731);
    expect(rec.gpsLng).toBe(-7.6298);
  });

  it('été NON différent ⇒ factureEte est null (jamais la valeur saisie)', async () => {
    const fwd = stubForward();
    await call({
      ...qualified,
      factureHiver: 900,
      // une valeur résiduelle est envoyée mais doit être IGNORÉE car eteDifferente=false
      factureEte: 9999,
      eteDifferente: false,
      raccordement: 'monophase',
    });
    const rec = fwd.get() as Record<string, unknown>;
    expect(rec.eteDifferente).toBe(false);
    expect(rec.factureEte).toBeNull();
    expect(rec.factureHiver).toBe(900);
    expect(rec.raccordement).toBe('monophase');
  });

  it('le GPS du repère validé (roofPoint) prime sur les champs gps* bruts', async () => {
    const fwd = stubForward();
    await call({
      ...qualified,
      roofPoint: { lat: 31.63, lng: -8.0 },
      gpsLat: 0,
      gpsLng: 0,
    });
    const rec = fwd.get() as Record<string, unknown>;
    expect(rec.roofPoint).toEqual({ lat: 31.63, lng: -8.0 });
    expect(rec.gpsLat).toBe(31.63);
    expect(rec.gpsLng).toBe(-8.0);
  });

  it('des valeurs énergétiques absurdes / inconnues ne sont PAS jointes', async () => {
    const fwd = stubForward();
    await call({
      ...qualified,
      factureHiver: -50, // ≤ 0 → ignoré
      raccordement: 'pentaphase', // inconnu → ignoré
      adresse: '   ', // vide après trim → ignoré
      gpsLat: 'x', // non fini → ignoré
    });
    const rec = fwd.get() as Record<string, unknown>;
    expect(rec).not.toHaveProperty('factureHiver');
    expect(rec).not.toHaveProperty('raccordement');
    expect(rec).not.toHaveProperty('adresse');
    expect(rec).not.toHaveProperty('gpsLat');
    // factureEte/eteDifferente sont toujours émis (contrat explicite)
    expect(rec.eteDifferente).toBe(false);
    expect(rec.factureEte).toBeNull();
  });
});
