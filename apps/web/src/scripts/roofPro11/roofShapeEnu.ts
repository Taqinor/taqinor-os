// Nouveau fichier car : scene3d.ts est un fichier gelé (C20) — projection ENU et azimuts des pans générés (RoofShape), sortis tels quels.
import type { LngLat } from '../../lib/roof';
import { DEG2RAD, DEG2M } from './constants';

/** Projection ENU locale (mètres) autour d'une origine — même formule que partout ailleurs
 *  dans roofPro11 (freeMode.toEnu, estimatorBrainV2.roofDominantAzimuthDeg). */
export function shapeToEnu(pt: LngLat, origin: LngLat): [number, number] {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  return [(pt[0] - origin[0]) * DEG2M * cosLat, (pt[1] - origin[1]) * DEG2M];
}
export function shapeFromEnu(p: [number, number], origin: LngLat): LngLat {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  return [origin[0] + p[0] / (DEG2M * cosLat), origin[1] + p[1] / DEG2M];
}

/** Azimut (0=N, 90=E…) d'un vecteur ENU (E, N) — même convention que roofDominantAzimuthDeg. */
export function enuAzimuthDeg(de: number, dn: number): number {
  return (Math.atan2(de, dn) / DEG2RAD + 360) % 360;
}

/** Centre (moyenne des sommets, ENU) — suffit à déterminer le côté « extérieur » d'une
 *  arête sur un contour convexe (le cas visé : un pan de toit tracé est quasi convexe). */
export function enuVertexAverage(pts: [number, number][]): [number, number] {
  let sx = 0;
  let sy = 0;
  for (const [x, y] of pts) {
    sx += x;
    sy += y;
  }
  return [sx / pts.length, sy / pts.length];
}

/** Azimut de face sortant de l'arête (a→b), perpendiculaire à l'arête et pointant à
 *  l'opposé du centre du contour. */
export function outwardEdgeAzimuthDeg(a: [number, number], b: [number, number], center: [number, number]): number {
  const de = b[0] - a[0];
  const dn = b[1] - a[1];
  // Deux perpendiculaires possibles ; on garde celle qui s'éloigne du centre.
  const n1: [number, number] = [dn, -de];
  const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const toMid: [number, number] = [mid[0] - center[0], mid[1] - center[1]];
  const dot1 = n1[0] * toMid[0] + n1[1] * toMid[1];
  const outward: [number, number] = dot1 >= 0 ? n1 : [-n1[0], -n1[1]];
  return enuAzimuthDeg(outward[0], outward[1]);
}
