// Agrégation PURE des zones de panneaux (estimateur 3D pro-11 « plusieurs zones »).
// Vérifie : aggregateAreas somme champ par champ, ignore les null, retombe à zéro
// sur une liste vide / tout-null ; les économies sont SOMMÉES (jamais re-plafonnées) ;
// areaLabel produit « Zone N » (1-based à l'affichage).
import { describe, expect, it } from 'vitest';
import { aggregateAreas, areaLabel, emptyResult, type AreaResult } from '../src/lib/roofAreas';

const mk = (panels: number, kwc: number, annualKwh: number, savingsLow: number, savingsHigh: number): AreaResult => ({
  panels,
  kwc,
  annualKwh,
  savingsLow,
  savingsHigh,
});

describe('aggregateAreas — somme champ par champ', () => {
  it('additionne deux zones non nulles', () => {
    const total = aggregateAreas([mk(10, 7.2, 12000, 8000, 9000), mk(5, 3.6, 6000, 4000, 4500)]);
    expect(total).toEqual({ panels: 15, kwc: 10.8, annualKwh: 18000, savingsLow: 12000, savingsHigh: 13500 });
  });

  it('additionne trois zones (panneaux et kWc cumulés)', () => {
    const total = aggregateAreas([mk(4, 2.88, 4800, 3000, 3300), mk(6, 4.32, 7200, 4500, 5000), mk(8, 5.76, 9600, 6000, 6600)]);
    expect(total.panels).toBe(18);
    expect(total.kwc).toBeCloseTo(12.96, 6);
    expect(total.annualKwh).toBe(21600);
    expect(total.savingsLow).toBe(13500);
    expect(total.savingsHigh).toBe(14900);
  });

  it('liste vide → résultat à zéro', () => {
    expect(aggregateAreas([])).toEqual(emptyResult());
    expect(aggregateAreas([])).toEqual({ panels: 0, kwc: 0, annualKwh: 0, savingsLow: 0, savingsHigh: 0 });
  });

  it('ignore les null (zones non calculées) et somme le reste', () => {
    const total = aggregateAreas([null, mk(10, 7.2, 12000, 8000, 9000), null, mk(2, 1.44, 2400, 1500, 1700)]);
    expect(total).toEqual({ panels: 12, kwc: 8.64, annualKwh: 14400, savingsLow: 9500, savingsHigh: 10700 });
  });

  it('liste tout-null → résultat à zéro', () => {
    expect(aggregateAreas([null, null])).toEqual(emptyResult());
  });

  it('les économies sont SOMMÉES, pas re-plafonnées', () => {
    // Deux zones avec économies élevées : le total est la SOMME, pas un plafond global.
    const total = aggregateAreas([mk(20, 14.4, 24000, 18000, 20000), mk(20, 14.4, 24000, 18000, 20000)]);
    expect(total.savingsLow).toBe(36000);
    expect(total.savingsHigh).toBe(40000);
  });
});

describe('areaLabel — « Zone N » 1-based', () => {
  it('mappe l\'index 0-based sur un libellé 1-based', () => {
    expect(areaLabel(0)).toBe('Zone 1');
    expect(areaLabel(1)).toBe('Zone 2');
    expect(areaLabel(4)).toBe('Zone 5');
  });
});

describe('emptyResult — zéros', () => {
  it('renvoie un résultat tout à zéro et un nouvel objet à chaque appel', () => {
    const a = emptyResult();
    const b = emptyResult();
    expect(a).toEqual({ panels: 0, kwc: 0, annualKwh: 0, savingsLow: 0, savingsHigh: 0 });
    expect(a).not.toBe(b);
  });
});
