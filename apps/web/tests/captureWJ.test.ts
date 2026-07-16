// WJ1/WJ3/WJ4/WJ5 — couverture de la refonte du parcours de capture /devis/mon-toit.
//
// On NE teste PAS le DOM Astro ici (couvert par les boots W112/W2/W3) : on prouve
// les invariants LOGIQUES qui doivent rester vrais après l'élévation —
//  - WJ1 : l'estimation instantanée vient du VRAI moteur (estimatorBrainV2) et donne
//    une fourchette PLAUSIBLE non fabriquée, à partir de la facture SEULE ;
//  - WJ3 : le deeplink WhatsApp est correctement construit avec l'estimation ;
//  - WJ4 : le contrat webhook + le seuil 1 000 MAD restent intacts (capture-lead) ;
//  - WJ5 : un lead sous le seuil n'atteint jamais le CRM (réponse honnête).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { estimateFromBill, formatMadRange } from '../src/lib/billEstimate';
// V1 (estimatorBrain.ts, labo) supprimé — billToAnnualKwh vit dans V2 (corps
// identique, parité prouvée avant suppression).
import { billToAnnualKwh } from '../src/lib/estimatorBrainV2';
import { qualifiesForCrm } from '../src/lib/billRange';
import { captureWhatsappText, whatsappLink } from '../src/lib/whatsapp';

// ——— cloudflare:workers mock (réutilisé pour le test d'endpoint capture-lead) ———
const mockEnv: Record<string, string> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));
import { resetRateLimit } from '../src/lib/rateLimit';

describe('WJ1 — estimation instantanée honnête à partir de la facture SEULE', () => {
  it('une facture connue produit une fourchette PLAUSIBLE et non fabriquée', () => {
    const est = estimateFromBill(2000); // 2 000 MAD/mois — villa moyenne
    expect(est).not.toBeNull();
    const e = est!;
    // kWc dans une plage réaliste pour ~2 000 MAD/mois (ni absurde ni nul).
    expect(e.kwc).toBeGreaterThan(2);
    expect(e.kwc).toBeLessThan(20);
    // Production cohérente : ~1 400–1 900 kWh/kWc/an au Maroc.
    const yieldPerKwc = e.productionKwhYr / e.kwc;
    expect(yieldPerKwc).toBeGreaterThan(1300);
    expect(yieldPerKwc).toBeLessThan(2000);
    // Économies > 0 et BORNÉES par la facture annuelle (loi 82-21, autoconso).
    expect(e.savingsHigh).toBeGreaterThan(0);
    expect(e.savingsLow).toBeLessThanOrEqual(e.savingsHigh);
    expect(e.savingsHigh).toBeLessThanOrEqual(2000 * 12);
    // Le mensuel dérive du même chiffre.
    expect(e.savingsMonthlyHigh).toBeLessThanOrEqual(e.savingsHigh);
    expect(e.paybackLabel).toMatch(/ans/);
  });

  it('une facture plus grosse implique plus de kWc et plus d\'économies (monotone)', () => {
    const small = estimateFromBill(1200)!;
    const big = estimateFromBill(6000)!;
    expect(big.kwc).toBeGreaterThan(small.kwc);
    expect(big.savingsHigh).toBeGreaterThan(small.savingsHigh);
  });

  it('le besoin annuel utilisé est COHÉRENT avec le cerveau (billToAnnualKwh)', () => {
    // L'estimation s'appuie sur le même besoin annuel que le moteur testé.
    const target = billToAnnualKwh(3000);
    expect(target).toBeGreaterThan(0);
    const e = estimateFromBill(3000)!;
    // Production couvre globalement le besoin (dimensionnée cible + marge).
    expect(e.productionKwhYr).toBeGreaterThan(target * 0.8);
  });

  it('une facture absente / non chiffrable ⇒ null (jamais une valeur inventée)', () => {
    expect(estimateFromBill(0)).toBeNull();
    expect(estimateFromBill(-50)).toBeNull();
    expect(estimateFromBill(NaN)).toBeNull();
    expect(estimateFromBill(Number.POSITIVE_INFINITY)).toBeNull();
  });

  it('un repère (lat) affine la production sans casser la fourchette', () => {
    const casa = estimateFromBill(2500, { lat: 33.5 })!;
    const agadir = estimateFromBill(2500, { lat: 30.4 })!;
    // Les deux restent plausibles ; la latitude d'Agadir (plus ensoleillée) ne
    // dégrade pas la production par kWc.
    expect(agadir.productionKwhYr / agadir.kwc).toBeGreaterThanOrEqual(
      casa.productionKwhYr / casa.kwc - 1,
    );
  });

  it('formatMadRange rend une fourchette lisible', () => {
    expect(formatMadRange(1200, 1800)).toContain('–');
    expect(formatMadRange(0, 0)).toBe('—');
    expect(formatMadRange(1500, 1500)).not.toContain('–');
  });
});

describe('WJ3 — deeplink WhatsApp prérempli avec l\'estimation', () => {
  it('construit un lien wa.me avec le texte d\'estimation encodé', () => {
    const text = captureWhatsappText({
      fullName: 'Reda K.',
      city: 'Casablanca',
      kwcLabel: '5 kWc',
      savingsLabel: '1 200 – 1 800 MAD/mois',
    });
    const url = whatsappLink('212661850410', text);
    expect(url).toMatch(/^https:\/\/wa\.me\/212661850410\?text=/);
    expect(decodeURIComponent(url)).toContain('Reda K.');
    expect(decodeURIComponent(url)).toContain('5 kWc');
    expect(decodeURIComponent(url)).toContain('Casablanca');
  });

  it('reste robuste sans estimation (pas de « undefined » dans le texte)', () => {
    const text = captureWhatsappText({ fullName: 'Sara', city: 'Rabat' });
    expect(text).not.toContain('undefined');
    expect(text).toContain('Sara');
  });
});

// ——— WJ4/WJ5 — l'endpoint capture-lead garde son contrat (seuil + webhook) ———
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
const qualified = {
  fullName: 'Reda K.',
  phone: '0612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

describe('WJ4/WJ5 — capture-lead : contrat webhook + seuil 1 000 MAD intacts', () => {
  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = 'https://crm.example/hook';
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
  });
  afterEach(() => vi.unstubAllGlobals());

  it('WJ4 — un lead qualifié SANS repère (address-only) atteint quand même le CRM', async () => {
    let forwarded: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: { body?: string }) => {
        if (String(url).includes('crm.example/hook') && init?.body) forwarded = JSON.parse(init.body);
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    // Aucun roofPoint/roofOutline : la soumission « adresse seule » doit passer.
    const { status, json } = await call({ ...qualified, adresse: 'Maârif, Casablanca' });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.qualified).toBe(true);
    const rec = forwarded as unknown as Record<string, unknown> | null;
    expect(rec).not.toBeNull();
    expect(rec).not.toHaveProperty('roofPoint'); // address-only : pas de repère
    expect(rec!.city).toBe('Casablanca');
  });

  it('WJ3 — e-mail valide + whatsappOptIn sont transmis au CRM', async () => {
    let forwarded: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: { body?: string }) => {
        if (String(url).includes('crm.example/hook') && init?.body) forwarded = JSON.parse(init.body);
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    await call({ ...qualified, email: 'reda@example.com', whatsappOptIn: true });
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec).not.toBeNull();
    expect(rec.email).toBe('reda@example.com');
    expect(rec.whatsappOptIn).toBe(true);
  });

  it('WJ3 — un e-mail invalide n\'est PAS joint (record propre)', async () => {
    let forwarded: Record<string, unknown> | null = null;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: { body?: string }) => {
        if (String(url).includes('crm.example/hook') && init?.body) forwarded = JSON.parse(init.body);
        return { ok: true, json: async () => ({}) } as unknown as Response;
      }),
    );
    await call({ ...qualified, email: 'pas-un-email' });
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec).not.toHaveProperty('email');
  });

  it('WJ30 — le webhook reçoit facture exacte, GPS, contour, mode, raccordement, e-mail ET langue', async () => {
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
      email: 'reda@example.com',
      factureHiver: 1450.5,
      eteDifferente: true,
      factureEte: 2600,
      billKwh: 9000,
      raccordement: 'triphase',
      mode: 'agricole',
      langue_preferee: 'ar',
      roofPoint: { lat: 31.63, lng: -8.0 },
      roofOutline: [
        [31.63, -8.0],
        [31.631, -8.0],
        [31.631, -7.999],
      ],
    });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec).not.toBeNull();
    // WJ30 — plus AUCUN champ capturé n'est jeté en route.
    expect(rec.email).toBe('reda@example.com');
    expect(rec.factureHiver).toBe(1450.5);
    expect(rec.eteDifferente).toBe(true);
    expect(rec.factureEte).toBe(2600);
    expect(rec.billKwh).toBe(9000);
    expect(rec.raccordement).toBe('triphase');
    expect(rec.mode).toBe('agricole');
    expect(rec.langue_preferee).toBe('ar');
    expect(rec.roofPoint).toEqual({ lat: 31.63, lng: -8.0 });
    expect(rec.gpsLat).toBe(31.63);
    expect(rec.gpsLng).toBe(-8.0);
    expect((rec.roofOutline as unknown[]).length).toBe(3);
    // …et le contrat existant tient (consentement horodaté + seuil).
    expect(rec.consent).toBe(true);
    expect(typeof rec.consentTimestamp).toBe('string');
    expect(rec.qualified).toBe(true);
  });

  it('WJ30 — un champ facultatif MALFORMÉ est écarté sans jamais faire échouer le lead', async () => {
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
      mode: 'martien',
      langue_preferee: 'en',
      roofPoint: { lat: 48.85, lng: 2.35 }, // hors Maroc → garbage
      billKwh: -3,
    });
    expect(status).toBe(200);
    expect(json.ok).toBe(true); // le lead passe, comme hier
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec).not.toHaveProperty('mode');
    expect(rec).not.toHaveProperty('langue_preferee');
    expect(rec).not.toHaveProperty('roofPoint');
    expect(rec).not.toHaveProperty('billKwh');
  });

  it('WJ31 — le webhook reçoit distributeur, kWh, ombrage, âge toit, charges futures, qualificateurs et financement', async () => {
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
      distributeur: 'onee',
      billKwh: 700,
      ombrage: 'aucun',
      roofAgeYears: 8,
      futureLoads: ['ve', 'pompe'],
      batteryInterest: true,
      occupantType: 'decideur',
      projectTiming: 'maintenant',
      financingIntent: 'comptant',
      hasMeterPhoto: true,
    });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    const rec = forwarded as unknown as Record<string, unknown>;
    expect(rec).not.toBeNull();
    expect(rec.distributeur).toBe('onee');
    expect(rec.billKwh).toBe(700);
    expect(rec.ombrage).toBe('aucun');
    expect(rec.roofAgeYears).toBe(8);
    expect(rec.futureLoads).toEqual(['ve', 'pompe']);
    expect(rec.batteryInterest).toBe(true);
    expect(rec.occupantType).toBe('decideur');
    expect(rec.projectTiming).toBe('maintenant');
    expect(rec.financingIntent).toBe('comptant');
    expect(rec.hasMeterPhoto).toBe(true);
    // …le contrat existant tient (consentement + seuil).
    expect(rec.consent).toBe(true);
    expect(rec.qualified).toBe(true);
  });

  it('WJ31 — skipper toutes les questions optionnelles ne bloque toujours pas le lead', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status, json } = await call({ ...qualified });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    expect(json.qualified).toBe(true);
  });

  it('WJ5 — un lead SOUS le seuil renvoie qualified=false et ne touche pas le CRM', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }) as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { status, json } = await call({ ...qualified, billRange: 'lt800' });
    expect(status).toBe(200);
    expect(json.ok).toBe(true);
    // Honnêteté WJ5 : la réponse expose qualified=false → l'écran montre le chemin
    // « sous le seuil » au lieu d'un faux « demande enregistrée ».
    expect(json.qualified).toBe(false);
    expect(qualifiesForCrm('lt800')).toBe(false);
    expect(fetchMock.mock.calls.filter((c) => String(c[0]).includes('crm.example/hook')).length).toBe(0);
  });
});
