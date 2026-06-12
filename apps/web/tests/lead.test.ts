import { describe, expect, it, vi } from 'vitest';
import {
  buildLeadRecord,
  fireCapi,
  forwardLead,
  runSimulation,
  validateLead,
  type LeadEnv,
  type ValidatedLead,
} from '../src/lib/lead';

const validBody = {
  fullName: 'Karim Benali',
  phone: '06 12 34 56 78',
  whatsappOptIn: true,
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
  fbclid: 'fb.1.123.abc',
  utm_source: 'facebook',
  utm_medium: 'cpc',
  utm_campaign: 'lancement',
  utm_content: 'video-a',
  utm_term: 'solaire',
};

function makeLead(over: Partial<ValidatedLead> = {}): ValidatedLead {
  const v = validateLead(validBody);
  if (!v.ok) throw new Error('fixture invalide');
  return { ...v.lead, ...over };
}

describe('validateLead', () => {
  it('accepte un lead complet, normalise le téléphone en E.164', () => {
    const r = validateLead(validBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.phoneE164).toBe('+212612345678');
    expect(r.lead.fbclid).toBe('fb.1.123.abc');
    expect(r.lead.utm).toEqual({
      utm_source: 'facebook',
      utm_medium: 'cpc',
      utm_campaign: 'lancement',
      utm_content: 'video-a',
      utm_term: 'solaire',
    });
  });

  it('exige le consentement explicite', () => {
    const r = validateLead({ ...validBody, consent: false });
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.errors.consent).toBeDefined();
  });

  it('exige la tranche de facture (champ obligatoire)', () => {
    const r = validateLead({ ...validBody, billRange: '' });
    expect(r.ok).toBe(false);
  });

  it('rejette un téléphone non marocain', () => {
    const r = validateLead({ ...validBody, phone: '+33612345678' });
    expect(r.ok).toBe(false);
  });

  it('tolère fbclid et UTM absents', () => {
    const { fbclid, utm_source, utm_medium, utm_campaign, utm_content, utm_term, ...rest } = validBody;
    const r = validateLead(rest);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.fbclid).toBeNull();
    expect(r.lead.utm).toEqual({});
  });
});

describe('buildLeadRecord', () => {
  it('horodate le consentement et persiste fbclid + UTM', () => {
    const now = new Date('2026-06-11T10:00:00Z');
    const record = buildLeadRecord(makeLead(), { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' }, now, '/contact');
    expect(record.consentTimestamp).toBe('2026-06-11T10:00:00.000Z');
    expect(record.qualified).toBe(true);
    expect(record.fbclid).toBe('fb.1.123.abc');
    expect(record.utm.utm_campaign).toBe('lancement');
    expect(record.page).toBe('/contact');
  });

  it('marque non qualifié sous 1 000 MAD', () => {
    const record = buildLeadRecord(makeLead({ billRange: '800-1000' }), { kwcMin: 2, kwcMax: 4, kwcLabel: '2 à 4 kWc', paybackLabel: '5 à 7 ans', source: 'local' }, new Date());
    expect(record.qualified).toBe(false);
  });
});

describe('runSimulation', () => {
  it('utilise le fallback local sans SIMULATOR_API_URL', async () => {
    const band = await runSimulation(makeLead(), {});
    expect(band.source).toBe('local');
    expect(band.kwcLabel).toBe('5 à 9 kWc');
  });

  it('proxifie vers SIMULATOR_API_URL quand configurée', async () => {
    const fetchFn = vi.fn(async () =>
      new Response(JSON.stringify({ kwcMin: 6, kwcMax: 8, kwcLabel: '6 à 8 kWc', paybackLabel: '4 à 5 ans' })),
    ) as unknown as typeof fetch;
    const band = await runSimulation(makeLead(), { SIMULATOR_API_URL: 'https://sim.example/api' }, fetchFn);
    expect(band.source).toBe('simulator');
    expect(band.kwcLabel).toBe('6 à 8 kWc');
    expect(fetchFn).toHaveBeenCalledOnce();
  });

  it('retombe sur le local si le simulateur est en panne', async () => {
    const fetchFn = vi.fn(async () => {
      throw new Error('down');
    }) as unknown as typeof fetch;
    const band = await runSimulation(makeLead(), { SIMULATOR_API_URL: 'https://sim.example/api' }, fetchFn);
    expect(band.source).toBe('local');
  });
});

describe('forwardLead — tolérance', () => {
  const band = { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' as const };

  it("un lead sous le seuil n'atteint JAMAIS le webhook CRM", async () => {
    const fetchFn = vi.fn() as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead({ billRange: 'lt800' }), band, new Date());
    const r = await forwardLead(record, { LEAD_WEBHOOK_URL: 'https://crm.example/hook' }, fetchFn);
    expect(r.delivered).toBe(false);
    expect(r.reason).toBe('below-threshold');
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('tolère un webhook absent (non configuré)', async () => {
    const record = buildLeadRecord(makeLead(), band, new Date());
    const r = await forwardLead(record, {});
    expect(r.delivered).toBe(false);
    expect(r.reason).toBe('no-webhook-configured');
  });

  it('tolère un webhook en panne sans lever', async () => {
    const fetchFn = vi.fn(async () => {
      throw new Error('ECONNREFUSED');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date());
    const r = await forwardLead(record, { LEAD_WEBHOOK_URL: 'https://crm.example/hook' }, fetchFn);
    expect(r.delivered).toBe(false);
  });

  it('livre un lead qualifié au webhook avec le payload complet', async () => {
    let sentBody = '';
    const fetchFn = vi.fn(async (_url: unknown, init?: RequestInit) => {
      sentBody = String(init?.body);
      return new Response('ok');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date('2026-06-11T10:00:00Z'));
    const r = await forwardLead(record, { LEAD_WEBHOOK_URL: 'https://crm.example/hook' }, fetchFn);
    expect(r.delivered).toBe(true);
    const payload = JSON.parse(sentBody);
    expect(payload.phoneE164).toBe('+212612345678');
    expect(payload.fbclid).toBe('fb.1.123.abc');
    expect(payload.utm.utm_source).toBe('facebook');
    expect(payload.consentTimestamp).toBe('2026-06-11T10:00:00.000Z');
  });

  it('joint le secret X-Webhook-Secret quand il est configuré', async () => {
    let sentHeaders: Record<string, string> = {};
    const fetchFn = vi.fn(async (_url: unknown, init?: RequestInit) => {
      sentHeaders = (init?.headers ?? {}) as Record<string, string>;
      return new Response('ok');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date());
    await forwardLead(record, {
      LEAD_WEBHOOK_URL: 'https://crm.example/hook',
      LEAD_WEBHOOK_SECRET: 's3cret',
    }, fetchFn);
    expect(sentHeaders['x-webhook-secret']).toBe('s3cret');
    // …et jamais d'en-tête sans configuration
    await forwardLead(record, { LEAD_WEBHOOK_URL: 'https://crm.example/hook' }, fetchFn);
    expect(sentHeaders['x-webhook-secret']).toBeUndefined();
  });
});

describe('fireCapi — fire-and-forget', () => {
  const band = { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' as const };
  const env: LeadEnv = { CAPI_URL: 'https://capi.example/events' };

  it('envoie fbclid + UTM pour un lead qualifié', async () => {
    let sentBody = '';
    const fetchFn = vi.fn(async (_url: unknown, init?: RequestInit) => {
      sentBody = String(init?.body);
      return new Response('ok');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date());
    const r = await fireCapi(record, env, fetchFn);
    expect(r.sent).toBe(true);
    const payload = JSON.parse(sentBody);
    expect(payload.event).toBe('Lead');
    expect(payload.fbclid).toBe('fb.1.123.abc');
    expect(payload.utm.utm_term).toBe('solaire');
  });

  it("tolère l'absence du service en silence", async () => {
    const fetchFn = vi.fn(async () => {
      throw new Error('unreachable');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date());
    await expect(fireCapi(record, env, fetchFn)).resolves.toEqual({ sent: false });
  });

  it("n'envoie rien pour un lead non qualifié", async () => {
    const fetchFn = vi.fn() as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead({ billRange: 'lt800' }), band, new Date());
    const r = await fireCapi(record, env, fetchFn);
    expect(r.sent).toBe(false);
    expect(fetchFn).not.toHaveBeenCalled();
  });
});
