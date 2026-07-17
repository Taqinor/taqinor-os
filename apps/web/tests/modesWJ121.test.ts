// WJ121 — 4 vrais modes au départ du parcours /devis/mon-toit.
// La carte « Professionnel » est scindée en 🏭 Industriel (usine, production)
// et 🏪 Commercial (hôtel, commerce, services) — FR/EN/AR. Le site n'ÉMET plus
// jamais 'professionnel' (les sessions en cours sont migrées vers 'industriel'
// à la réhydratation) mais l'alias reste ACCEPTÉ côté validation (compat
// sessions en vol / anciens liens ; le backend mappe déjà
// professionnel→industriel). Les règles billRange/plafond/qualification
// traitent industriel ET commercial exactement comme professionnel se
// comportait.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
  LEAD_MODES,
  MAX_BILL_BY_MODE,
  buildLeadRecord,
  validateLead,
} from '../src/lib/lead';
import { localEstimateBand } from '../src/lib/billRange';

// ——— cloudflare:workers mock (même patron que captureWJ.test.ts) ———
const mockEnv: Record<string, string> = {};
vi.mock('cloudflare:workers', () => ({
  get env() {
    return mockEnv;
  },
  waitUntil: undefined,
}));
import { resetRateLimit } from '../src/lib/rateLimit';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

describe('WJ121 — LEAD_MODES : 4 modes émis + alias hérité accepté', () => {
  it('contient les 4 modes émis par le site', () => {
    for (const m of ['residentiel', 'industriel', 'commercial', 'agricole']) {
      expect(LEAD_MODES).toContain(m);
    }
  });

  it("garde 'professionnel' ACCEPTÉ (compat sessions en vol / anciens liens)", () => {
    expect(LEAD_MODES).toContain('professionnel');
  });
});

describe('WJ121 — MAX_BILL_BY_MODE : industriel et commercial reprennent le plafond pro', () => {
  it('industriel et commercial ont chacun une entrée = le plafond professionnel existant (1 M MAD, jamais un chiffre inventé)', () => {
    expect(MAX_BILL_BY_MODE.industriel).toBe(MAX_BILL_BY_MODE.professionnel);
    expect(MAX_BILL_BY_MODE.commercial).toBe(MAX_BILL_BY_MODE.professionnel);
    expect(MAX_BILL_BY_MODE.industriel).toBe(1_000_000);
    expect(MAX_BILL_BY_MODE.commercial).toBe(1_000_000);
  });

  it('résidentiel/agricole gardent le plafond historique 200 000 (inchangé)', () => {
    expect(MAX_BILL_BY_MODE.residentiel).toBe(200_000);
    expect(MAX_BILL_BY_MODE.agricole).toBe(200_000);
  });
});

describe('WJ121 — billRange/qualification : industriel et commercial = même règle que professionnel', () => {
  const base = {
    fullName: 'Reda K.',
    phone: '0612345678',
    city: 'Casablanca',
    roofType: 'autre',
    consent: true,
  };

  it('billRange reste REQUIS en industriel ET en commercial (comme professionnel hier)', () => {
    for (const mode of ['industriel', 'commercial', 'professionnel']) {
      const r = validateLead({ ...base, mode });
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.errors).toHaveProperty('billRange');
    }
  });

  it('billRange reste FACULTATIF en agricole (comportement WJ111/QX inchangé)', () => {
    const r = validateLead({ ...base, mode: 'agricole' });
    expect(r.ok).toBe(true);
  });

  it('le mode industriel/commercial validé survit tel quel dans le lead', () => {
    for (const mode of ['industriel', 'commercial']) {
      const r = validateLead({ ...base, mode, billRange: '1500-3000' });
      expect(r.ok).toBe(true);
      if (r.ok) expect(r.lead.mode).toBe(mode);
    }
  });

  it('la qualification (seuil 1 000 MAD) est IDENTIQUE pour industriel/commercial/professionnel', () => {
    const now = new Date('2026-07-16T12:00:00Z');
    for (const mode of ['industriel', 'commercial', 'professionnel']) {
      const over = validateLead({ ...base, mode, billRange: '1500-3000' });
      expect(over.ok).toBe(true);
      if (over.ok) expect(buildLeadRecord(over.lead, localEstimateBand('1500-3000'), now).qualified).toBe(true);
      const under = validateLead({ ...base, mode, billRange: 'lt800' });
      expect(under.ok).toBe(true);
      if (under.ok) expect(buildLeadRecord(under.lead, localEstimateBand('lt800'), now).qualified).toBe(false);
    }
  });
});

// ——— Done du plan : « leads commercial typés `commercial` (et industriel
// `industriel`) dans le CRM » — prouvé sur le VRAI endpoint capture-lead
// (le corps forwardé au webhook porte le mode tel quel). ———
describe('WJ121 — capture-lead : le CRM reçoit mode=commercial / mode=industriel', () => {
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
    roofType: 'autre',
    billRange: 'gt10000',
    consent: true,
  };

  beforeEach(() => {
    resetRateLimit();
    for (const k of Object.keys(mockEnv)) delete mockEnv[k];
    mockEnv.LEAD_WEBHOOK_URL = 'https://crm.example/hook';
    mockEnv.LEAD_WEBHOOK_SECRET = 's3cret';
  });
  afterEach(() => vi.unstubAllGlobals());

  for (const mode of ['commercial', 'industriel'] as const) {
    it(`un lead ${mode} part au webhook typé mode='${mode}' (jamais 'professionnel')`, async () => {
      let forwarded: Record<string, unknown> | null = null;
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url: string, init?: { body?: string }) => {
          if (String(url).includes('crm.example/hook') && init?.body) forwarded = JSON.parse(init.body);
          return { ok: true, json: async () => ({}) } as unknown as Response;
        }),
      );
      const { status, json } = await call({ ...qualified, mode });
      expect(status).toBe(200);
      expect(json.ok).toBe(true);
      const rec = forwarded as unknown as Record<string, unknown>;
      expect(rec).not.toBeNull();
      expect(rec.mode).toBe(mode);
      expect(rec.qualified).toBe(true);
    });
  }
});

describe.each(LOCALES)('WJ121 — 4 cartes de mode dans mon-toit.astro (%s)', (_locale, rel) => {
  const src = read(rel);

  it('le sélecteur propose EXACTEMENT les 4 modes émis (residentiel/industriel/commercial/agricole)', () => {
    for (const id of ['residentiel', 'industriel', 'commercial', 'agricole']) {
      expect(src).toContain(`id: '${id}'`);
    }
    // Plus AUCUNE carte 'professionnel' : le site ne peut plus l'émettre.
    expect(src).not.toContain("id: 'professionnel'");
  });

  it('les deux nouvelles cartes portent le framing du plan (🏭 usine/production, 🏪 hôtel/commerce/services)', () => {
    expect(src).toContain('🏭');
    expect(src).toContain('🏪');
  });

  it("les sessions en cours sont migrées : 'professionnel' réhydraté → 'industriel'", () => {
    expect(src).toContain("if (mode === 'professionnel') mode = 'industriel';");
  });

  it('industriel et commercial partagent le MOTEUR pro via isProMode ; WJ122 : commercial a son PROPRE panneau', () => {
    expect(src).toContain('function isProMode(');
    // WJ122 — le panneau pro ne s'affiche plus que pour industriel (+ alias
    // professionnel) ; 'commercial' a désormais son propre sous-panneau. Le
    // MOTEUR (computeProEstimate) reste partagé via isProMode côté CALCUL.
    expect(src).toContain("pro.hidden = !(m === 'industriel' || m === 'professionnel');");
    expect(src).toContain("commercial.hidden = m !== 'commercial';");
    expect(src).toContain('isProMode(mode)');
    // 'professionnel' n'est JAMAIS traité comme un mode AUTONOME : chaque
    // occurrence du littéral est soit la ligne de migration, soit une garde
    // d'alias industriel `mode === 'industriel' || mode === 'professionnel'`
    // (WJ123 — professionnel = alias hérité d'industriel pour les champs de
    // charge industriels). Aucun branchement métier sur professionnel seul.
    const proLiteral = src.match(/mode === 'professionnel'/g) ?? [];
    const aliasGuards = src.match(/mode === 'industriel' \|\| mode === 'professionnel'/g) ?? [];
    const migration = src.match(/if \(mode === 'professionnel'\) mode = 'industriel'/g) ?? [];
    expect(proLiteral.length).toBe(aliasGuards.length + migration.length);
    expect(migration).toHaveLength(1); // la migration existe toujours
  });

  it('le fil d’étapes a un libellé par mode pour industriel ET commercial', () => {
    expect(src).toMatch(/industriel: \['[^']+', '[^']+', '[^']+'\]/);
    expect(src).toMatch(/commercial: \['[^']+', '[^']+', '[^']+'\]/);
  });

  it('la grille passe à 4 cartes (2×2 dès sm:)', () => {
    expect(src).toContain('id="mt-mode-grid"');
    expect(src).toMatch(/mt-mode-grid" class="[^"]*sm:grid-cols-2/);
  });
});
