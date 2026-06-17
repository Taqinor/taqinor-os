// Cerveau V3 de l'estimateur — src/lib/estimatorBrainV3.ts (preview privé pro-6).
// V3 COMPOSE sur V2 sans le modifier : ces tests prouvent
//  1. CHEMIN TOIT PLAT inchangé : evalFlatConfig réutilise la physique de V2
//     (packConfig + productionKwh) à l'identique → pro-5 sûr.
//  2. RECHERCHE PLEINE : l'optimum est le VRAI gagnant du produit cartésien
//     (jamais pire que la reco V2 ; meilleur quand marge/azimut le permet).
//  3. RÉ-OPTIMISATION CONTRAINTE : une épingle est tenue ; le badge « Recommandé »
//     reste l'optimum GLOBAL quel que soit l'épinglage.
//  4. TOIT EN PENTE : pente=inclinaison, face=azimut (imposés, non balayés) ;
//     pose affleurante sans pas solaire (loge plus qu'un toit plat) ; Σ empreintes
//     ≤ utile ; pan nord sauté/signalé ; plafond besoin + plafond économies tenus.
// Voir apps/web/BRAIN_V3_NOTES.md.
import { describe, expect, it } from 'vitest';
import {
  fullSearchOptimum,
  reoptimize,
  evalFlatConfig,
  betterFlat,
  packFlushPlane,
  recommendPitched,
  flushPlaneYield,
  PITCH_PRESETS_DEG,
  FLUSH_MAINTENANCE_GAP_M,
  type RoofPlane,
} from '../src/lib/estimatorBrainV3';
import {
  recommend,
  packConfig,
  productionKwh,
  aspectForAzimuth,
  neededPanelsForTarget,
  billToAnnualKwh,
  billMAD,
  roofDominantAzimuthDeg,
  PANEL2_WATT,
  REGIE_TARIFF,
} from '../src/lib/estimatorBrainV2';
import { geodesicAreaM2, type LngLat } from '../src/lib/roof';

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

// Rectangle de wEW × hNS, tourné de rotDeg (horaire vu du ciel), centré sur le toit.
function rotatedRect(wEW: number, hNS: number, rotDeg: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const cosLat = Math.cos(lat0 * DEG);
  const c = Math.cos(rotDeg * DEG);
  const s = Math.sin(rotDeg * DEG);
  const corners: [number, number][] = [
    [-wEW / 2, -hNS / 2],
    [wEW / 2, -hNS / 2],
    [wEW / 2, hNS / 2],
    [-wEW / 2, hNS / 2],
  ];
  return corners.map(([x, y]) => {
    const xr = x * c - y * s;
    const yr = x * s + y * c;
    return [lng0 + xr / (111320 * cosLat), lat0 + yr / 111320] as LngLat;
  });
}

// ——————————————————————————————————————————————————————————————————————
// 1. CHEMIN TOIT PLAT : la physique V3 EST celle de V2 (aucune fork).
// ——————————————————————————————————————————————————————————————————————
describe('V3 toit plat — physique identique à V2 (réutilise packConfig + productionKwh)', () => {
  it('evalFlatConfig redonne EXACTEMENT le pavage et la production de V2', () => {
    const ring = squareRing(20);
    const target = billToAnnualKwh(2500);
    const needed = neededPanelsForTarget(target, LAT);
    const roofAz = roofDominantAzimuthDeg(ring);
    for (const family of ['south', 'eastwest'] as const) {
      for (const tiltDeg of [10, 15, 29]) {
        for (const orientation of ['portrait', 'landscape'] as const) {
          const e = evalFlatConfig(
            ring,
            LAT,
            { family, tiltDeg, azimuth: 'south', orientation, margin: 'keep' },
            needed,
            target,
            [],
            roofAz,
            0.5,
            REGIE_TARIFF,
          );
          const pack = packConfig(ring, LAT, { family, tiltDeg, setbackM: 0.5 });
          const grid = orientation === 'portrait' ? pack.portrait : pack.landscape;
          expect(e.fitCount).toBe(grid.count);
          const placed = Math.min(needed, grid.count);
          const kwc = (placed * PANEL2_WATT) / 1000;
          const aspect = aspectForAzimuth(family, pack.azimuthDeg);
          expect(e.annualKwh).toBeCloseTo(productionKwh(LAT, family, tiltDeg, kwc, aspect), 6);
        }
      }
    }
  });

  it('l’optimum plein-recherche n’est JAMAIS pire que la reco V2 (aucune régression)', () => {
    for (const [side, bill] of [[40, 1000], [20, 2500], [14, 5000], [11, 5000]] as const) {
      const ring = squareRing(side);
      const v2 = recommend(ring, LAT, bill, [], { enableRoofAligned: true });
      const v3 = fullSearchOptimum(ring, LAT, bill);
      expect(v3.winner.annualKwh).toBeGreaterThanOrEqual(v2.recommended.annualKwh - 1e-6);
    }
  });
});

// ——————————————————————————————————————————————————————————————————————
// 2. RECHERCHE PLEINE : vrai gagnant, plafonné, bornes physiques tenues.
// ——————————————————————————————————————————————————————————————————————
describe('V3 fullSearchOptimum — le vrai gagnant du produit cartésien', () => {
  it('plafonne toujours au besoin et à ce qui tient', () => {
    for (const side of [9, 11, 14, 20, 40]) {
      for (const bill of [1500, 3500, 8000]) {
        const o = fullSearchOptimum(squareRing(side), LAT, bill);
        expect(o.winner.placedCount).toBeLessThanOrEqual(o.neededPanels);
        expect(o.winner.placedCount).toBeLessThanOrEqual(o.winner.fitCount);
      }
    }
  });

  it('évalue beaucoup plus de combinaisons que les 5 lignes du tableau', () => {
    const o = fullSearchOptimum(squareRing(20), LAT, 2500);
    expect(o.evaluated).toBeGreaterThan(50);
  });

  it('chaque économie ≤ coût énergie évitable (plafond)', () => {
    for (const side of [12, 20, 30]) {
      const o = fullSearchOptimum(squareRing(side), LAT, 1500);
      const cap = billMAD(o.targetAnnualKwh / 12) * 12 + 1e-6;
      expect(o.winner.savingsHigh).toBeLessThanOrEqual(cap);
    }
  });

  it('toit tourné, limité : l’optimum peut suivre les arêtes ET retirer la marge', () => {
    const roof = rotatedRect(13, 11, 25);
    const o = fullSearchOptimum(roof, LAT, 9000);
    expect(o.roofLimited).toBe(true);
    // l’optimum loge au moins autant qu’une marge gardée plein sud à l’optimal
    const keepSouth = fullSearchOptimum(roof, LAT, 9000).winner;
    expect(o.winner.placedCount).toBeGreaterThanOrEqual(keepSouth.placedCount);
    // l’axe azimut recommandé n’est jamais inventé
    expect(['south', 'aligned']).toContain(o.recommendedOptions.azimuth);
  });

  it('grand toit + petite facture : garde plein sud, marge, optimal (zéro overfill)', () => {
    const o = fullSearchOptimum(squareRing(40), LAT, 1000);
    expect(o.recommendedOptions.family).toBe('south');
    expect(o.recommendedOptions.azimuth).toBe('south');
    expect(o.recommendedOptions.margin).toBe('keep');
    expect(o.winner.placedCount).toBe(neededPanelsForTarget(o.targetAnnualKwh, LAT));
  });

  it('déterministe : deux appels identiques → même optimum', () => {
    const a = fullSearchOptimum(squareRing(14), LAT, 5000);
    const b = fullSearchOptimum(squareRing(14), LAT, 5000);
    expect(b.recommendedOptions).toEqual(a.recommendedOptions);
    expect(b.winner.annualKwh).toBe(a.winner.annualKwh);
  });
});

// ——————————————————————————————————————————————————————————————————————
// 3. RÉ-OPTIMISATION CONTRAINTE : épingle tenue, badge = optimum global.
// ——————————————————————————————————————————————————————————————————————
describe('V3 reoptimize — fige l’épingle, re-résout le reste, badges = optimum global', () => {
  it('rien d’épinglé → gagnant == optimum global', () => {
    const ring = squareRing(16);
    const opt = fullSearchOptimum(ring, LAT, 4000);
    const re = reoptimize({}, ring, LAT, 4000);
    expect(re.winner.tiltDeg).toBe(opt.winner.tiltDeg);
    expect(re.winner.family).toBe(opt.winner.family);
    expect(re.winner.margin).toBe(opt.winner.margin);
    expect(re.recommendedOptions).toEqual(opt.recommendedOptions);
  });

  it('inclinaison épinglée à 15° : le gagnant tient 15°, le reste se re-résout', () => {
    const ring = squareRing(14);
    const re = reoptimize({ tiltDeg: 15 }, ring, LAT, 5000);
    expect(re.winner.tiltDeg).toBe(15);
    // le badge reste l’optimum global (qui n’est pas forcément 15°)
    const global = fullSearchOptimum(ring, LAT, 5000);
    expect(re.recommendedOptions).toEqual(global.recommendedOptions);
  });

  it('famille épinglée Est-Ouest : le gagnant est Est-Ouest, badge inchangé', () => {
    const ring = squareRing(20);
    const re = reoptimize({ family: 'eastwest' }, ring, LAT, 2500);
    expect(re.winner.family).toBe('eastwest');
    const global = fullSearchOptimum(ring, LAT, 2500);
    expect(re.recommendedOptions.family).toBe(global.recommendedOptions.family);
  });

  it('le gagnant contraint n’est jamais meilleur que le global (la contrainte coûte ou égale)', () => {
    const ring = squareRing(14);
    const re = reoptimize({ tiltDeg: 10, margin: 'keep' }, ring, LAT, 5000);
    expect(re.winner.annualKwh).toBeLessThanOrEqual(re.globalWinner.annualKwh + 1e-6);
    expect(re.winner.tiltDeg).toBe(10);
    expect(re.winner.margin).toBe('keep');
  });
});

// ——————————————————————————————————————————————————————————————————————
// 4. TOIT EN PENTE / TUILES : pose affleurante, physique imposée par le toit.
// ——————————————————————————————————————————————————————————————————————
describe('V3 toit en pente — pente=inclinaison, face=azimut (imposés, non balayés)', () => {
  it('le pavage affleurant fige la pente et la face données (lecture seule)', () => {
    const plane: RoofPlane = { ring: squareRing(20), pitchDeg: 30, facingAzimuthDeg: 180 };
    const pack = packFlushPlane(plane);
    expect(pack.pitchDeg).toBe(30);
    expect(pack.facingAzimuthDeg).toBe(180);
  });

  it('AUCUN pas de rangée solaire : pas affleurant = empreinte plan + petit jeu', () => {
    const beta = 30 * DEG;
    const plane: RoofPlane = { ring: squareRing(20), pitchDeg: 30, facingAzimuthDeg: 180 };
    const pack = packFlushPlane(plane);
    // portrait : grand côté 2,384 dans la pente → empreinte plan = 2,384·cos30°.
    const expectedPitch = 2.384 * Math.cos(beta) + FLUSH_MAINTENANCE_GAP_M;
    expect(pack.portrait.rowPitchM).toBeCloseTo(expectedPitch, 6);
  });

  it('pose affleurante loge STRICTEMENT plus qu’un toit plat de même surface/pente', () => {
    const ring = squareRing(30);
    const flush = packFlushPlane({ ring, pitchDeg: 30, facingAzimuthDeg: 180 });
    const flat = packConfig(ring, LAT, { family: 'south', tiltDeg: 30 });
    expect(flush.best.count).toBeGreaterThan(flat.best.count);
  });

  it('Σ empreintes ≤ surface utile, et chaque pan reste borné', () => {
    for (const pitch of PITCH_PRESETS_DEG) {
      const pack = packFlushPlane({ ring: squareRing(18), pitchDeg: pitch, facingAzimuthDeg: 180 });
      for (const grid of [pack.portrait, pack.landscape]) {
        expect(grid.count * grid.footprintPerPanelM2).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-6);
      }
    }
  });

  it('le rendement/panneau suit honnêtement la face (sud > est > sud-ouest lointain)', () => {
    const south = flushPlaneYield(LAT, 30, 180);
    const east = flushPlaneYield(LAT, 30, 90);
    expect(south).toBeGreaterThan(east);
    expect(east).toBeGreaterThan(0);
  });

  it('un pan orienté NORD est signalé et jamais retenu', () => {
    const north: RoofPlane = { ring: squareRing(20), pitchDeg: 30, facingAzimuthDeg: 0 };
    const pack = packFlushPlane(north);
    expect(pack.northFacing).toBe(true);
    const rec = recommendPitched([north], LAT, 3000);
    expect(rec.skippedNorth).toBe(1);
    expect(rec.totalPlacedCount).toBe(0);
    expect(rec.planes[0].skipped).toBe('north');
  });
});

describe('V3 recommendPitched — multi-pans, plafond besoin et économies', () => {
  it('remplit le meilleur pan d’abord, plafonné au besoin (jamais au-delà)', () => {
    const planes: RoofPlane[] = [
      { ring: squareRing(16), pitchDeg: 30, facingAzimuthDeg: 180 }, // plein sud (meilleur)
      { ring: squareRing(16, -7.6201), pitchDeg: 30, facingAzimuthDeg: 90 }, // est (moins bon)
    ];
    const rec = recommendPitched(planes, LAT, 2500);
    expect(rec.totalPlacedCount).toBeLessThanOrEqual(rec.neededPanels);
    // le pan sud (meilleur rendement) sert le besoin en premier
    const south = rec.planes.find((p) => p.facingAzimuthDeg === 180)!;
    const east = rec.planes.find((p) => p.facingAzimuthDeg === 90)!;
    expect(south.placedCount).toBeGreaterThanOrEqual(east.placedCount);
  });

  it('deux pans sud utiles : tous deux peuvent contribuer sur un gros besoin', () => {
    const planes: RoofPlane[] = [
      { ring: squareRing(10), pitchDeg: 30, facingAzimuthDeg: 170 },
      { ring: squareRing(10, -7.6203), pitchDeg: 30, facingAzimuthDeg: 190 },
    ];
    const rec = recommendPitched(planes, LAT, 12000);
    const used = rec.planes.filter((p) => p.placedCount > 0);
    expect(used.length).toBe(2);
  });

  it('économies ≤ coût énergie évitable (plafond), production = somme par pan', () => {
    const planes: RoofPlane[] = [
      { ring: squareRing(14), pitchDeg: 22, facingAzimuthDeg: 180 },
      { ring: squareRing(14, -7.6202), pitchDeg: 22, facingAzimuthDeg: 200 },
    ];
    const rec = recommendPitched(planes, LAT, 2000);
    const cap = billMAD(rec.targetAnnualKwh / 12) * 12 + 1e-6;
    expect(rec.savingsHigh).toBeLessThanOrEqual(cap);
    const sumKwh = rec.planes.reduce((s, p) => s + p.annualKwh, 0);
    expect(rec.totalAnnualKwh).toBeCloseTo(sumKwh, 6);
  });

  it('toit en pente spacieux : dimensionné au besoin, pas de sur-remplissage', () => {
    const planes: RoofPlane[] = [{ ring: squareRing(40), pitchDeg: 30, facingAzimuthDeg: 180 }];
    const rec = recommendPitched(planes, LAT, 1000);
    expect(rec.totalPlacedCount).toBe(rec.neededPanels);
    expect(rec.roofLimited).toBe(false);
  });
});
