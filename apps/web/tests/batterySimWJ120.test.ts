// WJ120 — Moteur horaire glouton du simulateur « et avec N batteries ? ». Preuve
// que le moteur respecte la physique (conservation de l'énergie), qu'ajouter des
// batteries améliore MONOTONIQUEMENT l'autosuffisance et réduit l'import réseau, que
// les heures de secours sont linéaires en N, et que le JOUR 2 (régime permanent,
// SoC reporté) diffère bien d'un jour 1 démarré batterie vide. Aucun chiffre
// inventé : la capacité vient des réfs catalogue Deyness (5/10), jamais du 6.
import { describe, expect, it } from 'vitest';
import {
  simulateBattery,
  scaleShapeToDaily,
  resolveOfferBattery,
  renderBatterySplitSvg,
  DEYNESS_CAPACITY_KWH,
  ESSENTIAL_LOAD_W,
  BATTERY_ONE_WAY_EFFICIENCY,
  BATTERY_DEPTH_OF_DISCHARGE,
  HOURS_PER_DAY,
  type BatterySimInput,
} from '../src/lib/batterySim';
import { consumptionProfile, solarProfile } from '../src/lib/proposalCurve';
import type { ProposalItem } from '../src/lib/proposition';

// Silhouettes RÉELLES du parcours : conso résidentielle marocaine (soirée-dominante)
// vs cloche solaire — exactement celles pré-rendues par la page proposition.
const consShape = Array.from({ length: HOURS_PER_DAY }, (_, h) =>
  consumptionProfile(h, { mode: 'residentiel', variant: 'normal' }),
);
const solarShape = Array.from({ length: HOURS_PER_DAY }, (_, h) => solarProfile(h));

function baseInput(units: number, overrides: Partial<BatterySimInput> = {}): BatterySimInput {
  return {
    consumptionShape: consShape,
    productionShape: solarShape,
    dailyConsumptionKwh: 15,
    dailyProductionKwh: 20, // surplus disponible à stocker
    capacityKwhPerUnit: DEYNESS_CAPACITY_KWH['BAT-DEY-5'], // 5 kWh
    units,
    ...overrides,
  };
}

describe('WJ120 — scaleShapeToDaily : la silhouette somme EXACTEMENT au total journalier', () => {
  it('somme = dailyKwh, jamais d’énergie fabriquée', () => {
    const arr = scaleShapeToDaily(consShape, 15);
    const sum = arr.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(15, 6);
    expect(arr).toHaveLength(24);
  });
  it('total ≤ 0 / silhouette nulle / taille ≠ 24 → 24 zéros (jamais NaN)', () => {
    expect(scaleShapeToDaily(consShape, 0).every((v) => v === 0)).toBe(true);
    expect(scaleShapeToDaily(new Array(24).fill(0), 15).every((v) => v === 0)).toBe(true);
    expect(scaleShapeToDaily([1, 2, 3], 15).every((v) => v === 0)).toBe(true);
  });
});

describe('WJ120 — N=0 : aucune batterie', () => {
  const res = simulateBattery(baseInput(0));
  it('from-battery = 0 (rien à décharger)', () => {
    expect(res.fromBatteryKwh).toBe(0);
    expect(res.usableCapacityKwh).toBe(0);
  });
  it('autoconsommation = solaire directement consommé (pas de stockage)', () => {
    // Sans batterie, solaire→batterie = 0 → autoconso = direct/production.
    expect(res.solarToBatteryKwh).toBe(0);
    const expected = (res.directKwh / res.productionKwh) * 100;
    expect(res.selfConsumptionPct).toBeCloseTo(expected, 6);
  });
  it('autosuffisance = direct/consommation (aucun apport batterie)', () => {
    const expected = (res.directKwh / res.consumptionKwh) * 100;
    expect(res.selfSufficiencyPct).toBeCloseTo(expected, 6);
  });
  it('heures de secours = 0', () => {
    expect(res.backupHours).toBe(0);
  });
});

describe('WJ120 — conservation de l’énergie (moteur exact)', () => {
  for (const n of [0, 1, 2, 3]) {
    it(`N=${n} : direct + batterie + réseau == consommation`, () => {
      const r = simulateBattery(baseInput(n));
      expect(r.directKwh + r.fromBatteryKwh + r.fromGridKwh).toBeCloseTo(r.consumptionKwh, 6);
    });
    it(`N=${n} : direct + solaire→batterie + exporté == production`, () => {
      const r = simulateBattery(baseInput(n));
      expect(r.directKwh + r.solarToBatteryKwh + r.exportedKwh).toBeCloseTo(r.productionKwh, 6);
    });
  }
});

describe('WJ120 — ajouter une batterie ↑ autosuffisance & ↑ autoconsommation, ↓ import réseau (MONOTONE)', () => {
  const results = [0, 1, 2, 3].map((n) => simulateBattery(baseInput(n)));
  it('autosuffisance non décroissante, strictement ↑ de 0 à 1', () => {
    for (let i = 1; i < results.length; i++) {
      expect(results[i].selfSufficiencyPct).toBeGreaterThanOrEqual(results[i - 1].selfSufficiencyPct - 1e-9);
    }
    expect(results[1].selfSufficiencyPct).toBeGreaterThan(results[0].selfSufficiencyPct);
  });
  it('import réseau non croissant, strictement ↓ de 0 à 1', () => {
    for (let i = 1; i < results.length; i++) {
      expect(results[i].fromGridKwh).toBeLessThanOrEqual(results[i - 1].fromGridKwh + 1e-9);
    }
    expect(results[1].fromGridKwh).toBeLessThan(results[0].fromGridKwh);
  });
  it('autoconsommation non décroissante (moins d’export à mesure qu’on stocke)', () => {
    for (let i = 1; i < results.length; i++) {
      expect(results[i].selfConsumptionPct).toBeGreaterThanOrEqual(results[i - 1].selfConsumptionPct - 1e-9);
    }
  });
  it('les deux taux restent bornés ∈ [0,100]', () => {
    for (const r of results) {
      expect(r.selfConsumptionPct).toBeGreaterThanOrEqual(0);
      expect(r.selfConsumptionPct).toBeLessThanOrEqual(100 + 1e-9);
      expect(r.selfSufficiencyPct).toBeGreaterThanOrEqual(0);
      expect(r.selfSufficiencyPct).toBeLessThanOrEqual(100 + 1e-9);
    }
  });
});

describe('WJ120 — heures de secours : linéaires en N, sur charges ESSENTIELLES', () => {
  it('backup(2) ≈ 2 × backup(1), backup(0) = 0', () => {
    const b1 = simulateBattery(baseInput(1)).backupHours;
    const b2 = simulateBattery(baseInput(2)).backupHours;
    const b0 = simulateBattery(baseInput(0)).backupHours;
    expect(b0).toBe(0);
    expect(b1).toBeGreaterThan(0);
    expect(b2).toBeCloseTo(2 * b1, 6);
  });
  it('valeur = capacité utile × rendement décharge ÷ charge essentielle', () => {
    const r = simulateBattery(baseInput(1));
    const usable = 1 * DEYNESS_CAPACITY_KWH['BAT-DEY-5'] * BATTERY_DEPTH_OF_DISCHARGE;
    const expected = (usable * BATTERY_ONE_WAY_EFFICIENCY) / (ESSENTIAL_LOAD_W / 1000);
    expect(r.backupHours).toBeCloseTo(expected, 6);
  });
});

describe('WJ120 — jour 2 (régime permanent, SoC reporté) ≠ jour 1 démarré batterie vide', () => {
  it('le jour 2 décharge PLUS (leftover de la veille sert le matin) et importe MOINS', () => {
    const r = simulateBattery(baseInput(2)); // ~9 kWh utiles : leftover overnight
    expect(r.fromBatteryKwh).toBeGreaterThan(r.day1.fromBatteryKwh);
    expect(r.fromGridKwh).toBeLessThan(r.day1.fromGridKwh);
  });
});

describe('WJ120 — capacité par unité : STRICTEMENT réfs catalogue 5/10, jamais le 6', () => {
  it('5 et 10 kWh mènent à des capacités utiles différentes (jamais BATTERY_KWH_PER_DAY=6)', () => {
    const r5 = simulateBattery(baseInput(1, { capacityKwhPerUnit: 5 }));
    const r10 = simulateBattery(baseInput(1, { capacityKwhPerUnit: 10 }));
    expect(r5.usableCapacityKwh).toBeCloseTo(5 * BATTERY_DEPTH_OF_DISCHARGE, 6);
    expect(r10.usableCapacityKwh).toBeCloseTo(10 * BATTERY_DEPTH_OF_DISCHARGE, 6);
    // Le 6 (kWh/jour) n'apparaît nulle part comme capacité de stockage.
    expect(r5.usableCapacityKwh).not.toBeCloseTo(6, 3);
  });
});

describe('WJ120 — moteur déterministe sur silhouettes triviales (vérif à la main)', () => {
  // Conso 100 % à 20 h, production 100 % à 12 h ; rendement/DoD parfaits.
  const cons = new Array(24).fill(0);
  cons[20] = 1;
  const prod = new Array(24).fill(0);
  prod[12] = 1;
  const perfect: BatterySimInput = {
    consumptionShape: cons,
    productionShape: prod,
    dailyConsumptionKwh: 10,
    dailyProductionKwh: 10,
    capacityKwhPerUnit: 10,
    units: 1,
    oneWayEfficiency: 1,
    depthOfDischarge: 1,
  };
  it('1 batterie parfaite décale tout le solaire de midi vers le soir → 100 % autosuffisant', () => {
    const r = simulateBattery(perfect);
    expect(r.directKwh).toBeCloseTo(0, 6);
    expect(r.fromBatteryKwh).toBeCloseTo(10, 6);
    expect(r.fromGridKwh).toBeCloseTo(0, 6);
    expect(r.exportedKwh).toBeCloseTo(0, 6);
    expect(r.selfSufficiencyPct).toBeCloseTo(100, 6);
    expect(r.selfConsumptionPct).toBeCloseTo(100, 6);
  });
  it('0 batterie : le solaire de midi est exporté, le soir vient du réseau', () => {
    const r = simulateBattery({ ...perfect, units: 0 });
    expect(r.fromBatteryKwh).toBe(0);
    expect(r.fromGridKwh).toBeCloseTo(10, 6);
    expect(r.exportedKwh).toBeCloseTo(10, 6);
    expect(r.selfSufficiencyPct).toBeCloseTo(0, 6);
    expect(r.selfConsumptionPct).toBeCloseTo(0, 6);
  });
});

describe('WJ120 — resolveOfferBattery : capacité depuis les réfs catalogue, unités = quantité', () => {
  const mkItem = (designation: string, quantite = 1): ProposalItem => ({
    designation,
    quantite,
    prix_unit_ht: 0,
    prix_unit_ttc: 0,
    remise: 0,
    marque: '',
    taux_tva: 0,
  });
  it('BAT-DEY-10 → 10 kWh, quantité reportée', () => {
    const r = resolveOfferBattery([mkItem('Batterie Deyness 10 kWh (BAT-DEY-10)', 2)]);
    expect(r.present).toBe(true);
    expect(r.capacityKwhPerUnit).toBe(10);
    expect(r.units).toBe(2);
  });
  it('BAT-DEY-5 → 5 kWh', () => {
    const r = resolveOfferBattery([mkItem('Batterie lithium Deyness 5 kWh (BAT-DEY-5)')]);
    expect(r.capacityKwhPerUnit).toBe(5);
    expect(r.units).toBe(1);
  });
  it('repli « N kWh » explicite dans une ligne batterie', () => {
    const r = resolveOfferBattery([mkItem('Batterie LFP 5 kWh')]);
    expect(r.present).toBe(true);
    expect(r.capacityKwhPerUnit).toBe(5);
  });
  it('aucune ligne batterie → present=false, capacité null', () => {
    const r = resolveOfferBattery([mkItem('Panneau photovoltaïque 550 W'), mkItem('Onduleur hybride 5 kW')]);
    expect(r.present).toBe(false);
    expect(r.capacityKwhPerUnit).toBeNull();
    expect(r.units).toBe(0);
  });
  it('entrée vide/nulle → objet vide sûr', () => {
    expect(resolveOfferBattery(null).present).toBe(false);
    expect(resolveOfferBattery(undefined).present).toBe(false);
    expect(resolveOfferBattery([]).present).toBe(false);
  });
});

describe('WJ120 — renderBatterySplitSvg : aire empilée pure (direct/batterie/réseau)', () => {
  const r = simulateBattery(baseInput(2));
  const svg = renderBatterySplitSvg(r.hourly, undefined, 'fr');
  it('émet un SVG accessible (role img + title/desc)', () => {
    expect(svg).toContain('<svg');
    expect(svg).toContain('role="img"');
    expect(svg).toContain('<title>');
    expect(svg).toContain('<desc>');
  });
  it('trois bandes cumulées : direct (laiton), batterie (azur), réseau (faint)', () => {
    expect(svg).toContain('var(--color-brass-400');
    expect(svg).toContain('var(--color-azur-300');
    expect(svg).toContain('var(--color-lune-faint');
    // Trois <path> (une bande par origine).
    expect((svg.match(/<path /g) ?? []).length).toBe(3);
  });
  it('les libellés AR restent une chaîne SVG valide (rendu tri-langue)', () => {
    const ar = renderBatterySplitSvg(r.hourly, undefined, 'ar');
    expect(ar).toContain('<svg');
    expect(ar).toContain('role="img"');
  });
});
