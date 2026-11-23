// CAL84 — statistiques par pan, totalisées par bâtiment puis par site. Toutes les
// colonnes sont calculées ; ce test prouve que la somme des lignes == le total.
import { describe, expect, it } from 'vitest';
import { computePanStats, computeSiteStats, hasMultipleBuildings, htmlTableSite, PANEL_FOOTPRINT_M2 } from './panStats';
import { ctxDeBase, panDeTest, rectRing } from './harnaisAtelier'; // ACAL1420
import { JSDOM } from 'jsdom'; // ACAL1420
import { createZones } from './zones'; // ACAL1420
import { type Ctx } from './context'; // ACAL1420
import { type AreaRecord } from './types';
import { type AreaResult } from '../../lib/roofAreas';

const zone = panDeTest;

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

describe('ACAL981 — libellé du bâtiment et motif du contour', () => {
  it('un pan fermé d’aire positive ne porte pas « contour du pan non tracé » ; un contour ouvert le porte', () => {
    const ferme = computeSiteStats(computePanStats([zone('a')], () => null), []);
    expect(ferme.lignes[0].motif).not.toContain('non tracé');
    const ouvert = computeSiteStats(computePanStats([zone('a', { vertices: [] })], () => null), []);
    expect(ouvert.lignes[0].motif).toBe('contour du pan non tracé');
  });

  it('un contour de 3 sommets confondus (aire nulle) dit « aire nulle : vérifiez le contour »', () => {
    const p: [number, number] = [-7.6, 33.5];
    const stats = computeSiteStats(computePanStats([zone('a', { vertices: [p, p, p] })], () => null), []);
    expect(stats.lignes[0].motif).toBe('aire nulle : vérifiez le contour');
  });

  // ACAL1420 — le pan ACTIF se mesure sur ses sommets VIVANTS (`ctx.vertices`) : son enregistrement n'est synchronisé
  // qu'au changement de pan, et un toit tout juste fermé disait « contour du pan non tracé » à côté de ses 63 m².
  it('pan actif aux sommets vivants : aire > 0 dans le tableau Site, aucun « non tracé »', () => {
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body><div id="rp9-areas"></div></body>').window.document;
    try {
      const pan = zone('area-1', { vertices: [], roofType: 'flat' }); // enregistrement périmé : le tracé vit sur ctx
      const vivants = rectRing(9, 7);
      const ctx = { ...ctxDeBase([pan]), vertices: vivants, activeArea: () => pan, closed: true, roofType: 'flat',
        liveResult: { winner: { placedCount: 10, kwc: 7.2, annualKwh: 12000, savingsLow: 1, savingsHigh: 2 }, target: 12000 },
        shadeAnnualFactor: 1, horizonAnnualFactor: 1, dom: { areasWindowEl: document.getElementById('rp9-areas') } } as unknown as Ctx;
      createZones(ctx, { setStatus: () => undefined }).renderAreasPanel();
      const ligne = document.querySelector('[data-site-ligne="area-1"]')?.textContent ?? '';
      expect(ligne).not.toContain('non tracé');
      expect(ligne).toContain('63');
      expect(document.querySelector('[data-site-total=""]')?.textContent).not.toContain('sans contour mesuré');
    } finally { g.document = avant; }
  });

  it('htmlTableSite d’un groupe sans identifiant écrit « Bâtiment 1 », jamais « Bâtiment sans id »', () => {
    const html = htmlTableSite(computeSiteStats(computePanStats([zone('a')], () => RESULT_OK), []));
    expect(html).toContain('Bâtiment 1');
    expect(html).not.toContain('sans id');
    expect(html).toContain('Total Bâtiment 1');
  });

  it('deux groupes dont un sans identifiant : rang par ordre, l’identifiant saisi reste tel quel', () => {
    const html = htmlTableSite(computeSiteStats(computePanStats([zone('a', { buildingId: 'bat-A' }), zone('b')], () => RESULT_OK), []));
    expect(html).toContain('bat-A');
    expect(html).toContain('Bâtiment 2');
  });
});
