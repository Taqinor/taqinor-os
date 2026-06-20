import { describe, expect, it, vi } from 'vitest';
import {
  buildLeadRecord,
  fireCapi,
  forwardLead,
  hashCityForCapi,
  hashPhoneForCapi,
  leadLogId,
  redactLeadForLog,
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

  it('joint un en-tête x-webhook-timestamp ISO (atténuation rejeu, ERR110)', async () => {
    let sentHeaders: Record<string, string> = {};
    const fetchFn = vi.fn(async (_url: unknown, init?: RequestInit) => {
      sentHeaders = (init?.headers ?? {}) as Record<string, string>;
      return new Response('ok');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date());
    await forwardLead(record, { LEAD_WEBHOOK_URL: 'https://crm.example/hook' }, fetchFn);
    expect(sentHeaders['x-webhook-timestamp']).toBeDefined();
    // ISO 8601 valide → re-parsable.
    expect(Number.isNaN(Date.parse(sentHeaders['x-webhook-timestamp']))).toBe(false);
  });
});

describe('redactLeadForLog — aucune PII dans les logs (ERR32)', () => {
  const band = { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' as const };

  it('ne contient JAMAIS nom/téléphone/ville/email/consentement', () => {
    const record = buildLeadRecord(makeLead(), band, new Date('2026-06-11T10:00:00Z'), '/contact');
    const redacted = redactLeadForLog(record);
    const serialized = JSON.stringify(redacted);
    // PII brute absente de la sérialisation des logs.
    expect(serialized).not.toContain('Karim Benali');
    expect(serialized).not.toContain('+212612345678');
    expect(serialized).not.toContain('612345678');
    expect(serialized).not.toContain('Casablanca');
    // Pas de champs PII même vides.
    expect(redacted).not.toHaveProperty('fullName');
    expect(redacted).not.toHaveProperty('phoneE164');
    expect(redacted).not.toHaveProperty('city');
    expect(redacted).not.toHaveProperty('consent');
    expect(redacted).not.toHaveProperty('consentTimestamp');
  });

  it('garde des diagnostics non identifiants utiles', () => {
    const record = buildLeadRecord(makeLead(), band, new Date('2026-06-11T10:00:00Z'), '/contact');
    const redacted = redactLeadForLog(record);
    expect(redacted.qualified).toBe(true);
    expect(redacted.billRange).toBe('1500-3000');
    expect(redacted.hasName).toBe(true);
    expect(redacted.hasCity).toBe(true);
    expect(typeof redacted.id).toBe('string');
    expect(redacted.fbclid).toBe('present');
    expect(redacted.utmKeys).toContain('utm_source');
  });

  it('id corrélable, stable, non réversible (même téléphone → même id)', () => {
    const id1 = leadLogId('+212612345678');
    const id2 = leadLogId('+212612345678');
    const id3 = leadLogId('+212699999999');
    expect(id1).toBe(id2);
    expect(id1).not.toBe(id3);
    // Hash court hex, ne contient pas le numéro.
    expect(id1).not.toContain('612345678');
    expect(id1).toMatch(/^[0-9a-f]{8}$/);
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

  it('hache téléphone + ville en SHA-256, ne fuite jamais la PII en clair (ERR111)', async () => {
    let sentBody = '';
    const fetchFn = vi.fn(async (_url: unknown, init?: RequestInit) => {
      sentBody = String(init?.body);
      return new Response('ok');
    }) as unknown as typeof fetch;
    const record = buildLeadRecord(makeLead(), band, new Date());
    await fireCapi(record, env, fetchFn);
    const payload = JSON.parse(sentBody);
    // PII en clair JAMAIS présente.
    expect(sentBody).not.toContain('+212612345678');
    expect(sentBody).not.toContain('612345678');
    expect(sentBody).not.toContain('Casablanca');
    expect(payload).not.toHaveProperty('phoneE164');
    expect(payload).not.toHaveProperty('city');
    // Champs hachés présents (noms spec Meta) et conformes au hash attendu.
    expect(payload.ph).toBe(await hashPhoneForCapi(record.phoneE164));
    expect(payload.ct).toBe(await hashCityForCapi(record.city));
    expect(payload.ph).toMatch(/^[0-9a-f]{64}$/);
    expect(payload.ct).toMatch(/^[0-9a-f]{64}$/);
  });

  it('normalise selon la spec Meta avant de hacher (chiffres only / minuscules sans espaces)', async () => {
    // Le téléphone est haché sur les chiffres seuls (sans « + »).
    const knownPhone = await hashPhoneForCapi('+212612345678');
    // SHA-256("212612345678") — vérifié indépendamment via Web Crypto.
    const expectedPhone = await (async () => {
      const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('212612345678'));
      return Array.from(new Uint8Array(d)).map((b) => b.toString(16).padStart(2, '0')).join('');
    })();
    expect(knownPhone).toBe(expectedPhone);
    // La ville : minuscules, espaces/ponctuation retirés ("Casa Blanca" → "casablanca").
    expect(await hashCityForCapi('Casa Blanca')).toBe(await hashCityForCapi('casablanca'));
    expect(await hashCityForCapi('  CASABLANCA  ')).toBe(await hashCityForCapi('casablanca'));
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
