// WJ124 — Moteur agricole web : culture → eau → pompe.
// Port VERBATIM du moteur FAO-56 QX48 (agronomy.py) : parité numérique
// (Math.round = référence), série mensuelle, evergreen vs staged. Le chemin
// culture+région+surface → besoin m³/j → pompe/champ via estimateAgricole.
// regionAgricole traverse validateLead.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
  monthlyWaterDemand,
  cropKcMonthly,
  annualWaterFromMonthly,
  CROP_STAGES,
  ET0_MONTHLY,
  RAIN_EFF_MONTHLY,
  IRRIGATION_EFFICIENCY,
  KC_MID_DEFAUT,
  CROP_KEYS,
  REGION_KEYS,
  DAYS_IN_MONTH,
} from '../src/lib/agronomy';
import { estimateAgricole } from '../src/lib/estimatorAgricole';
import { validateLead, REGIONS_AGRICOLES } from '../src/lib/lead';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

describe('WJ124 — constantes MIROIR de QX48 (agronomy.py)', () => {
  it('20 cultures FAO-56 + 8 régions', () => {
    expect(CROP_KEYS.length).toBe(20);
    expect(REGION_KEYS.length).toBe(8);
    expect(Object.keys(ET0_MONTHLY).length).toBe(8);
    expect(Object.keys(RAIN_EFF_MONTHLY).length).toBe(8);
  });
  it('valeurs de calage sourcées (avocatier 0.85, dattier 0.95, goutte 0.90)', () => {
    expect(CROP_STAGES.avocatier.kc_mid).toBe(0.85);
    expect(CROP_STAGES.avocatier.evergreen).toBe(true);
    expect(CROP_STAGES.dattier.kc_mid).toBe(0.95);
    expect(IRRIGATION_EFFICIENCY.goutte).toBe(0.9);
    expect(ET0_MONTHLY['gharb-loukkos'][6]).toBe(6.5); // juillet Kénitra/Larache
  });
});

describe('WJ124 — cropKcMonthly : evergreen constant vs staged', () => {
  it('une culture pérenne (avocatier) a un Kc CONSTANT sur 12 mois', () => {
    expect(cropKcMonthly('avocatier')).toEqual(new Array(12).fill(0.85));
  });
  it('une culture inconnue retombe sur le Kc défaut plat', () => {
    expect(cropKcMonthly('inconnu')).toEqual(new Array(12).fill(KC_MID_DEFAUT));
  });
  it('une culture à stades (céréales, semis novembre) a un Kc SAISONNIER (nul en été)', () => {
    const kc = cropKcMonthly('cereales');
    expect(kc[10]).toBe(0.4); // novembre = initiation (kc_ini)
    expect(kc[6]).toBe(0); // juillet : hors saison → 0 (pas d'eau)
    // le pic (kc_mid 1.15) tombe en hiver, jamais en été.
    expect(Math.max(...kc)).toBe(1.15);
  });
});

describe('WJ124 — monthlyWaterDemand : parité numérique (avocat Gharb 5 ha goutte)', () => {
  const md = monthlyWaterDemand('avocatier', 'gharb-loukkos', 5, 'goutte');

  it('le besoin de pointe (mois le plus chaud) est crédible et EXACT (306,9 m³/j)', () => {
    expect(md.peak_m3_farm_day).toBe(306.9);
  });
  it('la série mensuelle a 12 valeurs cohérentes (été > hiver pour un evergreen)', () => {
    expect(md.gross_m3_farm_day).toHaveLength(12);
    // juillet (index 6) > janvier (index 0) — la demande suit l'ET0.
    expect(md.gross_m3_farm_day[6]).toBeGreaterThan(md.gross_m3_farm_day[0]);
  });
  it('l’annualisation par intégrale = somme(série × jours du mois)', () => {
    const expected = md.gross_m3_farm_day.reduce((s, v, m) => s + v * DAYS_IN_MONTH[m], 0);
    expect(annualWaterFromMonthly(md)).toBe(Math.floor(expected + 0.5));
  });
  it('kc_estimated=false pour l’avocatier (FAO-matched)', () => {
    expect(md.kc_estimated).toBe(false);
  });
});

describe('WJ124 — chaîne culture → eau → pompe (avocat Gharb 5 ha)', () => {
  it('le besoin de pointe dimensionne une pompe/champ crédibles', () => {
    const md = monthlyWaterDemand('avocatier', 'gharb-loukkos', 5, 'goutte');
    const est = estimateAgricole({ besoinM3j: md.peak_m3_farm_day, hmtM: 55, heuresPompage: 7, pompeType: 'immergee' });
    expect(est.ok).toBe(true);
    if (est.ok) {
      expect(est.pompeCv).toBe(20);
      expect(est.champKwc).toBeCloseTo(20.59, 2);
      expect(est.m3Jour).toBe(307); // ≈ besoin de pointe arrondi
      expect(est.nbPanneaux).toBeGreaterThan(0);
    }
  });
});

describe('WJ124 — validateLead : regionAgricole + culture traversent la liste blanche', () => {
  const base = {
    fullName: 'Reda K.', phone: '0612345678', city: 'Kénitra',
    roofType: 'autre', consent: true, mode: 'agricole',
  };

  it('une région valide + une culture (clé CROP_STAGES) survivent', () => {
    const r = validateLead({ ...base, regionAgricole: 'gharb-loukkos', culture: 'avocatier' });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.lead.regionAgricole).toBe('gharb-loukkos');
      expect(r.lead.culture).toBe('avocatier');
    }
  });

  it('les 8 zones sont acceptées ; une zone inconnue est écartée', () => {
    for (const z of REGIONS_AGRICOLES) {
      const r = validateLead({ ...base, regionAgricole: z });
      expect(r.ok && r.lead.regionAgricole).toBe(z);
    }
    const bad = validateLead({ ...base, regionAgricole: 'mars' });
    expect(bad.ok).toBe(true);
    if (bad.ok) expect(bad.lead.regionAgricole).toBeUndefined();
  });
});

describe.each(LOCALES)('WJ124 — panneau agricole enrichi dans mon-toit.astro (%s)', (_locale, rel) => {
  const src = read(rel);

  it('a des cartes culture + région pilotées par le moteur agronomique', () => {
    expect(src).toContain('mt-culture-card');
    expect(src).toContain('mt-region-card');
    expect(src).toContain("import { monthlyWaterDemand } from");
  });

  it('déduit le besoin sans débit connu, en gardant le chemin hydraulique', () => {
    expect(src).toContain('monthlyWaterDemand(crop, regionAgricole, surfaceHa, irrigation');
    expect(src).toContain('md.peak_m3_farm_day');
  });

  it('n’expose PAS le besoin dimensionnant avant l’envoi (garde WJ125)', () => {
    expect(src).toContain('agroPeak == null || PUBLIC_ESTIMATE_GATED');
  });

  it('envoie regionAgricole au payload + suggère un bassin', () => {
    expect(src).toContain('regionAgricole: regionAgricole || undefined');
    expect(src).toContain('s.bassinM3 = ag.m3Jour');
  });

  it('un SEUL mt-culture (pas de doublon d’id après remontée)', () => {
    const ids = src.match(/id="mt-culture"/g) ?? [];
    expect(ids).toHaveLength(1);
    const surf = src.match(/id="mt-surface-ha"/g) ?? [];
    expect(surf).toHaveLength(1);
  });
});
