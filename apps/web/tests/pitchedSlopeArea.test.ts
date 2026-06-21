// Cerveau EN PENTE — aire VRAIE du versant (src/lib/estimatorBrainV3 + V8).
// Un toit incliné est RACCOURCI horizontalement sur l'imagerie satellite : il paraît
// plus petit qu'il ne l'est. La surface réelle du pan = aire projetée / cos(pente).
// Ces tests prouvent :
//  1. `slopeAreaM2` : pente 0 → inchangé ; 30° → ÷cos30° ; 45° → ÷cos45°.
//  2. `packFlushPlane` expose `slopeAreaM2`/`usableSlopeAreaM2` = projeté ÷ cos(pente),
//     STRICTEMENT > projeté à pente non nulle, ÉGAL à pente 0.
//  3. RÉGRESSION : le COMPTE de panneaux d'un même tracé+pente est INCHANGÉ — on n'a
//     fait qu'ajouter une aire honnête, jamais touché au pavage ni à la production.
//  4. `solveLivePitched` relaie `slopeAreaM2`/`usableSlopeAreaM2` (> 0) pour un pan sud.
import { describe, expect, it } from 'vitest';
import {
  packFlushPlane,
  slopeAreaM2,
  type RoofPlane,
} from '../src/lib/estimatorBrainV3';
import { solveLivePitched } from '../src/lib/estimatorBrainV8';
import { type LngLat } from '../src/lib/roof';

const DEG = Math.PI / 180;
const LAT = 33.59;
const BILL = 1500;

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

describe('slopeAreaM2 — aire projetée → aire vraie du versant', () => {
  it('pente 0 : aire inchangée', () => {
    expect(slopeAreaM2(100, 0)).toBe(100);
  });

  it('pente 30° : aire = projetée / cos(30°) ≈ 115,47', () => {
    expect(slopeAreaM2(100, 30)).toBeCloseTo(100 / Math.cos(30 * DEG), 6);
    expect(slopeAreaM2(100, 30)).toBeCloseTo(115.4700538, 5);
  });

  it('pente 45° : aire = projetée / cos(45°) ≈ 141,42', () => {
    expect(slopeAreaM2(100, 45)).toBeCloseTo(100 / Math.cos(45 * DEG), 6);
    expect(slopeAreaM2(100, 45)).toBeCloseTo(141.4213562, 5);
  });

  it('garde-fous : cos ≤ 0 ou non fini → on renvoie l’aire projetée', () => {
    expect(slopeAreaM2(100, 120)).toBe(100); // cos < 0 (saisie aberrante)
    expect(slopeAreaM2(100, 180)).toBe(100); // cos = -1
    expect(slopeAreaM2(100, Number.NaN)).toBe(100); // non fini
  });
});

describe('packFlushPlane — aire VRAIE du pan exposée', () => {
  it('pente 30° : slopeAreaM2 ≈ areaM2 / cos(30°) et > areaM2', () => {
    const plane: RoofPlane = { ring: squareRing(20), pitchDeg: 30, facingAzimuthDeg: 180 };
    const pack = packFlushPlane(plane);
    expect(pack.slopeAreaM2).toBeCloseTo(pack.areaM2 / Math.cos(30 * DEG), 6);
    expect(pack.slopeAreaM2).toBeGreaterThan(pack.areaM2);
    expect(pack.usableSlopeAreaM2).toBeCloseTo(pack.usableAreaM2 / Math.cos(30 * DEG), 6);
    expect(pack.usableSlopeAreaM2).toBeGreaterThanOrEqual(pack.usableAreaM2);
  });

  it('pente 0 : slopeAreaM2 === areaM2 (aucune correction)', () => {
    const plane: RoofPlane = { ring: squareRing(20), pitchDeg: 0, facingAzimuthDeg: 180 };
    const pack = packFlushPlane(plane);
    expect(pack.slopeAreaM2).toBe(pack.areaM2);
    expect(pack.usableSlopeAreaM2).toBe(pack.usableAreaM2);
  });

  it('RÉGRESSION : le compte de panneaux d’un tracé+pente fixés est INCHANGÉ', () => {
    const plane: RoofPlane = { ring: squareRing(18), pitchDeg: 30, facingAzimuthDeg: 180 };
    const pack = packFlushPlane(plane);
    // On n'a ajouté que l'aire honnête : le pavage/compte/production restent les mêmes.
    expect(pack.best.count).toBeGreaterThan(0);
    expect(Number.isInteger(pack.best.count)).toBe(true);
    expect(pack.best.kwc).toBeGreaterThan(0);
    // L'aire honnête ne remplace JAMAIS la borne projetée du pavage.
    expect(pack.areaM2).toBeGreaterThan(0);
    expect(pack.usableAreaM2).toBeGreaterThan(0);
  });
});

describe('solveLivePitched — relais de l’aire VRAIE', () => {
  it('un pan sud en pente expose slopeAreaM2/usableSlopeAreaM2 > 0', () => {
    const res = solveLivePitched(squareRing(16), LAT, BILL, 30, 180, [], {});
    expect(res.slopeAreaM2).toBeGreaterThan(0);
    expect(res.usableSlopeAreaM2).toBeGreaterThan(0);
    // Pente non nulle → l'aire vraie dépasse l'aire projetée du pack gagnant.
    expect(res.slopeAreaM2).toBeCloseTo(res.winner.pack.slopeAreaM2, 6);
    expect(res.slopeAreaM2).toBeGreaterThan(res.winner.pack.areaM2);
  });
});
