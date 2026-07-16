// Parcours 3 profils — estimateur PROFESSIONNEL (lib/estimatorPro.ts, miroir
// solar.js computeEtudeIndustrielle) + billRangeFromExact + champs lead pro.
// Honnêteté : entrées manquantes ⇒ ok:false (jamais un chiffre fabriqué),
// hypothèses (tarif, prix kWc) exposées dans le résultat.
import { describe, expect, it } from 'vitest';
import {
  DAY_SHARE_BY_PROFILE,
  DEFAULT_DAY_SHARE,
  EFFICIENCY,
  GHI,
  PANEL_W,
  PRIX_KWC_HIGH,
  PRIX_KWC_LOW,
  TARIF_BT_PRO_MAD_KWH,
  TARIF_MT_MAD_KWH,
  estimatePro,
} from '../src/lib/estimatorPro';
import { billRangeFromExact, localEstimateBand } from '../src/lib/billRange';
import { MAX_BILL_BY_MODE, buildLeadRecord, validateLead } from '../src/lib/lead';

const GHI_SUM = GHI.reduce((s, v) => s + v, 0);

describe('estimatePro — constantes MIROIR de solar.js (jamais dérivées)', () => {
  it('GHI, EFFICIENCY et panneau 710 W identiques à frontend solar.js', () => {
    // Valeurs EXACTES de frontend/src/features/ventes/solar.js (GHI l.14-17).
    expect([...GHI]).toEqual([
      83.99, 96.79, 133.43, 155.3, 175.28, 179.62,
      179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
    ]);
    expect(EFFICIENCY).toBe(0.8);
    expect(PANEL_W).toBe(710);
  });

  it('part diurne « day » alignée sur l\'ERP (DAY_USAGE_DEFAULTS C&I = 80 %)', () => {
    expect(DAY_SHARE_BY_PROFILE.day).toBe(0.8);
    expect(DEFAULT_DAY_SHARE).toBe(0.8);
    expect(DAY_SHARE_BY_PROFILE.day_evening).toBe(0.65);
    expect(DAY_SHARE_BY_PROFILE.continuous).toBe(0.45);
  });
});

describe('estimatePro — chemin kWh déclarés', () => {
  it('10 000 kWh/mois profil jour : dimensionné à la part diurne, prod = GHI × kwc × 0.8', () => {
    const r = estimatePro({ monthlyKwh: 10_000, activityProfile: 'day' });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    // kWc ≈ (120 000 × 0.80) / (ΣGHI × 0.8), arrondi au demi-kWc.
    expect(r.kwc).toBe(76.5);
    expect(r.nbPanneaux).toBe(Math.ceil((76.5 * 1000) / PANEL_W)); // 108
    // Production annuelle = même formule que computeEtudeIndustrielle.
    expect(r.prodAnnuelleKwh).toBe(Math.round(76.5 * GHI_SUM * EFFICIENCY));
    expect(r.consoAnnuelleKwh).toBe(120_000);
    // Autoconsommation d'abord : couverture = part diurne (80 %), autoconso ≈ 100 %.
    expect(r.tauxCouverture).toBe(80);
    expect(r.tauxAutoconso).toBeGreaterThan(99);
    expect(r.tauxAutoconso).toBeLessThanOrEqual(100);
    // Économies = autoconsommé × tarif BT (défaut sans raccordement), bande ±10 %.
    expect(r.hypotheses.tarifMadKwh).toBe(TARIF_BT_PRO_MAD_KWH);
    expect(r.ecoAnnuelleMadLow).toBeLessThan(r.ecoAnnuelleMadHigh);
    // Payback borné et ordonné (jamais une promesse inversée).
    expect(r.paybackYearsLow).toBeGreaterThan(0);
    expect(r.paybackYearsLow).toBeLessThanOrEqual(r.paybackYearsHigh);
    expect(r.surfaceCapped).toBe(false);
    expect(r.hypotheses.prixKwcLow).toBe(PRIX_KWC_LOW);
    expect(r.hypotheses.prixKwcHigh).toBe(PRIX_KWC_HIGH);
  });

  it('plancher 2 kWc pour une toute petite conso', () => {
    const r = estimatePro({ monthlyKwh: 100 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.kwc).toBe(2);
  });
});

describe('estimatePro — chemin facture MAD (tarif d\'hypothèse par raccordement)', () => {
  it('MT : conso déduite au blend ≈ 1,15 MAD/kWh (hypothèse exposée)', () => {
    const r = estimatePro({ monthlyMad: 20_000, raccordement: 'mt' });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.hypotheses.tarifMadKwh).toBe(TARIF_MT_MAD_KWH);
    expect(r.consoAnnuelleKwh).toBe(Math.round((20_000 / TARIF_MT_MAD_KWH) * 12));
  });

  it('BT (et défaut sans raccordement) : ≈ 1,40 MAD/kWh', () => {
    const bt = estimatePro({ monthlyMad: 5_000, raccordement: 'bt' });
    const def = estimatePro({ monthlyMad: 5_000 });
    expect(bt.ok && def.ok).toBe(true);
    if (!bt.ok || !def.ok) return;
    expect(bt.hypotheses.tarifMadKwh).toBe(TARIF_BT_PRO_MAD_KWH);
    expect(def.hypotheses.tarifMadKwh).toBe(TARIF_BT_PRO_MAD_KWH);
    expect(def.kwc).toBe(bt.kwc);
  });

  it('les kWh déclarés PRIMENT sur la facture (pas de double déduction)', () => {
    const r = estimatePro({ monthlyKwh: 3_000, monthlyMad: 999_999 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.consoAnnuelleKwh).toBe(36_000);
  });
});

describe('estimatePro — effet du profil d\'activité (part diurne)', () => {
  it('un site 24/7 (continuous 0.45) est dimensionné plus petit qu\'un site diurne (0.80)', () => {
    const day = estimatePro({ monthlyKwh: 10_000, activityProfile: 'day' });
    const cont = estimatePro({ monthlyKwh: 10_000, activityProfile: 'continuous' });
    expect(day.ok && cont.ok).toBe(true);
    if (!day.ok || !cont.ok) return;
    expect(cont.kwc).toBeLessThan(day.kwc);
    expect(cont.hypotheses.dayShare).toBe(0.45);
    expect(day.hypotheses.dayShare).toBe(0.8);
  });
});

describe('estimatePro — plafond surface (≈ 6 m²/kWc)', () => {
  it('60 m² plafonnent à 10 kWc et le signalent (surfaceCapped)', () => {
    const r = estimatePro({ monthlyKwh: 10_000, activityProfile: 'day', surfaceM2: 60 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.kwc).toBe(10);
    expect(r.surfaceCapped).toBe(true);
    expect(r.nbPanneaux).toBe(Math.ceil((10 * 1000) / PANEL_W)); // 15
    // Production/taux recalculés avec le kWc PLAFONNÉ (jamais le théorique).
    expect(r.prodAnnuelleKwh).toBe(Math.round(10 * GHI_SUM * EFFICIENCY));
    expect(r.tauxAutoconso).toBe(100); // tout est autoconsommé sur un site sous-couvert
    expect(r.tauxCouverture).toBeLessThan(80);
  });

  it('une surface généreuse ne plafonne pas', () => {
    const r = estimatePro({ monthlyKwh: 1_000, surfaceM2: 500 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.surfaceCapped).toBe(false);
  });
});

describe('estimatePro — gardes honnêtes (jamais un chiffre fabriqué)', () => {
  it('trop grand : > 200 000 kWh/mois ou facture > 1 M MAD → too_large (étude dédiée)', () => {
    expect(estimatePro({ monthlyKwh: 250_000 })).toEqual({ ok: false, reason: 'too_large' });
    expect(estimatePro({ monthlyMad: 1_200_000 })).toEqual({ ok: false, reason: 'too_large' });
  });

  it('aucune info de conso → missing_conso (0 n\'est pas une conso)', () => {
    expect(estimatePro({})).toEqual({ ok: false, reason: 'missing_conso' });
    expect(estimatePro({ monthlyKwh: 0, monthlyMad: null })).toEqual({ ok: false, reason: 'missing_conso' });
  });

  it('NaN/négatif → invalid (jamais deviné)', () => {
    expect(estimatePro({ monthlyKwh: -5 })).toEqual({ ok: false, reason: 'invalid' });
    expect(estimatePro({ monthlyMad: NaN })).toEqual({ ok: false, reason: 'invalid' });
    expect(estimatePro({ monthlyKwh: 1_000, surfaceM2: -2 })).toEqual({ ok: false, reason: 'invalid' });
  });
});

// ——— billRangeFromExact — montant exact → tranche du select (bords inclus/exclus) ———
describe('billRangeFromExact — bords de tranches', () => {
  it('mappe chaque bord sur la bonne tranche (semi-ouvert [min, max))', () => {
    expect(billRangeFromExact(500)).toBe('lt800');
    expect(billRangeFromExact(799.99)).toBe('lt800');
    expect(billRangeFromExact(800)).toBe('800-1000');
    expect(billRangeFromExact(999.99)).toBe('800-1000');
    expect(billRangeFromExact(1000)).toBe('1000-1500');
    expect(billRangeFromExact(1500)).toBe('1500-3000');
    expect(billRangeFromExact(3000)).toBe('3000-5000');
    expect(billRangeFromExact(5000)).toBe('5000-10000');
    expect(billRangeFromExact(9999)).toBe('5000-10000');
    expect(billRangeFromExact(10_000)).toBe('gt10000');
  });

  it('la tranche haute ouverte attrape les grands montants', () => {
    expect(billRangeFromExact(5_000_000)).toBe('gt10000');
  });

  it('entrée non chiffrable → null (jamais deviné)', () => {
    expect(billRangeFromExact(0)).toBeNull();
    expect(billRangeFromExact(-10)).toBeNull();
    expect(billRangeFromExact(NaN)).toBeNull();
    expect(billRangeFromExact(Infinity)).toBeNull();
  });
});

// ——— lead.ts — champs pro facultatifs + plafond par mode + estimateShown ———
const validBody = {
  fullName: 'Karim Benali',
  phone: '06 12 34 56 78',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
};

describe('lead.ts — champs PRO facultatifs (sanitisés, jamais bloquants)', () => {
  it('tensionRaccordement/activityProfile/surfaceType valides sont conservés', () => {
    const r = validateLead({
      ...validBody,
      mode: 'professionnel',
      tensionRaccordement: 'mt',
      activityProfile: 'continuous',
      surfaceType: 'ombriere',
      puissanceKva: 400,
      surfaceM2: 1200,
      hasGenerator: true,
      proMonthlyKwh: 12_000,
      proMonthlyMad: 18_000,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.tensionRaccordement).toBe('mt');
    expect(r.lead.activityProfile).toBe('continuous');
    expect(r.lead.surfaceType).toBe('ombriere');
    expect(r.lead.puissanceKva).toBe(400);
    expect(r.lead.surfaceM2).toBe(1200);
    expect(r.lead.hasGenerator).toBe(true);
    expect(r.lead.proMonthlyKwh).toBe(12_000);
    expect(r.lead.proMonthlyMad).toBe(18_000);
  });

  it('valeurs hors vocabulaire / hors bornes sont ÉCARTÉES en silence', () => {
    const r = validateLead({
      ...validBody,
      tensionRaccordement: 'ht',
      activityProfile: 'night',
      surfaceType: 'jardin',
      puissanceKva: -3,
      surfaceM2: 'beaucoup',
      hasGenerator: 'oui',
      proMonthlyKwh: -1,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.tensionRaccordement).toBeUndefined();
    expect(r.lead.activityProfile).toBeUndefined();
    expect(r.lead.surfaceType).toBeUndefined();
    expect(r.lead.puissanceKva).toBeUndefined();
    expect(r.lead.surfaceM2).toBeUndefined();
    expect(r.lead.hasGenerator).toBeUndefined();
    expect(r.lead.proMonthlyKwh).toBeUndefined();
  });

  it('`tensionRaccordement` (bt/mt) coexiste avec le `raccordement` historique (mono/tri)', () => {
    const r = validateLead({ ...validBody, raccordement: 'triphase', tensionRaccordement: 'bt' });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.raccordement).toBe('triphase');
    expect(r.lead.tensionRaccordement).toBe('bt');
  });

  it('billRange reste REQUIS en mode professionnel (et résidentiel)', () => {
    const { billRange: _omit, ...noBill } = validBody;
    const pro = validateLead({ ...noBill, mode: 'professionnel' });
    expect(pro.ok).toBe(false);
    if (pro.ok) return;
    expect(pro.errors.billRange).toBeTruthy();
    const res = validateLead({ ...noBill, mode: 'residentiel' });
    expect(res.ok).toBe(false);
  });
});

describe('lead.ts — MAX_BILL_BY_MODE (plafond de saisie par mode)', () => {
  it('professionnel monte à 1 M MAD, résidentiel/agricole gardent 200 000', () => {
    expect(MAX_BILL_BY_MODE.residentiel).toBe(200_000);
    expect(MAX_BILL_BY_MODE.professionnel).toBe(1_000_000);
    expect(MAX_BILL_BY_MODE.agricole).toBe(200_000);
  });
});

describe('lead.ts — estimateShown : liste blanche stricte', () => {
  it('ne garde QUE les clés whitelistées, numériques finies + paybackLabel', () => {
    const r = validateLead({
      ...validBody,
      estimateShown: {
        kwc: 12.5,
        prodKwh: 15_700,
        ecoMadYearLow: 9_000,
        ecoMadYearHigh: 11_000,
        tauxAutoconso: 95.5,
        paybackLabel: '4 à 6 ans',
        evil: 'dropme',
        nested: { a: 1 },
        prodGarbage: 'NaN',
        m3Jour: 40,
      },
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.estimateShown).toEqual({
      kwc: 12.5,
      prodKwh: 15_700,
      ecoMadYearLow: 9_000,
      ecoMadYearHigh: 11_000,
      tauxAutoconso: 95.5,
      paybackLabel: '4 à 6 ans',
      m3Jour: 40,
    });
  });

  it('valeurs non finies / négatives / objet vide → écartées (champ absent)', () => {
    const r = validateLead({
      ...validBody,
      estimateShown: { kwc: NaN, prodKwh: -5, paybackLabel: '' },
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.lead.estimateShown).toBeUndefined();
    const r2 = validateLead({ ...validBody, estimateShown: 'texte' });
    expect(r2.ok).toBe(true);
    if (!r2.ok) return;
    expect(r2.lead.estimateShown).toBeUndefined();
  });
});

describe('lead.ts — qualification résidentiel/professionnel INCHANGÉE (seuil 1 000 MAD)', () => {
  it('lt800 reste non qualifié, 1500-3000 reste qualifié', () => {
    const now = new Date('2026-07-16T10:00:00Z');
    const low = validateLead({ ...validBody, billRange: 'lt800' });
    const mid = validateLead(validBody);
    expect(low.ok && mid.ok).toBe(true);
    if (!low.ok || !mid.ok) return;
    expect(buildLeadRecord(low.lead, localEstimateBand('lt800'), now).qualified).toBe(false);
    expect(buildLeadRecord(mid.lead, localEstimateBand('1500-3000'), now).qualified).toBe(true);
  });
});
