// Parcours 3 profils — estimateur AGRICOLE pompage (lib/estimatorAgricole.ts,
// miroir solar.js CV_TO_KW / champFromKw / HEURES_POMPAGE_DEFAUT) + règles lead
// agricole (billRange facultatif, lead toujours qualifié, champs pompage
// sanitisés). Honnêteté : hydraulique manquante ⇒ ok:false, jamais un chiffre
// fabriqué ; compositions pompage sans onduleur ni batterie (règle ERP).
import { describe, expect, it } from 'vitest';
import {
  CV_STEPS,
  CV_TO_KW,
  HEURES_POMPAGE_DEFAUT,
  PANEL_W,
  PUMP_EFF,
  PV_FACTOR,
  estimateAgricole,
} from '../src/lib/estimatorAgricole';
import { buildLeadRecord, validateLead } from '../src/lib/lead';
import type { EstimateBand } from '../src/lib/billRange';

describe('estimateAgricole — constantes MIROIR de solar.js', () => {
  it('CV_TO_KW, heures par défaut, facteur champ et panneau identiques à l\'ERP', () => {
    expect(CV_TO_KW).toBe(0.7355);
    expect(HEURES_POMPAGE_DEFAUT).toBe(7);
    expect(PV_FACTOR).toBe(1.4);
    expect(PANEL_W).toBe(710);
  });
});

describe('estimateAgricole — HMT déclarée + débit déclaré', () => {
  it('60 m / 10 m³/h : pompe 5,5 CV, champ 1.4× miroir champFromKw', () => {
    const r = estimateAgricole({ hmtM: 60, debitM3h: 10 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.hmtM).toBe(60);
    expect(r.hmtEstimated).toBe(false);
    expect(r.debitM3h).toBe(10);
    // hydraulique = 10×60×2.725/1000 = 1.635 kW ; /0.55 = 2.97 kW ; 4.04 CV → palier 5.5.
    expect(r.pompeCv).toBe(5.5);
    // MIROIR EXACT champFromKw(5.5 × 0.7355) : kW 4.05, champ 5.67 kW,
    // 8 panneaux 710 W, kWc recalculé depuis les panneaux posés = 5.68.
    expect(r.pompeKw).toBe(4.05);
    expect(r.nbPanneaux).toBe(8);
    expect(r.champKwc).toBe(5.68);
    // m³/jour = débit × heures (défaut 7 h) — même règle que l'ERP.
    expect(r.heures).toBe(7);
    expect(r.m3Jour).toBe(70);
    expect(r.hypotheses).toEqual({ pumpEff: PUMP_EFF.immergee, pvFactor: 1.4 });
  });
});

describe('estimateAgricole — HMT estimée depuis la profondeur (flaggée)', () => {
  it('profondeur 40 + refoulement 5 → HMT = 45 × 1.10 = 49.5, hmtEstimated', () => {
    const r = estimateAgricole({ profondeurM: 40, refoulementM: 5, debitM3h: 8 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.hmtM).toBe(49.5);
    expect(r.hmtEstimated).toBe(true);
  });

  it('refoulement absent → défaut 2 m ; refoulement 0 accepté tel quel', () => {
    const def = estimateAgricole({ profondeurM: 40, debitM3h: 8 });
    expect(def.ok).toBe(true);
    if (!def.ok) return;
    expect(def.hmtM).toBe(46.2); // (40 + 2) × 1.10
    const zero = estimateAgricole({ profondeurM: 40, refoulementM: 0, debitM3h: 8 });
    expect(zero.ok).toBe(true);
    if (!zero.ok) return;
    expect(zero.hmtM).toBe(44); // (40 + 0) × 1.10
  });

  it('la HMT déclarée PRIME sur la profondeur (jamais ré-estimée)', () => {
    const r = estimateAgricole({ hmtM: 55, profondeurM: 200, debitM3h: 8 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.hmtM).toBe(55);
    expect(r.hmtEstimated).toBe(false);
  });
});

describe('estimateAgricole — besoin m³/jour et heures de pompage', () => {
  it('besoin 35 m³/j sans débit → débit = besoin / 7 h ; m³/jour rend le besoin', () => {
    const r = estimateAgricole({ hmtM: 50, besoinM3j: 35 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.debitM3h).toBe(5);
    expect(r.m3Jour).toBe(35);
    expect(r.heures).toBe(7);
  });

  it('heures éditables : 40 m³/j sur 8 h → débit 5 m³/h, m³/jour 40', () => {
    const r = estimateAgricole({ hmtM: 50, besoinM3j: 40, heuresPompage: 8 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.debitM3h).toBe(5);
    expect(r.m3Jour).toBe(40);
    expect(r.heures).toBe(8);
  });
});

describe('estimateAgricole — paliers CV commerciaux', () => {
  it('petite pompe → plus petit palier 0.5 CV, champ jamais sous 2 panneaux', () => {
    const r = estimateAgricole({ hmtM: 20, debitM3h: 2 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.pompeCv).toBe(0.5);
    expect(r.nbPanneaux).toBe(2); // plancher champFromKw (min 2 panneaux)
    expect(r.champKwc).toBe(1.42); // 2 × 710 W recalculés
  });

  it('le palier retenu est toujours ≥ au besoin (jamais sous-dimensionné)', () => {
    for (const [hmt, debit] of [[30, 5], [80, 12], [120, 20], [200, 40]] as const) {
      const r = estimateAgricole({ hmtM: hmt, debitM3h: debit });
      expect(r.ok).toBe(true);
      if (!r.ok) continue;
      const needed = (debit * hmt * 2.725) / 1000 / PUMP_EFF.immergee / CV_TO_KW;
      expect(r.pompeCv).toBeGreaterThanOrEqual(needed);
      expect(CV_STEPS.includes(r.pompeCv as (typeof CV_STEPS)[number]) || r.pompeCv > 30).toBe(true);
    }
  });

  it('pompe de surface : rendement 0.50 (moins bon) → palier ≥ immergée', () => {
    const imm = estimateAgricole({ hmtM: 55, debitM3h: 8 });
    const surf = estimateAgricole({ hmtM: 55, debitM3h: 8, pompeType: 'surface' });
    expect(imm.ok && surf.ok).toBe(true);
    if (!imm.ok || !surf.ok) return;
    expect(imm.pompeCv).toBe(3);
    expect(surf.pompeCv).toBe(4);
    expect(surf.hypotheses.pumpEff).toBe(0.5);
  });

  it('au-delà du catalogue 30 CV : arrondi au CV entier supérieur (ordre de grandeur honnête)', () => {
    const r = estimateAgricole({ hmtM: 400, debitM3h: 120 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.pompeCv).toBeGreaterThan(30);
    expect(Number.isInteger(r.pompeCv)).toBe(true);
  });
});

describe('estimateAgricole — économie gasoil (facultative, bande 75–90 %)', () => {
  it('2 000 MAD/mois de gasoil → 18 000–21 600 MAD/an', () => {
    const r = estimateAgricole({ hmtM: 60, debitM3h: 10, fuelSpendMadMonth: 2000 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.fuelSavingMadYearLow).toBe(18_000);
    expect(r.fuelSavingMadYearHigh).toBe(21_600);
  });

  it('sans dépense gasoil déclarée → aucun chiffre inventé (champs absents)', () => {
    const r = estimateAgricole({ hmtM: 60, debitM3h: 10 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.fuelSavingMadYearLow).toBeUndefined();
    expect(r.fuelSavingMadYearHigh).toBeUndefined();
  });
});

describe('estimateAgricole — gardes honnêtes', () => {
  it('hydraulique incomplète → missing_hydraulics (repli honnête, jamais deviné)', () => {
    expect(estimateAgricole({})).toEqual({ ok: false, reason: 'missing_hydraulics' });
    expect(estimateAgricole({ debitM3h: 10 })).toEqual({ ok: false, reason: 'missing_hydraulics' });
    expect(estimateAgricole({ hmtM: 50 })).toEqual({ ok: false, reason: 'missing_hydraulics' });
  });

  it('HMT hors [3, 400] ou débit hors [0.3, 120] → out_of_range', () => {
    expect(estimateAgricole({ hmtM: 500, debitM3h: 10 })).toEqual({ ok: false, reason: 'out_of_range' });
    expect(estimateAgricole({ hmtM: 2, debitM3h: 10 })).toEqual({ ok: false, reason: 'out_of_range' });
    expect(estimateAgricole({ hmtM: 50, debitM3h: 0.1 })).toEqual({ ok: false, reason: 'out_of_range' });
    expect(estimateAgricole({ hmtM: 50, debitM3h: 150 })).toEqual({ ok: false, reason: 'out_of_range' });
    // La HMT ESTIMÉE passe par la même garde (380+2 → 420 > 400).
    expect(estimateAgricole({ profondeurM: 380, debitM3h: 10 })).toEqual({ ok: false, reason: 'out_of_range' });
  });

  it('NaN/négatif/heures impossibles → invalid', () => {
    expect(estimateAgricole({ hmtM: -5, debitM3h: 10 })).toEqual({ ok: false, reason: 'invalid' });
    expect(estimateAgricole({ hmtM: 50, besoinM3j: NaN })).toEqual({ ok: false, reason: 'invalid' });
    expect(estimateAgricole({ hmtM: 50, debitM3h: 10, heuresPompage: 30 })).toEqual({ ok: false, reason: 'invalid' });
  });
});

// ——— lead.ts — règles AGRICOLE : billRange facultatif, lead toujours qualifié ———
const agriBody = {
  fullName: 'Hassan El Fassi',
  phone: '06 12 34 56 78',
  city: 'Marrakech',
  roofType: 'autre',
  consent: true,
  mode: 'agricole',
};
const emptyBand: EstimateBand = { kwcMin: 0, kwcMax: 0, kwcLabel: '', paybackLabel: '', source: 'local' };

describe('lead.ts — mode agricole : billRange FACULTATIF', () => {
  it('une soumission agricole SANS tranche de facture est valide', () => {
    const r = validateLead(agriBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.mode).toBe('agricole');
    expect(r.lead.billRange).toBeUndefined();
    expect(r.lead.city).toBe('Marrakech');
  });

  it('une tranche fournie ET valide est conservée ; malformée, elle est écartée', () => {
    const withRange = validateLead({ ...agriBody, billRange: 'lt800' });
    expect(withRange.ok).toBe(true);
    if (!withRange.ok) return;
    expect(withRange.lead.billRange).toBe('lt800');
    const garbage = validateLead({ ...agriBody, billRange: 'xyz' });
    expect(garbage.ok).toBe(true);
    if (!garbage.ok) return;
    expect(garbage.lead.billRange).toBeUndefined();
  });

  it('régression : sans mode (ou résidentiel), billRange reste REQUIS', () => {
    const { mode: _omit, ...noMode } = agriBody;
    const r = validateLead(noMode);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.errors.billRange).toBeTruthy();
  });
});

describe('lead.ts — un lead agricole est TOUJOURS qualifié (haute valeur, jamais gaté facture)', () => {
  const now = new Date('2026-07-16T10:00:00Z');

  it('sans billRange → qualified true', () => {
    const r = validateLead(agriBody);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(buildLeadRecord(r.lead, emptyBand, now).qualified).toBe(true);
  });

  it('même avec une petite tranche (lt800) → qualified true (le mode prime)', () => {
    const r = validateLead({ ...agriBody, billRange: 'lt800' });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(buildLeadRecord(r.lead, emptyBand, now).qualified).toBe(true);
  });
});

describe('lead.ts — champs AGRICOLES facultatifs (sanitisés, forwardés au webhook)', () => {
  it('champs pompage valides conservés et présents sur le record forwardé', () => {
    const r = validateLead({
      ...agriBody,
      waterSource: 'forage',
      profondeurM: 60,
      hmtM: 70,
      debitM3h: 12,
      besoinM3j: 80,
      heuresPompage: 6,
      irrigation: 'goutte',
      culture: 'Olivier',
      surfaceHa: 12,
      pompeActuelle: 'diesel',
      pompeCvActuelle: 7.5,
      fuelSpendMad: 1500,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.waterSource).toBe('forage');
    expect(r.lead.profondeurM).toBe(60);
    expect(r.lead.hmtM).toBe(70);
    expect(r.lead.debitM3h).toBe(12);
    expect(r.lead.besoinM3j).toBe(80);
    expect(r.lead.heuresPompage).toBe(6);
    expect(r.lead.irrigation).toBe('goutte');
    expect(r.lead.culture).toBe('Olivier');
    expect(r.lead.surfaceHa).toBe(12);
    expect(r.lead.pompeActuelle).toBe('diesel');
    expect(r.lead.pompeCvActuelle).toBe(7.5);
    expect(r.lead.fuelSpendMad).toBe(1500);
    // buildLeadRecord (le payload webhook) porte les mêmes champs, comme
    // ombrage/roofAgeYears (spread de ValidatedLead — aucun champ perdu).
    const record = buildLeadRecord(r.lead, emptyBand, new Date('2026-07-16T10:00:00Z'));
    expect(record.waterSource).toBe('forage');
    expect(record.hmtM).toBe(70);
    expect(record.pompeActuelle).toBe('diesel');
  });

  it('valeurs hors vocabulaire / hors bornes écartées en silence (jamais bloquantes)', () => {
    const r = validateLead({
      ...agriBody,
      waterSource: 'lac',
      profondeurM: -3,
      hmtM: 'profond',
      heuresPompage: 30, // > 24 h/jour
      irrigation: 'pivot',
      culture: 'x'.repeat(200), // borné à 60
      pompeActuelle: 'essence',
      fuelSpendMad: -100,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.waterSource).toBeUndefined();
    expect(r.lead.profondeurM).toBeUndefined();
    expect(r.lead.hmtM).toBeUndefined();
    expect(r.lead.heuresPompage).toBeUndefined();
    expect(r.lead.irrigation).toBeUndefined();
    expect(r.lead.culture).toHaveLength(60);
    expect(r.lead.pompeActuelle).toBeUndefined();
    expect(r.lead.fuelSpendMad).toBeUndefined();
  });

  it('estimateShown agricole : clés pompage whitelistées (pompeCv/champKwc/m3Jour)', () => {
    const r = validateLead({
      ...agriBody,
      estimateShown: { pompeCv: 5.5, champKwc: 5.68, m3Jour: 70, hackerField: 'x' },
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.estimateShown).toEqual({ pompeCv: 5.5, champKwc: 5.68, m3Jour: 70 });
  });
});
