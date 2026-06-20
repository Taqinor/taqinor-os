// Tests PURS de la VARIABILITÉ de consommation (W68, « Affiner ma consommation ») de
// l'estimateur pro-11. Aucun DOM, aucun réseau : on vérifie la physique des appareils
// (clim BTU÷EER, VE kW×h ou km/jour, kWh = W×h÷1000), la répartition sur les créneaux et
// les sommes horaires, la règle « sur ma facture » (monte le total) vs « déjà compris »
// (reshape à total fixe), le recalage sur la facture, l'autoconsommation horaire (surplus
// à zéro) plafonnée par le modèle billMAD existant, et le dimensionnement batterie.
import { describe, expect, it } from 'vitest';
import {
  HOURS_PER_DAY,
  BATTERY_KWH_PER_DAY,
  emptyCurve,
  curveTotal,
  normHour,
  windowHours,
  baselineCurve,
  BASELINE_SHAPE,
  acWattsFromBtu,
  kwhFromWattsHours,
  evKwhFromDistance,
  distributeAppliance,
  applianceCurve,
  composeConsumption,
  rescaleToDaily,
  selfConsumptionDailyKwh,
  surplusDailyKwh,
  selfConsumptionRate,
  savingsFromHourly,
  annualConsumptionFromDaily,
  batterySizing,
  APPLIANCE_TYPICALS,
  applianceFromTypical,
  AC_BTU_PRESETS,
  EV_CHARGER_KW_PRESETS,
  EV_KWH_PER_100KM_DEFAULT,
  type Appliance,
  type HourlyCurve,
} from '../src/lib/applianceConsumption';
import { billToAnnualKwh, billMAD } from '../src/lib/estimatorBrainV2';

const approx = (a: number, b: number, eps = 1e-9) => expect(Math.abs(a - b)).toBeLessThan(eps);

describe('W68 — physique des appareils (chiffres traçables, jamais inventés)', () => {
  it('watts climatisation = BTU/h ÷ EER', () => {
    approx(acWattsFromBtu(9000, 9), 1000);
    approx(acWattsFromBtu(12000, 12), 1000); // inverter
    approx(acWattsFromBtu(18000, 9), 2000);
    approx(acWattsFromBtu(24000, 12), 2000);
  });

  it('clim : entrées invalides → 0 (jamais NaN)', () => {
    expect(acWattsFromBtu(0, 9)).toBe(0);
    expect(acWattsFromBtu(9000, 0)).toBe(0);
    expect(acWattsFromBtu(NaN, 9)).toBe(0);
    expect(acWattsFromBtu(9000, -1)).toBe(0);
  });

  it('kWh = W × h ÷ 1000', () => {
    approx(kwhFromWattsHours(1000, 6), 6); // clim 1 kW pendant 6 h = 6 kWh
    approx(kwhFromWattsHours(2000, 2.5), 5); // cumulus
    approx(kwhFromWattsHours(7400, 3), 22.2); // VE wallbox 7,4 kW × 3 h
    expect(kwhFromWattsHours(-5, 3)).toBe(0);
    expect(kwhFromWattsHours(500, NaN)).toBe(0);
  });

  it('VE par distance : km/jour × conso ÷ 100', () => {
    approx(evKwhFromDistance(50, 17), 8.5); // 50 km à 17 kWh/100 km
    approx(evKwhFromDistance(100, EV_KWH_PER_100KM_DEFAULT), 17);
    expect(evKwhFromDistance(0, 17)).toBe(0);
  });

  it('presets exposés : BTU avec CV, chargeurs kW, conso VE', () => {
    expect(AC_BTU_PRESETS.find((p) => p.btu === 9000)?.cv).toBe(1); // 9 000 BTU ≈ 1 CV
    expect(EV_CHARGER_KW_PRESETS).toContain(7.4); // wallbox monophasé courant
    expect(EV_KWH_PER_100KM_DEFAULT).toBe(17);
  });
});

describe('W68 — créneaux horaires & répartition', () => {
  it('normHour borne dans [0,23] (wrap circulaire)', () => {
    expect(normHour(25)).toBe(1);
    expect(normHour(-1)).toBe(23);
    expect(normHour(12)).toBe(12);
  });

  it('windowHours couvre le bon nombre d’heures, minuit compris', () => {
    expect(windowHours(13, 23)).toEqual([13, 14, 15, 16, 17, 18, 19, 20, 21, 22]);
    expect(windowHours(22, 6)).toEqual([22, 23, 0, 1, 2, 3, 4, 5]); // traverse minuit
    expect(windowHours(0, 24)).toHaveLength(24); // créneau plein
    expect(windowHours(10, 10)).toHaveLength(24); // start==end → 24 h
  });

  it('un appareil distribue son énergie sur son créneau, sommes correctes', () => {
    const a: Appliance = { kind: 'x', label: 'X', dailyKwh: 10, startHour: 13, endHour: 23, billing: 'onTop' };
    const curve = applianceCurve(a);
    expect(curve).toHaveLength(HOURS_PER_DAY);
    approx(curveTotal(curve), 10); // somme = dailyKwh
    // uniforme sur 10 heures → 1 kWh chacune ; zéro hors créneau
    for (let h = 13; h < 23; h++) approx(curve[h], 1);
    expect(curve[0]).toBe(0);
    expect(curve[23]).toBe(0);
  });

  it('appareil traversant minuit : les bonnes heures portent l’énergie', () => {
    const a: Appliance = { kind: 'ev', label: 'VE', dailyKwh: 8, startHour: 22, endHour: 6, billing: 'onTop' };
    const curve = applianceCurve(a);
    approx(curveTotal(curve), 8);
    approx(curve[22], 1); // 8 kWh / 8 h
    approx(curve[2], 1);
    expect(curve[12]).toBe(0);
  });

  it('baselineCurve somme exactement au total journalier visé', () => {
    approx(curveTotal(baselineCurve(30)), 30);
    expect(baselineCurve(0)).toEqual(emptyCurve());
    expect(BASELINE_SHAPE).toHaveLength(24);
  });
});

describe('W68 — « Sur ma facture » monte le total · « Déjà compris » reshape à total fixe', () => {
  const base = baselineCurve(20); // 20 kWh/jour issus de la facture

  it('« Déjà compris » (inBill) GARDE le total du socle (reshape seulement)', () => {
    const fridge: Appliance = { kind: 'frigo', label: 'Frigo', dailyKwh: 1.5, startHour: 0, endHour: 24, billing: 'inBill' };
    const out = composeConsumption(base, [fridge]);
    approx(curveTotal(out), 20); // total INCHANGÉ
    // la forme a changé (la nuit remonte un peu) mais le total reste 20
    expect(out).toHaveLength(24);
  });

  it('« Sur ma facture » (onTop) AUGMENTE le total de l’énergie de l’appareil', () => {
    const ac: Appliance = { kind: 'clim', label: 'Clim', dailyKwh: 6, startHour: 13, endHour: 23, billing: 'onTop' };
    const out = composeConsumption(base, [ac]);
    approx(curveTotal(out), 26); // 20 + 6
  });

  it('mélange : un inBill + un onTop → total = socle + onTop uniquement', () => {
    const fridge: Appliance = { kind: 'frigo', label: 'Frigo', dailyKwh: 1.5, startHour: 0, endHour: 24, billing: 'inBill' };
    const ev: Appliance = { kind: 'ev', label: 'VE', dailyKwh: 10, startHour: 11, endHour: 15, billing: 'onTop' };
    const out = composeConsumption(base, [fridge, ev]);
    approx(curveTotal(out), 30); // 20 (socle, frigo compris) + 10 (VE on top)
  });

  it('socle nul : un inBill ne fabrique pas d’énergie (reste à 0)', () => {
    const fridge: Appliance = { kind: 'frigo', label: 'Frigo', dailyKwh: 1.5, startHour: 0, endHour: 24, billing: 'inBill' };
    const out = composeConsumption(emptyCurve(), [fridge]);
    approx(curveTotal(out), 0);
  });
});

describe('W68 — « Recaler sur ma facture » rescale la courbe éditée au total facture', () => {
  it('une courbe éditée est remise au total journalier de la facture', () => {
    const edited: HourlyCurve = emptyCurve();
    edited[12] = 5;
    edited[19] = 15; // total 20, mais la facture dit 30
    const recaled = rescaleToDaily(edited, 30);
    approx(curveTotal(recaled), 30);
    // proportions préservées : 19h reste 3× l’heure 12h
    approx(recaled[19] / recaled[12], 3);
  });

  it('cible ≤ 0 ou courbe nulle → renvoyée telle quelle', () => {
    const edited = baselineCurve(10);
    expect(curveTotal(rescaleToDaily(edited, 0))).toBeCloseTo(10);
    expect(curveTotal(rescaleToDaily(emptyCurve(), 30))).toBe(0);
  });
});

describe('W68 — autoconsommation (surplus à zéro) + économies plafonnées billMAD', () => {
  // Production : 12 kWh étalés en cloche 8h–16h ; conso : pic du soir.
  const prod: HourlyCurve = emptyCurve();
  for (let h = 8; h < 16; h++) prod[h] = 1.5; // 12 kWh/jour de production

  it('autoconsommation = Σ min(conso, prod) heure par heure ; surplus valorisé à zéro', () => {
    const cons: HourlyCurve = emptyCurve();
    cons[20] = 10; // tout consommé le soir, hors soleil
    expect(selfConsumptionDailyKwh(cons, prod)).toBe(0); // rien aligné → autoconso 0
    expect(surplusDailyKwh(cons, prod)).toBe(12); // toute la prod est surplus

    const consDay: HourlyCurve = emptyCurve();
    for (let h = 8; h < 16; h++) consDay[h] = 1; // 8 kWh en journée
    expect(selfConsumptionDailyKwh(consDay, prod)).toBe(8); // min(1,1.5)=1 ×8h
    expect(surplusDailyKwh(consDay, prod)).toBe(4); // 12 produit − 8 autoconsommé
  });

  it('taux d’autoconsommation ∈ [0,1]', () => {
    const cons = baselineCurve(20);
    const r = selfConsumptionRate(cons, prod);
    expect(r).toBeGreaterThanOrEqual(0);
    expect(r).toBeLessThanOrEqual(1);
  });

  it('économies ≤ plafond billMAD (jamais production × tarif non plafonné)', () => {
    const annualCons = billToAnnualKwh(1500); // facture 1 500 MAD/mois
    const cons = baselineCurve(annualCons / 365);
    const s = savingsFromHourly(cons, prod, annualCons);
    expect(s.high).toBeGreaterThanOrEqual(s.low);
    // plafond : l’économie annuelle ne dépasse jamais le coût énergie évitable (12×billMAD)
    const cap = billMAD(annualCons / 12) * 12;
    expect(s.high).toBeLessThanOrEqual(cap + 1e-6);
    // l’autoconsommation alignée est cohérente (≥ 0, ≤ production annuelle)
    expect(s.selfAnnualKwh).toBeGreaterThanOrEqual(0);
  });

  it('plus d’alignement solaire → plus d’économies (monotone vers le haut)', () => {
    const annualCons = billToAnnualKwh(1500);
    // conso concentrée la nuit vs concentrée en journée : la journée économise plus
    const night: HourlyCurve = emptyCurve();
    night[21] = annualCons / 365;
    const day: HourlyCurve = emptyCurve();
    for (let h = 8; h < 16; h++) day[h] = annualCons / 365 / 8;
    const sNight = savingsFromHourly(night, prod, annualCons);
    const sDay = savingsFromHourly(day, prod, annualCons);
    expect(sDay.high).toBeGreaterThan(sNight.high);
  });
});

describe('W68 — dimensionnement : besoin annuel + batterie (6 kWh/jour, taille-au-besoin)', () => {
  it('un appareil « sur ma facture » monte le besoin annuel', () => {
    const base = baselineCurve(20);
    const ac: Appliance = { kind: 'clim', label: 'Clim', dailyKwh: 6, startHour: 13, endHour: 23, billing: 'onTop' };
    const before = annualConsumptionFromDaily(curveTotal(base));
    const after = annualConsumptionFromDaily(curveTotal(composeConsumption(base, [ac])));
    expect(after).toBeGreaterThan(before);
    approx(after - before, 6 * 365); // exactement l’énergie ajoutée, annualisée
  });

  it('batterie = plafond(énergie soir/nuit décalable ÷ 6), bornée par le surplus', () => {
    // grosse production le jour, grosse conso le soir → stockable borné par le surplus
    const prod: HourlyCurve = emptyCurve();
    for (let h = 9; h < 16; h++) prod[h] = 3; // 21 kWh/jour produits
    const cons: HourlyCurve = emptyCurve();
    cons[20] = 6;
    cons[21] = 6; // 12 kWh le soir, hors soleil
    const { storableDailyKwh, batteries } = batterySizing(cons, prod);
    expect(storableDailyKwh).toBeLessThanOrEqual(surplusDailyKwh(cons, prod) + 1e-9);
    expect(storableDailyKwh).toBeGreaterThan(0);
    expect(batteries).toBe(Math.ceil(storableDailyKwh / BATTERY_KWH_PER_DAY));
  });

  it('pas de surplus → 0 batterie (on ne stocke pas ce qu’on n’a pas produit)', () => {
    const prod: HourlyCurve = emptyCurve(); // aucune production
    const cons = baselineCurve(20);
    expect(batterySizing(cons, prod)).toEqual({ storableDailyKwh: 0, batteries: 0 });
  });
});

describe('W68 — catalogue d’appareils (défauts éditables, sourcés)', () => {
  it('expose les appareils demandés', () => {
    const kinds = APPLIANCE_TYPICALS.map((t) => t.kind);
    for (const k of ['clim', 'ev', 'cumulus', 'piscine', 'four', 'plaque', 'lave-linge', 'lave-vaisselle', 'seche-linge', 'frigo', 'chauffage', 'pompe-eau', 'fer', 'micro-ondes', 'pac', 'tv', 'led']) {
      expect(kinds, `manque ${k}`).toContain(k);
    }
  });

  it('chaque typique se convertit en Appliance avec un dailyKwh = W×h÷1000', () => {
    for (const t of APPLIANCE_TYPICALS) {
      const a = applianceFromTypical(t);
      approx(a.dailyKwh, kwhFromWattsHours(t.watts, t.hoursPerDay));
      expect(a.billing === 'onTop' || a.billing === 'inBill').toBe(true);
    }
  });
});
