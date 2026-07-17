// WJ123 — Panneau INDUSTRIEL v2 (équipes, MT, réalisme).
// Pattern d'équipes → PLAFOND d'autoconsommation honnête (un 3x8 ne voit plus
// l'autoconso d'un bureau). Ligne d'injection 82-21 (QX50) OFF par défaut,
// mirroir des constantes backend. Payload equipes/weekend/groupe traverse validateLead.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { estimatePro, SHIFT_DAY_SHARE_CEILING } from '../src/lib/estimatorPro';
import { EQUIPES_MODES, validateLead } from '../src/lib/lead';
import {
  injectionAnnuelle,
  netTarifDhKwh,
  PLAFOND_INJECTION_PCT,
  MENTION_82_21,
  ANRE_TARIF_HORS_POINTE,
  FRAIS_RESEAU_DH_KWH,
} from '../src/lib/constants82_21';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

describe('WJ123 — plafonds day-share par équipe : MONOTONES 1x8 > 2x8 > continu', () => {
  it('un 1x8 (jour) plafonne PLUS HAUT qu’un 2x8, lui-même plus haut qu’un continu', () => {
    expect(SHIFT_DAY_SHARE_CEILING['1x8']).toBeGreaterThan(SHIFT_DAY_SHARE_CEILING['2x8']);
    expect(SHIFT_DAY_SHARE_CEILING['2x8']).toBeGreaterThan(SHIFT_DAY_SHARE_CEILING['continu']);
    // 3x8 = 3 postes = couverture 24h → même palier bas que le continu.
    expect(SHIFT_DAY_SHARE_CEILING['3x8']).toBeLessThanOrEqual(SHIFT_DAY_SHARE_CEILING['2x8']);
  });

  it('les paliers restent dans les fourchettes citées (1x8 70-85 %, 2x8 55-70 %, continu 25-40 %)', () => {
    expect(SHIFT_DAY_SHARE_CEILING['1x8']).toBeGreaterThanOrEqual(0.70);
    expect(SHIFT_DAY_SHARE_CEILING['1x8']).toBeLessThanOrEqual(0.85);
    expect(SHIFT_DAY_SHARE_CEILING['2x8']).toBeGreaterThanOrEqual(0.55);
    expect(SHIFT_DAY_SHARE_CEILING['2x8']).toBeLessThanOrEqual(0.70);
    expect(SHIFT_DAY_SHARE_CEILING['continu']).toBeGreaterThanOrEqual(0.25);
    expect(SHIFT_DAY_SHARE_CEILING['continu']).toBeLessThanOrEqual(0.40);
  });
});

describe("WJ123 — EQUIPES_MODES : enum ALIGNÉ sur le webhook QX51", () => {
  it("est EXACTEMENT ('1x8','2x8','3x8','continu') — weekend est un booléen séparé", () => {
    expect([...EQUIPES_MODES]).toEqual(['1x8', '2x8', '3x8', 'continu']);
    // Jamais une 5e valeur combinée type '3x8+weekend'.
    expect(EQUIPES_MODES).not.toContain('3x8+weekend');
  });
});

describe('WJ123 — estimatePro : un 3x8 ne voit plus l’autoconso d’un bureau', () => {
  const bill = { monthlyMad: 50_000, raccordement: 'bt' as const };

  it('un 3x8 couvre BEAUCOUP moins qu’un site sans équipe déclarée (défaut 0.80)', () => {
    const shift3x8 = estimatePro({ ...bill, equipes: '3x8' });
    const noShift = estimatePro({ ...bill });
    expect(shift3x8.ok && noShift.ok).toBe(true);
    if (shift3x8.ok && noShift.ok) {
      expect(shift3x8.hypotheses.dayShare).toBeCloseTo(0.325, 5);
      expect(noShift.hypotheses.dayShare).toBeCloseTo(0.8, 5);
      expect(shift3x8.tauxCouverture).toBeLessThan(noShift.tauxCouverture);
    }
  });

  it('la couverture suit l’ordre des équipes : 1x8 > 2x8 > 3x8', () => {
    const s1 = estimatePro({ ...bill, equipes: '1x8' });
    const s2 = estimatePro({ ...bill, equipes: '2x8' });
    const s3 = estimatePro({ ...bill, equipes: '3x8' });
    expect(s1.ok && s2.ok && s3.ok).toBe(true);
    if (s1.ok && s2.ok && s3.ok) {
      expect(s1.tauxCouverture).toBeGreaterThan(s2.tauxCouverture);
      expect(s2.tauxCouverture).toBeGreaterThan(s3.tauxCouverture);
    }
  });
});

describe('WJ123 — injection 82-21 (QX50) : constantes MIROIR + OFF par défaut', () => {
  it('les constantes correspondent au module backend (plafond 20 %, tarif net honnête)', () => {
    expect(PLAFOND_INJECTION_PCT).toBe(20);
    expect(MENTION_82_21).toBe('Tarif ANRE 03/2026-02/2027, plafond en révision');
    // tarif net = rachat hors pointe − frais réseau, jamais négatif.
    expect(netTarifDhKwh(false)).toBeCloseTo(ANRE_TARIF_HORS_POINTE - FRAIS_RESEAU_DH_KWH, 6);
    expect(netTarifDhKwh(false)).toBeGreaterThan(0);
  });

  it('injectionAnnuelle plafonne le surplus à 20 % de la production', () => {
    // Production 100 000 kWh, autoconsommé 50 000 → surplus 50 000 mais plafonné à 20 000.
    const inj = injectionAnnuelle(100_000, 50_000);
    expect(inj.kwh).toBe(20_000);
    expect(inj.dh).toBe(Math.round(20_000 * netTarifDhKwh(false)));
  });

  it('surplus nul (autoconso ≥ production) → 0 injection', () => {
    expect(injectionAnnuelle(80_000, 90_000)).toEqual({ kwh: 0, dh: 0 });
  });

  it("estimatePro n'expose PAS de ligne d'injection par défaut (parcours public gaté)", () => {
    const est = estimatePro({ monthlyMad: 50_000, equipes: '1x8' });
    expect(est.ok).toBe(true);
    if (est.ok) expect(est.injectionPotential).toBeUndefined();
  });

  it("estimatePro expose la ligne d'injection UNIQUEMENT sur demande, avec sa mention", () => {
    const est = estimatePro({ monthlyMad: 50_000, equipes: '1x8', enableInjection: true });
    expect(est.ok).toBe(true);
    if (est.ok) {
      expect(est.injectionPotential).toBeDefined();
      expect(est.injectionPotential?.mention).toBe(MENTION_82_21);
      // Le potentiel injecté ne dépasse jamais 20 % de la production.
      expect(est.injectionPotential!.kwh).toBeLessThanOrEqual(Math.round(est.prodAnnuelleKwh * 0.2) + 1);
    }
  });
});

describe('WJ123 — validateLead : equipes/weekend/groupe traversent la liste blanche', () => {
  const base = {
    fullName: 'Reda K.', phone: '0612345678', city: 'Casablanca',
    roofType: 'autre', billRange: 'gt10000', consent: true, mode: 'industriel',
  };

  it('un pattern d’équipes valide + weekend + groupe kVA + diesel survivent', () => {
    const r = validateLead({
      ...base, equipes: '3x8', weekend: true, cosPhiConnu: 0.92,
      groupeKva: 250, dieselDhMois: 30_000, surfaceToitureM2: 1200, ombriere: true,
    });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.lead.equipes).toBe('3x8');
      expect(r.lead.weekend).toBe(true);
      expect(r.lead.cosPhiConnu).toBe(0.92);
      expect(r.lead.groupeKva).toBe(250);
      expect(r.lead.dieselDhMois).toBe(30_000);
      expect(r.lead.surfaceToitureM2).toBe(1200);
      expect(r.lead.ombriere).toBe(true);
    }
  });

  it('un pattern d’équipes inconnu est ÉCARTÉ en silence (jamais bloquant)', () => {
    const r = validateLead({ ...base, equipes: '4x8' });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.lead.equipes).toBeUndefined();
  });

  it('cos φ > 1 (impossible) est écarté (borne haute = 1)', () => {
    const r = validateLead({ ...base, cosPhiConnu: 1.5 });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.lead.cosPhiConnu).toBeUndefined();
  });
});

describe.each(LOCALES)('WJ123 — panneau industriel v2 dans mon-toit.astro (%s)', (_locale, rel) => {
  const src = read(rel);

  it('a les cartes de pattern d’équipes + le toggle weekend séparé', () => {
    expect(src).toContain('mt-equipes cine-card');
    for (const v of ['1x8', '2x8', '3x8', 'continu']) {
      expect(src).toContain(`data-value="${v}"`);
    }
    expect(src).toContain('id="mt-weekend"');
  });

  it('a les champs groupe électrogène (kVA + diesel) et cos φ', () => {
    expect(src).toContain('id="mt-groupe-kva"');
    expect(src).toContain('id="mt-diesel-dh"');
    expect(src).toContain('id="mt-cos-phi"');
  });

  it('la micro-copy dit que le solaire déplace les heures pleines (~1,01), la pointe seulement avec batterie', () => {
    expect(src).toMatch(/1[.,]01/);
  });

  it('l’estimateur reçoit equipes ; le payload envoie equipes + weekend', () => {
    expect(src).toContain("equipes: (mode === 'industriel' || mode === 'professionnel') && equipes ? equipes : undefined");
    expect(src).toContain("equipes: (mode === 'industriel' || mode === 'professionnel') ? (equipes || undefined) : undefined");
    expect(src).toContain("weekend: (mode === 'industriel' || mode === 'professionnel')");
  });
});
