/**
 * CAL57 — types d'arête par segment de contour (faîtage / noue / arêtier / égout /
 * rive / inconnue). Géométrie PURE (aucun Three, aucun DOM) : le type est DÉDUIT du
 * tracé + du toit voisin, jamais saisi par défaut au hasard — et laissé « inconnue »
 * quand la déduction ne serait qu'une supposition (distinguer une noue d'un arêtier
 * demande de comparer la pente ET le sens de fruit des deux pans, pas seulement leur
 * adjacence ; on ne l'invente pas ici).
 *
 * Indépendant de scene3d.ts (pas d'import croisé) : scene3d colore les segments en 3D
 * en import ANT ce module, donc ce module ne doit rien importer de scene3d — la
 * tolérance de recouvrement d'arête (`edgeOverlapM`) est une COPIE volontaire de
 * `enuSharedEdgeOverlapM` (mêmes constantes : 1,5 m / 12° / 0,5 m), pas une réécriture.
 */
import { upSlopeCoord } from '../../lib/estimatorBrainV6';
import { type LngLat } from '../../lib/roof';
import { DEG2RAD, DEG2M } from './constants';
import { type RoofType } from './types';

export type EdgeType = 'faitage' | 'noue' | 'arretier' | 'egout' | 'rive' | 'inconnue';

export interface SerializedEdge {
  /** Rang du segment dans `vertices` : va de vertices[index] à vertices[index+1] (le
   *  dernier reboucle sur vertices[0]). */
  index: number;
  type: EdgeType;
  /** true quand un humain a corrigé le type déduit (réservé — aucune UI d'édition
   *  manuelle dans cette tâche ; le champ existe pour que le schéma v2 le porte). */
  manuel?: boolean;
}

/** Couleur d'affichage 3D par type d'arête (hex Three.js), pour distinguer faîtage/
 *  égout/inconnue d'un coup d'œil sur le contour. */
export const EDGE_COLOR_BY_TYPE: Record<EdgeType, number> = {
  faitage: 0xf3cc66, // or — faîtière
  noue: 0x6ab0ff, // bleu — noue (creux)
  arretier: 0xff9f5b, // orange — arêtier (saillant)
  egout: 0x8fd694, // vert — égout (bas de pente)
  rive: 0xc9cfe0, // gris clair — rive
  inconnue: 0x6b7280, // gris terne — non déduit
};

/** Un pan minimal pour la déduction d'arêtes (contour + toit + face). */
export interface EdgeDeductionZone {
  vertices: LngLat[];
  roofType: RoofType;
  facingAzimuthDeg: number;
}

/** Projection ENU (m) autour d'une origine — même formule que le reste de roofPro11. */
function ringToEnu(ring: LngLat[], origin: LngLat): [number, number][] {
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  return ring.map(([lng, lat]) => [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M]);
}

/** Longueur (m) du recouvrement entre deux segments ENU quasi-collinéaires/coïncidents,
 *  ou 0 s'ils ne sont pas une arête partagée. COPIE des tolérances de
 *  `scene3d.enuSharedEdgeOverlapM` (1,5 m / 12° / 0,5 m) — voir l'en-tête du fichier. */
function edgeOverlapM(a1: [number, number], a2: [number, number], b1: [number, number], b2: [number, number]): number {
  const MAX_GAP_M = 1.5;
  const MAX_ANGLE_DEG = 12;
  const MIN_OVERLAP_M = 0.5;
  const da: [number, number] = [a2[0] - a1[0], a2[1] - a1[1]];
  const db: [number, number] = [b2[0] - b1[0], b2[1] - b1[1]];
  const la = Math.hypot(da[0], da[1]);
  const lb = Math.hypot(db[0], db[1]);
  if (la <= 0 || lb <= 0) return 0;
  const angA = Math.atan2(da[1], da[0]) * (180 / Math.PI);
  const angB = Math.atan2(db[1], db[0]) * (180 / Math.PI);
  let diff = Math.abs(angA - angB) % 180;
  if (diff > 90) diff = 180 - diff;
  if (diff > MAX_ANGLE_DEG) return 0;
  const distPS = (p: [number, number], s: [number, number], e: [number, number]): number => {
    const se: [number, number] = [e[0] - s[0], e[1] - s[1]];
    const len2 = se[0] * se[0] + se[1] * se[1];
    if (len2 === 0) return Math.hypot(p[0] - s[0], p[1] - s[1]);
    let t = ((p[0] - s[0]) * se[0] + (p[1] - s[1]) * se[1]) / len2;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(p[0] - (s[0] + se[0] * t), p[1] - (s[1] + se[1] * t));
  };
  const gap = (distPS(b1, a1, a2) + distPS(b2, a1, a2) + distPS(a1, b1, b2) + distPS(a2, b1, b2)) / 4;
  if (gap > MAX_GAP_M) return 0;
  const ux = da[0] / la;
  const uy = da[1] / la;
  const proj = (p: [number, number]): number => (p[0] - a1[0]) * ux + (p[1] - a1[1]) * uy;
  const lo2 = Math.min(proj(b1), proj(b2));
  const hi2 = Math.max(proj(b1), proj(b2));
  const overlap = Math.min(la, hi2) - Math.max(0, lo2);
  return overlap >= MIN_OVERLAP_M ? overlap : 0;
}

/**
 * CAL57 — déduit le type de chaque segment du contour d'un pan :
 *  - toit PLAT : aucun concept de faîtière/égout n'existe → tous les segments sont
 *    des rives (fait géométrique, pas une supposition) ;
 *  - toit en PENTE : un segment partagé avec un pan en pente ADJACENT (même test
 *    d'adjacence que `computeRidgeLifts`, qui suppose déjà un groupe connecté = une
 *    faîtière commune) devient 'faitage' ; parmi les segments restants, celui dont la
 *    coordonnée amont-aval moyenne est la plus BASSE (le plus en aval de la pente) est
 *    l'égout — fait géométrique déduit de la pente saisie, pas une invention ; tout le
 *    reste reste 'inconnue' (distinguer une rive d'une noue/arêtier demanderait de
 *    comparer le fruit du pan voisin, non disponible ici).
 * Renvoie [] pour un contour < 3 sommets (rien à typer).
 */
export function deduceEdgeTypes(zone: EdgeDeductionZone, others: readonly EdgeDeductionZone[]): SerializedEdge[] {
  const ring = zone.vertices;
  const n = ring.length;
  if (n < 3) return [];
  if (zone.roofType !== 'pitched') {
    return ring.map((_, i) => ({ index: i, type: 'rive' as const }));
  }
  const origin = ring[0];
  const enu = ringToEnu(ring, origin);
  const shared = new Array<boolean>(n).fill(false);
  for (const other of others) {
    if (other.roofType !== 'pitched' || other.vertices.length < 3) continue;
    const otherEnu = ringToEnu(other.vertices, origin);
    for (let i = 0; i < n; i++) {
      const a1 = enu[i];
      const a2 = enu[(i + 1) % n];
      for (let j = 0; j < otherEnu.length; j++) {
        const b1 = otherEnu[j];
        const b2 = otherEnu[(j + 1) % otherEnu.length];
        if (edgeOverlapM(a1, a2, b1, b2) > 0) {
          shared[i] = true;
          break;
        }
      }
    }
  }
  let egoutIdx = -1;
  let minUp = Infinity;
  for (let i = 0; i < n; i++) {
    if (shared[i]) continue;
    const [x1, y1] = enu[i];
    const [x2, y2] = enu[(i + 1) % n];
    const uMid = (upSlopeCoord(x1, y1, zone.facingAzimuthDeg) + upSlopeCoord(x2, y2, zone.facingAzimuthDeg)) / 2;
    if (uMid < minUp) {
      minUp = uMid;
      egoutIdx = i;
    }
  }
  return ring.map((_, i) => {
    if (shared[i]) return { index: i, type: 'faitage' as const };
    if (i === egoutIdx) return { index: i, type: 'egout' as const };
    return { index: i, type: 'inconnue' as const };
  });
}
