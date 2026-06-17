// Cerveau V4 de l'estimateur — src/lib/estimatorBrainV4.ts (preview privé pro-7).
// V4 COMPOSE sur V2/V3 sans les modifier. Ces tests prouvent :
//  1. MAPPING AZIMUT→ASPECT PVGIS : Sud=0, Est=−90, Ouest=+90, Nord=180 (un mauvais
//     signe corromprait silencieusement la production).
//  2. OPTIMUM = VRAI MAXIMUM DE LA GRILLE : avec un rendement injecté qui pique à un
//     (tilt, aspect) donné, le gagnant est bien cette config — pas un preset.
//  3. PVGIS = SOURCE DE VÉRITÉ : injecter PVGIS déplace la reco par rapport à la
//     table committée (inclinaison gagnante différente).
//  4. REPLI GRACIEUX : sans PVGIS (ou PVGIS=null), on retombe sur la table et la
//     source est « estimate », l'optimum reste valide.
// Voir apps/web/BRAIN_V4_NOTES.md.
import { describe, expect, it } from 'vitest';
import {
  aspectFromCompass,
  pvgisLegs,
  fineTiltGrid,
  fineGridOptimum,
  pvgisCandidatePairs,
  type YieldFn,
} from '../src/lib/estimatorBrainV4';
import { optimalSouthTiltDeg } from '../src/lib/estimatorBrainV2';
import type { LngLat } from '../src/lib/roof';

const DEG = Math.PI / 180;
const LAT = 33.59;

function squareRing(side: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

// ——————————————————————————————————————————————————————————————————————
// 1. Mapping azimut boussole → aspect PVGIS.
// ——————————————————————————————————————————————————————————————————————
describe('V4 — aspect PVGIS (Sud=0, Est=−90, Ouest=+90, Nord=180)', () => {
  it('mappe les quatre cardinaux correctement', () => {
    expect(aspectFromCompass(180)).toBe(0); // Sud
    expect(aspectFromCompass(90)).toBe(-90); // Est
    expect(aspectFromCompass(270)).toBe(90); // Ouest
    expect(aspectFromCompass(0)).toBe(180); // Nord
    expect(aspectFromCompass(360)).toBe(180); // Nord (équivalent)
  });

  it('intermédiaires : Sud-Est négatif, Sud-Ouest positif', () => {
    expect(aspectFromCompass(135)).toBe(-45); // Sud-Est
    expect(aspectFromCompass(225)).toBe(45); // Sud-Ouest
  });

  it('jambes PVGIS : Sud = 1 jambe (aspect=azimut−180), Est-Ouest = 2 jambes', () => {
    const south = pvgisLegs('south', 30, 180, 6);
    expect(south).toHaveLength(1);
    expect(south[0]).toMatchObject({ kwc: 6, tiltDeg: 30, aspect: 0 });
    const ew = pvgisLegs('eastwest', 12, 90, 6);
    expect(ew).toHaveLength(2);
    expect(ew.map((l) => l.aspect).sort((a, b) => a - b)).toEqual([-90, 90]);
    expect(ew.every((l) => l.kwc === 3)).toBe(true);
  });
});

// ——————————————————————————————————————————————————————————————————————
// 2. La grille fine couvre 5..35 + l'optimum table.
// ——————————————————————————————————————————————————————————————————————
describe('V4 — grille fine d\'inclinaison', () => {
  it('inclut 5°→35° par pas de 5 et l\'optimum Sud de la table, borné [5,35]', () => {
    const grid = fineTiltGrid(LAT);
    expect(grid[0]).toBeGreaterThanOrEqual(5);
    expect(grid[grid.length - 1]).toBeLessThanOrEqual(35);
    for (const t of [5, 10, 15, 20, 25, 30, 35]) expect(grid).toContain(t);
    expect(grid).toContain(optimalSouthTiltDeg(LAT));
    expect([...grid].sort((a, b) => a - b)).toEqual(grid); // trié
  });

  it('couples PVGIS candidats : Sud (aspect 0) sur toit aligné ; aligné + E-O sur toit tourné', () => {
    // Toit plein sud (roofAz=180) : seul l'axe Sud, aspect 0 présent, pas de 180.
    const flat = pvgisCandidatePairs(LAT, 180);
    expect(flat.some((p) => p.aspect === 0)).toBe(true);
    expect(flat.some((p) => Math.abs(p.aspect) === 180)).toBe(false);
    // Toit tourné de 25° : l'axe aligné ouvre des aspects décalés du sud.
    const turned = pvgisCandidatePairs(LAT, 205);
    expect(turned.length).toBeGreaterThan(flat.length);
    expect(turned.some((p) => p.aspect !== 0 && Math.abs(p.aspect) < 90)).toBe(true);
  });
});

// ——————————————————————————————————————————————————————————————————————
// 3. L'optimum est le VRAI maximum de la grille, piloté par le rendement injecté.
// ——————————————————————————————————————————————————————————————————————
describe('V4 — optimum = vrai maximum sur la grille (PVGIS injecté)', () => {
  // Toit carré spacieux, non tourné (seul l'axe Sud est ouvert), petite facture →
  // tous les tilts logent le besoin : la production ∝ rendement/panneau injecté.
  const ring = squareRing(20);
  const bill = 1500;

  it('pique le gagnant sur le (tilt, Sud) du pic injecté, pas sur un preset', () => {
    const peakTilt = 20;
    const yieldFn: YieldFn = (tilt, aspect) =>
      Math.max(200, 1600 - Math.abs(tilt - peakTilt) * 8 - Math.abs(aspect) * 6);
    const res = fineGridOptimum(ring, LAT, bill, [], { yieldFn });
    expect(res.winner.family).toBe('south');
    expect(res.winner.azimuth).toBe('south');
    expect(res.winner.tiltDeg).toBe(peakTilt);
    expect(res.yieldSource).toBe('pvgis');
    expect(res.optimumRow.yieldSource).toBe('pvgis');
  });

  it('PVGIS = source de vérité : déplace l\'inclinaison gagnante vs la table seule', () => {
    // Table seule → optimum ≈ optimalSouthTilt (~29-30° à Casablanca).
    const tableOnly = fineGridOptimum(ring, LAT, bill, []);
    expect(tableOnly.yieldSource).toBe('estimate');
    expect(tableOnly.winner.tiltDeg).toBeGreaterThanOrEqual(25);

    // PVGIS injecté piquant à plat (10°) → l'optimum devient plat, PROUVANT que
    // c'est PVGIS qui pilote la recherche, pas la table.
    const flatPeak: YieldFn = (tilt, aspect) =>
      Math.max(200, 1700 - Math.abs(tilt - 10) * 12 - Math.abs(aspect) * 6);
    const pvgis = fineGridOptimum(ring, LAT, bill, [], { yieldFn: flatPeak });
    expect(pvgis.winner.tiltDeg).toBe(10);
    expect(pvgis.winner.tiltDeg).not.toBe(tableOnly.winner.tiltDeg);
  });
});

// ——————————————————————————————————————————————————————————————————————
// 4. Repli gracieux : PVGIS injoignable (yieldFn→null) → table, source « estimate ».
// ——————————————————————————————————————————————————————————————————————
describe('V4 — repli gracieux quand PVGIS est indisponible', () => {
  const ring = squareRing(20);

  it('yieldFn=null partout → identique à la table seule, source estimate', () => {
    const nullFn: YieldFn = () => null;
    const withNull = fineGridOptimum(ring, LAT, 1500, [], { yieldFn: nullFn });
    const tableOnly = fineGridOptimum(ring, LAT, 1500, []);
    expect(withNull.yieldSource).toBe('estimate');
    expect(withNull.winner.tiltDeg).toBe(tableOnly.winner.tiltDeg);
    expect(withNull.winner.family).toBe(tableOnly.winner.family);
    expect(Math.round(withNull.winner.annualKwh)).toBe(Math.round(tableOnly.winner.annualKwh));
  });

  it('optimumRow décrit l\'optimum (label + raison + standard) et plafonne au besoin', () => {
    const res = fineGridOptimum(ring, LAT, 1500, []);
    expect(res.optimumRow.label).toContain('Optimum calculé');
    expect(res.optimumRow.reason.length).toBeGreaterThan(10);
    expect(typeof res.optimumRow.isStandard).toBe('boolean');
    expect(res.winner.placedCount).toBeLessThanOrEqual(res.neededPanels);
  });
});
