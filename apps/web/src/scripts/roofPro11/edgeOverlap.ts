/**
 * Recouvrement de deux arêtes ENU quasi-collinéaires : géométrie PURE (aucun Three, aucun
 * DOM), partagée par `scene3d.ts` (coloration 3D des segments) et `edges.ts` (déduction du
 * type d'arête) — ENF19 : c'était une COPIE volontaire pour qu'`edges.ts` n'importe pas
 * scene3d ; ce module sans dépendance rend la copie inutile. Mêmes tolérances que
 * roofAdjacency (1,5 m / 12° / 0,5 m).
 */

/** Longueur (m) du segment de RECOUVREMENT entre deux arêtes quasi-collinéaires/coïncidentes
 *  en ENU, ou 0 si elles ne sont pas une arête partagée (écart trop grand, angle trop large,
 *  recouvrement trop court). Mêmes tolérances que roofAdjacency (1,5 m / 12° / 0,5 m). */
export function enuSharedEdgeOverlapM(
  a1: [number, number],
  a2: [number, number],
  b1: [number, number],
  b2: [number, number],
): number {
  const MAX_GAP_M = 1.5;
  const MAX_ANGLE_DEG = 12;
  const MIN_OVERLAP_M = 0.5;
  const da: [number, number] = [a2[0] - a1[0], a2[1] - a1[1]];
  const db: [number, number] = [b2[0] - b1[0], b2[1] - b1[1]];
  const la = Math.hypot(da[0], da[1]);
  const lb = Math.hypot(db[0], db[1]);
  if (la <= 0 || lb <= 0) return 0;
  // Angle d'arête (non-orienté, mod 180°).
  const angA = Math.atan2(da[1], da[0]) * (180 / Math.PI);
  const angB = Math.atan2(db[1], db[0]) * (180 / Math.PI);
  let diff = Math.abs(angA - angB) % 180;
  if (diff > 90) diff = 180 - diff;
  if (diff > MAX_ANGLE_DEG) return 0;
  // Écart moyen point→segment (robuste aux longueurs différentes).
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
  // Recouvrement : projette les 4 extrémités sur la direction unitaire de l'arête A.
  const ux = da[0] / la;
  const uy = da[1] / la;
  const proj = (p: [number, number]): number => (p[0] - a1[0]) * ux + (p[1] - a1[1]) * uy;
  const lo2 = Math.min(proj(b1), proj(b2));
  const hi2 = Math.max(proj(b1), proj(b2));
  const overlap = Math.min(la, hi2) - Math.max(0, lo2);
  return overlap >= MIN_OVERLAP_M ? overlap : 0;
}
