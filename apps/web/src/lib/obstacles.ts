/**
 * Géométrie PURE des obstacles de toiture (cheminée, climatiseur, lanterneau,
 * bâche, évent…) marqués par le visiteur sur l'estimateur piloté par la facture
 * (preview privé /preview/toiture-3d-pro-3).
 *
 * Un obstacle est une zone d'exclusion : on n'y pose pas de panneaux. On le
 * stocke par CENTRE (lng/lat) + dimensions réelles (longueur N-S, largeur E-O,
 * en mètres), sans rotation (v1). Ce module ne fait que de la géométrie : il
 * convertit centre+dimensions ⇆ rectangle lng/lat et mesure un rectangle tracé.
 * Le « cerveau » (estimatorBrain.ts) reçoit ensuite ces rectangles comme
 * obstructions et en déduit la surface utile et le calepinage.
 *
 * Aucune dépendance, aucun DOM, aucune carte → testé (tests/obstacles.test.ts).
 * La colle carte/tracé/édition vit dans src/scripts/roof-tool-pro3.ts.
 */
import type { LngLat } from './roof';

const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;

/** Dimensions plancher/plafond d'un obstacle marqué (m). */
export const OBSTACLE_MIN_DIM_M = 0.5;
export const OBSTACLE_MAX_DIM_M = 30;
/** Taille par défaut d'un obstacle créé d'un simple tap (m). */
export const OBSTACLE_DEFAULT_DIM_M = 2;
/** Facteur d'agrandissement/réduction uniforme des boutons + / − . */
export const OBSTACLE_STEP_FACTOR = 1.2;

export interface Obstacle {
  id: string;
  centerLng: number;
  centerLat: number;
  /** Étendue nord-sud (m). */
  lengthM: number;
  /** Étendue est-ouest (m). */
  widthM: number;
}

/** Borne une dimension dans [MIN, MAX] ; toute valeur non finie → MIN. */
export function clampDim(m: number): number {
  if (!Number.isFinite(m) || m <= 0) return OBSTACLE_MIN_DIM_M;
  return Math.max(OBSTACLE_MIN_DIM_M, Math.min(OBSTACLE_MAX_DIM_M, m));
}

/**
 * Rectangle aligné nord-sud/est-ouest (4 sommets lng/lat, sens trigonométrique)
 * pour un obstacle. `lengthM` = côté nord-sud, `widthM` = côté est-ouest.
 */
export function obstacleRing(o: Obstacle): LngLat[] {
  const cosLat = Math.max(1e-6, Math.cos(o.centerLat * DEG2RAD));
  const dLat = o.lengthM / 2 / DEG2M;
  const dLng = o.widthM / 2 / (DEG2M * cosLat);
  return [
    [o.centerLng - dLng, o.centerLat - dLat],
    [o.centerLng + dLng, o.centerLat - dLat],
    [o.centerLng + dLng, o.centerLat + dLat],
    [o.centerLng - dLng, o.centerLat + dLat],
  ];
}

/**
 * Dimensions réelles (m) d'un rectangle d'obstacle tracé (sommets lng/lat).
 * Même projection que le reste de l'estimateur : largeur E-O corrigée du cosinus
 * de la latitude médiane, longueur N-S directe.
 */
export function ringDimsM(ring: LngLat[]): { lengthM: number; widthM: number } {
  if (!Array.isArray(ring) || ring.length < 3) return { lengthM: 0, widthM: 0 };
  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  for (const [lng, lat] of ring) {
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  const midLat = (minLat + maxLat) / 2;
  const widthM = (maxLng - minLng) * DEG2M * Math.cos(midLat * DEG2RAD);
  const lengthM = (maxLat - minLat) * DEG2M;
  return { lengthM, widthM };
}

/**
 * Construit un obstacle depuis deux coins de glissé (lng/lat). Le centre est le
 * milieu des deux coins ; les dimensions sont mesurées puis bornées (un glissé
 * minuscule devient le carré minimal autour de ce centre).
 */
export function obstacleFromDrag(id: string, a: LngLat, b: LngLat): Obstacle {
  const centerLng = (a[0] + b[0]) / 2;
  const centerLat = (a[1] + b[1]) / 2;
  const ring: LngLat[] = [a, [b[0], a[1]], b, [a[0], b[1]]];
  const { lengthM, widthM } = ringDimsM(ring);
  return { id, centerLng, centerLat, lengthM: clampDim(lengthM), widthM: clampDim(widthM) };
}

/** Obstacle par défaut (carré) centré sur un point — pour un simple tap. */
export function defaultObstacle(id: string, center: LngLat): Obstacle {
  return {
    id,
    centerLng: center[0],
    centerLat: center[1],
    lengthM: OBSTACLE_DEFAULT_DIM_M,
    widthM: OBSTACLE_DEFAULT_DIM_M,
  };
}

/** Agrandit/réduit UNIFORMÉMENT un obstacle (centre conservé, dimensions bornées). */
export function scaledObstacle(o: Obstacle, factor: number): Obstacle {
  return { ...o, lengthM: clampDim(o.lengthM * factor), widthM: clampDim(o.widthM * factor) };
}

/** Redimensionne un obstacle aux longueur/largeur saisies (centre conservé, bornées). */
export function resizedObstacle(o: Obstacle, lengthM: number, widthM: number): Obstacle {
  return { ...o, lengthM: clampDim(lengthM), widthM: clampDim(widthM) };
}
