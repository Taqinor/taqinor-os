// Calepinage « pro » (rangées de panneaux inclinés espacés) — src/lib/roofPro.ts.
// On vérifie : un nombre de panneaux réaliste et JAMAIS supérieur au calepinage
// collé à plat (roof.ts), des panneaux bien à l'intérieur du tracé, kWc cohérent,
// et la pose affleurante (toit en pente) plus dense que la pose inclinée espacée.
import { describe, expect, it } from 'vitest';
import { layoutProRows, PANEL_TILT_DEG, ROW_GAP_RISE_FACTOR } from '../src/lib/roofPro';
import { layoutPanels, pointInPolygon, geodesicAreaM2, type LngLat } from '../src/lib/roof';

// Carré de `side` mètres centré sur (lng0, lat0).
function squareRing(side: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

describe('layoutProRows — rangées inclinées espacées', () => {
  it('dispose un nombre réaliste de panneaux sur un grand toit', () => {
    const ring = squareRing(24);
    const layout = layoutProRows(ring, 'sud');
    expect(layout.count).toBeGreaterThan(20);
    expect(layout.kwc).toBeCloseTo(layout.count * 0.55, 5); // 550 Wc/panneau
    expect(layout.areaM2).toBeGreaterThan(500); // ~576 m²
    expect(layout.tiltRad).toBeCloseTo((PANEL_TILT_DEG * Math.PI) / 180, 6);
    expect(layout.origin).toHaveLength(2);
    expect(layout.ringENU.length).toBe(4);
  });

  it('compte MOINS que le calepinage collé à plat (rangées = jeux → plus juste)', () => {
    const ring = squareRing(24);
    const pro = layoutProRows(ring, 'sud');
    const flush = layoutPanels(ring); // roof.ts, panneaux collés
    expect(pro.count).toBeGreaterThan(0);
    expect(flush.count).toBeGreaterThan(0);
    expect(pro.count).toBeLessThan(flush.count);
  });

  it('tous les panneaux sont à l’intérieur du tracé', () => {
    const ring = squareRing(24);
    const layout = layoutProRows(ring, 'sud');
    for (const p of layout.panels) {
      expect(pointInPolygon([p.cx, p.cy], layout.ringENU)).toBe(true);
    }
  });

  it('l’aire correspond à roof.ts (réutilise geodesicAreaM2, non recodé)', () => {
    const ring = squareRing(20);
    expect(layoutProRows(ring, 'sud').areaM2).toBeCloseTo(geodesicAreaM2(ring), 6);
  });

  it('un tracé trop petit ou invalide → zéro panneau', () => {
    expect(layoutProRows(squareRing(2), 'sud').count).toBe(0);
    expect(layoutProRows([[0, 0], [1, 1]] as LngLat[], 'sud').count).toBe(0);
  });

  it('la pose affleurante (toit en pente) est plus dense que l’inclinée espacée', () => {
    const ring = squareRing(24);
    const tilted = layoutProRows(ring, 'sud'); // défaut : 12° + jeux
    const flush = layoutProRows(ring, 'sud', { tiltDeg: 18, rowGapFactor: 0 }); // affleurant
    expect(flush.count).toBeGreaterThanOrEqual(tilted.count);
  });

  it('le pas inter-rangées suit la règle = empreinte + facteur × hauteur projetée', () => {
    // Sanity : sur le même toit, augmenter le jeu réduit le nombre de rangées.
    const ring = squareRing(30);
    const tight = layoutProRows(ring, 'sud', { rowGapFactor: 0 });
    const loose = layoutProRows(ring, 'sud', { rowGapFactor: ROW_GAP_RISE_FACTOR + 2 });
    expect(loose.count).toBeLessThan(tight.count);
  });
});
