// ACAL501 — objet d'environnement « ligne » (haie, mur) : une polyligne SAISIE, de hauteur et
// d'épaisseur SAISIES, posée au sol. PUR (aucun DOM) : chaque segment devient un prisme
// rectangulaire (longueur du segment × épaisseur) pour le même lancer de rayon que les autres
// objets (`ShadeObstructionENU.footprint`). Sans épaisseur : aucune ombre, jamais une épaisseur
// de repli. Le câble aérien n'est PAS modélisé (il n'occulte pas sous sa hauteur).
import { type LngLat } from '../../lib/roof';
import { type ShadeObstructionENU } from '../../lib/shadingEngine';
import { WGS84_RADIUS } from '../../lib/geo';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * WGS84_RADIUS;
type XY = [number, number];

/** Au moins deux points finis. */
export function traceValide(t: unknown): t is LngLat[] {
  return Array.isArray(t) && t.length >= 2 && t.every((p) => Array.isArray(p) && p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]));
}

/** Le centre CALCULÉ d'une trace : milieu de son emprise (jamais saisi). */
export function centreDeTrace(trace: readonly LngLat[]): LngLat {
  const lngs = trace.map((p) => p[0]);
  const lats = trace.map((p) => p[1]);
  return [(Math.min(...lngs) + Math.max(...lngs)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2];
}

/** Rectangle (ENU, m) d'un segment a→b d'épaisseur `epaisseurM`, ou null (segment nul). */
export function anneauLigne(a: XY, b: XY, epaisseurM: number): XY[] | null {
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  const l = Math.hypot(dx, dy);
  if (l < 1e-9 || !(epaisseurM > 0)) return null;
  const [nx, ny] = [(-dy / l) * (epaisseurM / 2), (dx / l) * (epaisseurM / 2)];
  return [[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]];
}

/** Une entrée d'ombre par segment (empreinte = longueur × épaisseur) ; rien sans épaisseur. */
export function entreesOmbreLigne(trace: unknown, epaisseurM: unknown, effHeightM: number, origin: LngLat): ShadeObstructionENU[] {
  if (!traceValide(trace) || typeof epaisseurM !== 'number' || !(epaisseurM > 0) || !(effHeightM > 0)) return [];
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  const enu = trace.map(([lng, lat]): XY => [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M]);
  const out: ShadeObstructionENU[] = [];
  for (let i = 1; i < enu.length; i++) {
    const footprint = anneauLigne(enu[i - 1], enu[i], epaisseurM);
    if (!footprint) continue;
    const [x, y] = [(enu[i - 1][0] + enu[i][0]) / 2, (enu[i - 1][1] + enu[i][1]) / 2];
    const halfWidthM = Math.hypot(Math.hypot(enu[i][0] - enu[i - 1][0], enu[i][1] - enu[i - 1][1]) / 2, epaisseurM / 2);
    out.push({ x, y, effHeightM, halfWidthM, footprint });
  }
  return out;
}
