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

// ——— WJ30 — validateLead ne JETTE plus les champs capturés : pass-through validé ———
describe('WJ30 — validateLead élargi : les champs capturés passent, le garbage tombe', () => {
  const widened = {
    ...validBody,
    email: 'karim@example.com',
    factureHiver: 1450.5,
    eteDifferente: true,
    factureEte: 2600,
    billKwh: 9000,
    raccordement: 'triphase',
    adresse: 'Maârif, Casablanca, Maroc',
    mode: 'professionnel',
    langue_preferee: 'ar',
    roofPoint: { lat: 33.5731, lng: -7.6298 },
    roofOutline: [
      [33.5731, -7.6298],
      [33.5732, -7.6298],
      [33.5732, -7.6297],
    ],
  };

  it('transmet e-mail, factures exactes, kWh, raccordement, adresse, mode, langue, GPS et contour', () => {
    const r = validateLead(widened);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.email).toBe('karim@example.com');
    expect(r.lead.factureHiver).toBe(1450.5);
    expect(r.lead.eteDifferente).toBe(true);
    expect(r.lead.factureEte).toBe(2600);
    expect(r.lead.billKwh).toBe(9000);
    expect(r.lead.raccordement).toBe('triphase');
    expect(r.lead.adresse).toBe('Maârif, Casablanca, Maroc');
    expect(r.lead.mode).toBe('professionnel');
    expect(r.lead.langue_preferee).toBe('ar');
    expect(r.lead.roofPoint).toEqual({ lat: 33.5731, lng: -7.6298 });
    // le repère validé alimente aussi gpsLat/gpsLng
    expect(r.lead.gpsLat).toBe(33.5731);
    expect(r.lead.gpsLng).toBe(-7.6298);
    expect(r.lead.roofOutline).toHaveLength(3);
  });

  it('un lead SANS champ facultatif garde exactement la forme d\'hier (aucune clé ajoutée)', () => {
    const r = validateLead(validBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    for (const k of ['email', 'factureHiver', 'factureEte', 'eteDifferente', 'billKwh',
      'raccordement', 'adresse', 'mode', 'langue_preferee', 'roofPoint', 'gpsLat', 'gpsLng', 'roofOutline']) {
      expect(r.lead).not.toHaveProperty(k);
    }
  });

  it('un champ facultatif MALFORMÉ est écarté SANS faire échouer le lead', () => {
    const r = validateLead({
      ...validBody,
      email: 'pas-un-email',
      factureHiver: -50,
      billKwh: 'abc',
      raccordement: 'pentaphase',
      mode: 'martien',
      langue_preferee: 'en',
      roofPoint: { lat: 'x', lng: null },
      roofOutline: [[1]],
    });
    expect(r.ok).toBe(true); // JAMAIS bloquant
    if (!r.ok) return;
    for (const k of ['email', 'factureHiver', 'billKwh', 'raccordement', 'mode',
      'langue_preferee', 'roofPoint', 'roofOutline']) {
      expect(r.lead).not.toHaveProperty(k);
    }
  });

  it('un GPS hors du Maroc est du garbage : écarté, lead intact', () => {
    const r = validateLead({
      ...validBody,
      roofPoint: { lat: 48.85, lng: 2.35 }, // Paris — hors bornes
      gpsLat: 0,
      gpsLng: 90,
      roofOutline: [
        [0, 0],
        [0, 0],
        [0, 0],
      ],
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead).not.toHaveProperty('roofPoint');
    expect(r.lead).not.toHaveProperty('gpsLat');
    expect(r.lead).not.toHaveProperty('gpsLng');
    expect(r.lead).not.toHaveProperty('roofOutline');
  });

  it('été NON différent ⇒ factureEte null même si une valeur résiduelle est envoyée', () => {
    const r = validateLead({ ...validBody, eteDifferente: false, factureEte: 9999 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.eteDifferente).toBe(false);
    expect(r.lead.factureEte).toBeNull();
  });

  it('le contour est borné (200 sommets max) et exige 3 paires valides', () => {
    const many = Array.from({ length: 500 }, (_, i) => [33.5 + i * 1e-6, -7.6]);
    const r = validateLead({ ...validBody, roofOutline: many });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect((r.lead.roofOutline ?? []).length).toBeLessThanOrEqual(200);
    const r2 = validateLead({ ...validBody, roofOutline: [[33.5, -7.6], [33.5, -7.6]] });
    expect(r2.ok).toBe(true);
    if (!r2.ok) return;
    expect(r2.lead).not.toHaveProperty('roofOutline');
  });

  it('le record transmis au webhook porte les champs élargis (buildLeadRecord les conserve)', () => {
    const v = validateLead(widened);
    if (!v.ok) throw new Error('fixture invalide');
    const record = buildLeadRecord(v.lead, { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' }, new Date());
    expect(record.email).toBe('karim@example.com');
    expect(record.mode).toBe('professionnel');
    expect(record.langue_preferee).toBe('ar');
    expect(record.factureHiver).toBe(1450.5);
    expect(record.roofPoint).toEqual({ lat: 33.5731, lng: -7.6298 });
    // le contrat existant tient toujours
    expect(record.qualified).toBe(true);
    expect(record.fbclid).toBe('fb.1.123.abc');
  });
});

// ——— WJ31 — validateLead élargi encore : questions best-in-world facultatives ———
describe('WJ31 — validateLead élargi : distributeur, ombrage, âge toit, puces, qualificateurs', () => {
  const widened31 = {
    ...validBody,
    distributeur: 'lydec',
    roofAgeYears: 12,
    ombrage: 'partiel',
    futureLoads: ['clim', 've'],
    batteryInterest: true,
    occupantType: 'proprietaire',
    projectTiming: '3mois',
    financingIntent: 'financement',
    hasMeterPhoto: true,
  };

  it('transmet distributeur, ombrage, âge du toit, charges futures, batterie, qualificateurs et financement', () => {
    const r = validateLead(widened31);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.distributeur).toBe('lydec');
    expect(r.lead.roofAgeYears).toBe(12);
    expect(r.lead.ombrage).toBe('partiel');
    expect(r.lead.futureLoads).toEqual(['clim', 've']);
    expect(r.lead.batteryInterest).toBe(true);
    expect(r.lead.occupantType).toBe('proprietaire');
    expect(r.lead.projectTiming).toBe('3mois');
    expect(r.lead.financingIntent).toBe('financement');
    expect(r.lead.hasMeterPhoto).toBe(true);
  });

  it('un lead SANS ces champs garde exactement la forme d\'hier (aucune clé ajoutée)', () => {
    const r = validateLead(validBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    for (const k of ['distributeur', 'roofAgeYears', 'ombrage', 'futureLoads',
      'batteryInterest', 'occupantType', 'projectTiming', 'financingIntent', 'hasMeterPhoto']) {
      expect(r.lead).not.toHaveProperty(k);
    }
  });

  it('un champ facultatif MALFORMÉ est écarté SANS faire échouer le lead', () => {
    const r = validateLead({
      ...validBody,
      distributeur: 'iam', // pas un distributeur électrique connu
      roofAgeYears: -5,
      ombrage: 'beaucoup',
      futureLoads: ['jacuzzi', 42, 'clim'], // seul 'clim' est valide
      occupantType: 'invite',
      projectTiming: 'un jour',
      financingIntent: 'crypto',
    });
    expect(r.ok).toBe(true); // JAMAIS bloquant
    if (!r.ok) return;
    expect(r.lead).not.toHaveProperty('distributeur');
    expect(r.lead).not.toHaveProperty('roofAgeYears');
    expect(r.lead).not.toHaveProperty('ombrage');
    expect(r.lead.futureLoads).toEqual(['clim']); // le garbage est filtré, le valide garde
    expect(r.lead).not.toHaveProperty('occupantType');
    expect(r.lead).not.toHaveProperty('projectTiming');
    expect(r.lead).not.toHaveProperty('financingIntent');
  });

  it('roofAgeYears hors bornes (> 100 ans) est écarté', () => {
    const r = validateLead({ ...validBody, roofAgeYears: 500 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead).not.toHaveProperty('roofAgeYears');
  });

  it('futureLoads déduplique et ignore un tableau vide', () => {
    const r = validateLead({ ...validBody, futureLoads: ['clim', 'clim', 'pompe'] });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.futureLoads).toEqual(['clim', 'pompe']);

    const r2 = validateLead({ ...validBody, futureLoads: [] });
    expect(r2.ok).toBe(true);
    if (!r2.ok) return;
    expect(r2.lead).not.toHaveProperty('futureLoads');
  });

  it('le record transmis au webhook porte les champs WJ31 (buildLeadRecord les conserve)', () => {
    const v = validateLead(widened31);
    if (!v.ok) throw new Error('fixture invalide');
    const record = buildLeadRecord(v.lead, { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' }, new Date());
    expect(record.distributeur).toBe('lydec');
    expect(record.ombrage).toBe('partiel');
    expect(record.futureLoads).toEqual(['clim', 've']);
    expect(record.occupantType).toBe('proprietaire');
    // le contrat existant tient toujours
    expect(record.qualified).toBe(true);
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
