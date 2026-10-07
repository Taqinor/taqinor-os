/**
 * Source UNIQUE des constantes de projection côté écran (ACAL349).
 * Sphère WGS84 R = 6 378 137 m — même convention que core/calepinage/geo.py (D08-T44).
 * Aucune autre copie littérale de 6378137 / 111320 n'est admise dans apps/web
 * (gardé par lib/roof.projection.test.ts).
 */
export const WGS84_RADIUS = 6378137;
export const DEG2RAD_GEO = Math.PI / 180;
/** Mètres par degré de latitude sur la sphère WGS84 (≈ 111 319,49). */
export const DEG2M_GEO = DEG2RAD_GEO * WGS84_RADIUS;

/** Mètres par degré de latitude et de longitude à la latitude `latDeg`. */
export function metresParDegre(latDeg: number): { lat: number; lng: number } {
  return { lat: DEG2M_GEO, lng: DEG2M_GEO * Math.cos(latDeg * DEG2RAD_GEO) };
}
