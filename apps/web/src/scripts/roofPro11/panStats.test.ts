// CAL84 — statistiques par pan, totalisées par bâtiment puis par site. Toutes les
// colonnes sont calculées ; ce test prouve que la somme des lignes == le total.
import { describe, expect, it } from 'vitest';
import { computePanStats, hasMultipleBuildings, PANEL_FOOTPRINT_M2 } from './panStats';
import { type AreaRecord } from './types';
import { type AreaResult } from '../../lib/roofAreas';

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'pitched',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...opts,
  };
}

const RESULT_OK: AreaResult = { panels: 10, kwc: 7.2, annualKwh: 12000, savingsLow: 1000, savingsHigh: 1500 };

describe('CAL84 — computePanStats', () => {
  it('la somme des lignes égale exactement le total du site', () => {
    const areas = [zone('a'), zone('b')];
    const stats = computePanStats(areas, () => RESULT_OK);
    const sumPanels = stats.pans.reduce((s, p) => s + p.panels, 0);
    const sumKwc = stats.pans.reduce((s, p) => s + p.kwc, 0);
    expect(sumPanels).toBe(stats.site.panels);
    expect(sumKwc).toBeCloseTo(stats.site.kwc, 9);
  });

  it('un pan sans panneau apparaît avec zéro panneau et une raison non vide', () => {
    const areas = [zone('a', { vertices: [] })];
    const stats = computePanStats(areas, () => null);
    expect(stats.pans[0].panels).toBe(0);
    expect(stats.pans[0].zeroReason.length).toBeGreaterThan(0);
    expect(stats.pans[0].zeroReason).toBe('toit non tracé');
  });

  it('un pan avec contour mais sans résultat calculé porte un motif différent', () => {
    const areas = [zone('a')];
    const stats = computePanStats(areas, () => null);
    expect(stats.pans[0].zeroReason).toBe('à calculer');
  });

  it('totalise par bâtiment quand buildingId est renseigné', () => {
    const areas = [zone('a', { buildingId: 'bat-1' }), zone('b', { buildingId: 'bat-1' }), zone('c', { buildingId: 'bat-2' })];
    const stats = computePanStats(areas, () => RESULT_OK);
    expect(hasMultipleBuildings(stats)).toBe(true);
    expect(stats.byBuilding).toHaveLength(2);
    const bat1 = stats.byBuilding.find((b) => b.buildingId === 'bat-1')!;
    expect(bat1.panels).toBe(20); // 2 pans × 10
    const bat2 = stats.byBuilding.find((b) => b.buildingId === 'bat-2')!;
    expect(bat2.panels).toBe(10);
    expect(bat1.panels + bat2.panels).toBe(stats.site.panels);
  });

  it('sans buildingId sur aucun pan, pas de sous-totaux redondants (un seul groupe)', () => {
    const areas = [zone('a'), zone('b')];
    const stats = computePanStats(areas, () => RESULT_OK);
    expect(hasMultipleBuildings(stats)).toBe(false);
  });

  it('taux d’occupation = surface panneaux posés / surface utile, calculé (jamais saisi)', () => {
    const areas = [zone('a')];
    const stats = computePanStats(areas, () => RESULT_OK);
    const p = stats.pans[0];
    expect(p.areaM2).toBeGreaterThan(0);
    expect(p.occupancyRate).toBeCloseTo((RESULT_OK.panels * PANEL_FOOTPRINT_M2) / p.areaM2, 9);
  });

  it('azimut/pente sont null pour un toit PLAT (n’a pas de sens)', () => {
    const areas = [zone('a', { roofType: 'flat' })];
    const stats = computePanStats(areas, () => RESULT_OK);
    expect(stats.pans[0].azimuthDeg).toBeNull();
    expect(stats.pans[0].pitchDeg).toBeNull();
  });
});
