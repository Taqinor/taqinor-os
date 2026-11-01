/**
 * Primitives de pavage partagées par roofPro.ts et roofPro2.ts (projection locale ENU,
 * bornes (u,v), pavage en rangées). Extraites telles quelles de ces deux fichiers
 * (dette « duplicats littéraux ») : même arithmétique, mêmes constantes, même ordre.
 */
import type { LngLat } from './roof';
import { WGS84_RADIUS } from './geo';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * WGS84_RADIUS;

/** Centroïde (moyenne des sommets) d'un tracé lng/lat. */
export function centroidLngLat(ring: LngLat[]): [number, number] {
  let olng = 0;
  let olat = 0;
  for (const [lng, lat] of ring) {
    olng += lng;
    olat += lat;
  }
  olng /= ring.length;
  olat /= ring.length;
  return [olng, olat];
}

/** Projection équirectangulaire locale, origine = centroïde du tracé. */
export function projectRingENU(ring: LngLat[]): {
  olng: number;
  olat: number;
  toENU: (pt: LngLat) => [number, number];
  ringENU: [number, number][];
} {
  const [olng, olat] = centroidLngLat(ring);
  const cosLat = Math.cos(olat * DEG2RAD);
  const toENU = ([lng, lat]: LngLat): [number, number] => [
    (lng - olng) * DEG2M * cosLat,
    (lat - olat) * DEG2M,
  ];
  return { olng, olat, toENU, ringENU: ring.map(toENU) };
}

/** Bornes d'un tracé déjà exprimé en (u,v). */
export function uvBounds(ringUV: [number, number][]): { uMin: number; uMax: number; vMin: number; vMax: number } {
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [uu, vv] of ringUV) {
    if (uu < uMin) uMin = uu;
    if (uu > uMax) uMax = uu;
    if (vv < vMin) vMin = vv;
    if (vv > vMax) vMax = vv;
  }
  return { uMin, uMax, vMin, vMax };
}

/** Bornes (u,v) du tracé dans le repère des rangées (u = axe des rangées, s = pente). */
export function ringUVBounds(
  ringENU: [number, number][],
  u: [number, number],
  s: [number, number],
): { uMin: number; uMax: number; vMin: number; vMax: number } {
  return uvBounds(ringENU.map(([x, y]) => [x * u[0] + y * u[1], x * s[0] + y * s[1]] as [number, number]));
}

/** Conversion (u,v) → ENU pour le repère des rangées. */
export function uvToENU(u: [number, number], s: [number, number]): (uu: number, vv: number) => [number, number] {
  return (uu, vv) => [uu * u[0] + vv * s[0], uu * u[1] + vv * s[1]];
}

/** Pavage en rangées/colonnes ; `ok` valide les 4 coins d'un panneau. */
export function paverRangees(p: {
  rows: number;
  cols: number;
  uMin: number;
  vMin: number;
  vMax: number;
  setbackM: number;
  rowPitch: number;
  colPitch: number;
  alongRow: number;
  depthFootprint: number;
  toENUfromUV: (uu: number, vv: number) => [number, number];
  ok: (corners: [number, number][]) => boolean;
}): { cx: number; cy: number }[] {
  const { rows, cols, uMin, vMin, vMax, setbackM, rowPitch, colPitch, alongRow, depthFootprint, toENUfromUV, ok } = p;
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < rows; r++) {
    const v0 = vMin + setbackM + r * rowPitch;
    const v1 = v0 + depthFootprint;
    if (v1 > vMax - setbackM + 1e-6) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uMin + setbackM + c * colPitch;
      const u1 = u0 + alongRow;
      const corners: [number, number][] = [
        toENUfromUV(u0, v0),
        toENUfromUV(u1, v0),
        toENUfromUV(u1, v1),
        toENUfromUV(u0, v1),
      ];
      if (!ok(corners)) continue;
      const center = toENUfromUV(u0 + alongRow / 2, v0 + depthFootprint / 2);
      panels.push({ cx: center[0], cy: center[1] });
    }
  }
  return panels;
}
