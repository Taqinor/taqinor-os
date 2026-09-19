/**
 * CAL102 — outil de MESURE (distance cumulée, surface d'un polygone fermé, angle),
 * persistable comme annotation du calepinage.
 *
 * Constat : aucune règle de mesure n'existait dans l'atelier — les seules distances
 * affichées venaient d'un glissé en placement libre (FreeCheck.edgeM/panelM), rien pour
 * vérifier une cote sur l'image satellite elle-même. La GÉOMÉTRIE ci-dessous est PURE
 * (mêmes formules que `lib/roof.ts` geodesicAreaM2/geodesicPerimeterM — projection locale
 * équirectangulaire, échelle cos(latitude moyenne), rayon WGS84 : AUCUNE dimension
 * inventée) ; la couche UI en bas de fichier n'est qu'un pont vers `ctx.measurements`.
 */
import { geodesicAreaM2, type LngLat } from '../../lib/roof';
import { DEG2RAD, WGS84_RADIUS } from './constants';
import { type Ctx } from './context';

export type MeasureKind = 'distance' | 'area' | 'angle';

/** Une mesure posée : ses points (lng/lat, mêmes coordonnées que le tracé du toit), son
 *  genre, et la valeur calculée AU MOMENT de la pose (m pour distance/angle-support, m²
 *  pour surface, ° pour angle) — recalculable à tout instant depuis `points` via
 *  `measureValue`, jamais une valeur figée séparée de sa géométrie source. */
export interface Measurement {
  id: string;
  kind: MeasureKind;
  points: LngLat[];
  /** Libellé posé par l'utilisateur (optionnel — « côté sud », « toiture principale »…). */
  label?: string;
}

/** Distance géodésique (m) entre deux points lng/lat — même projection locale que
 *  `geodesicPerimeterM` (échelle cos(latitude moyenne), rayon WGS84). */
export function segmentDistanceM(a: LngLat, b: LngLat): number {
  const midLat = ((a[1] + b[1]) / 2) * DEG2RAD;
  const de = (b[0] - a[0]) * DEG2RAD * Math.cos(midLat) * WGS84_RADIUS;
  const dn = (b[1] - a[1]) * DEG2RAD * WGS84_RADIUS;
  return Math.hypot(de, dn);
}

/** Distance CUMULÉE (m) le long d'une polyligne ouverte (≥ 2 points) — somme des segments
 *  consécutifs, PAS une fermeture sur le premier point (à la différence d'une aire). */
export function cumulativeDistanceM(points: readonly LngLat[]): number {
  if (!Array.isArray(points) || points.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < points.length; i++) total += segmentDistanceM(points[i - 1], points[i]);
  return total;
}

/** Surface (m²) du polygone FERMÉ formé par ≥ 3 points — réutilise directement
 *  `geodesicAreaM2` (aucune formule dupliquée : la même aire que le tracé du toit
 *  utiliserait sur ce même contour). */
export function polygonAreaM2(points: readonly LngLat[]): number {
  return geodesicAreaM2([...points]);
}

/** Angle (°, 0–180) formé au sommet `points[1]` par les deux segments vers `points[0]` et
 *  `points[2]` — projection locale équirectangulaire (même repère que les distances
 *  ci-dessus), donc cohérent avec elles sur une même mesure. Nécessite exactement 3 points ;
 *  renvoie 0 si un segment est dégénéré (deux points confondus). */
export function vertexAngleDeg(points: readonly LngLat[]): number {
  if (!Array.isArray(points) || points.length !== 3) return 0;
  const origin = points[1];
  const toEnu = (p: LngLat): [number, number] => {
    const midLat = ((p[1] + origin[1]) / 2) * DEG2RAD;
    return [(p[0] - origin[0]) * DEG2RAD * Math.cos(midLat) * WGS84_RADIUS, (p[1] - origin[1]) * DEG2RAD * WGS84_RADIUS];
  };
  const [ax, ay] = toEnu(points[0]);
  const [bx, by] = toEnu(points[2]);
  const la = Math.hypot(ax, ay);
  const lb = Math.hypot(bx, by);
  if (la === 0 || lb === 0) return 0;
  const cos = Math.max(-1, Math.min(1, (ax * bx + ay * by) / (la * lb)));
  return (Math.acos(cos) * 180) / Math.PI;
}

/** Valeur calculée d'une mesure selon son genre — TOUJOURS dérivée de `points`, jamais une
 *  valeur séparée susceptible de diverger de la géométrie posée. */
export function measureValue(m: Pick<Measurement, 'kind' | 'points'>): number {
  switch (m.kind) {
    case 'distance':
      return cumulativeDistanceM(m.points);
    case 'area':
      return polygonAreaM2(m.points);
    case 'angle':
      return vertexAngleDeg(m.points);
    default:
      return 0;
  }
}

/** Une mesure est-elle GÉOMÉTRIQUEMENT VALIDE pour son genre (assez de points, genre
 *  reconnu) ? Distance ≥ 2 points, surface ≥ 3, angle exactement 3. */
export function isMeasureValid(m: Pick<Measurement, 'kind' | 'points'>): boolean {
  if (!Array.isArray(m.points)) return false;
  if (m.kind === 'distance') return m.points.length >= 2;
  if (m.kind === 'area') return m.points.length >= 3;
  if (m.kind === 'angle') return m.points.length === 3;
  return false;
}

/** Libellé FR lisible de la valeur d'une mesure. */
export function formatMeasure(m: Pick<Measurement, 'kind' | 'points'>): string {
  const v = measureValue(m);
  if (m.kind === 'area') return `${v.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} m²`;
  if (m.kind === 'angle') return `${Math.round(v)}°`;
  return `${v.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} m`;
}

// ═══════════ Couche UI — pont vers `ctx.measurements` (persistance du calepinage) ═══════════

export interface MesureUiDeps {
  /** Repeint la liste des mesures à l'écran (échafaudage `rp9-mesure-*`, optionnel). */
  render?: () => void;
}

export interface MesureUi {
  /** Mesures posées sur le pan ACTIF (lecture — copie, jamais la référence vivante). */
  list: () => Measurement[];
  /** Ajoute une mesure (genre + points). Refusée (renvoie null) si géométriquement
   *  invalide pour son genre — jamais posée à moitié. */
  add: (kind: MeasureKind, points: readonly LngLat[], label?: string) => Measurement | null;
  /** Retire une mesure par id. */
  remove: (id: string) => boolean;
  /** Vide toutes les mesures du pan actif. */
  clear: () => void;
}

let nextMeasureId = 0;
/** Générateur d'id STABLE dans une session (préfixe + compteur) — jamais Math.random() dans
 *  un module par ailleurs déterministe, mais unique tant que la page vit. */
function makeMeasureId(): string {
  nextMeasureId += 1;
  return `mes${nextMeasureId}`;
}

/** CAL102 — pont UI : `ctx.measurements` est le stockage (persisté avec le calepinage, cf.
 *  `types.ts`/`prefill.ts` pour le format de sauvegarde), ce module n'en est que la porte
 *  d'entrée contrôlée (jamais une mesure invalide posée). Optionnel côté `ctx` — un `ctx`
 *  antérieur à CAL102 n'en porte pas, jamais lu en aveugle. */
export function createMesureUi(ctx: Ctx, deps: MesureUiDeps = {}): MesureUi {
  function ensure(): Measurement[] {
    if (!Array.isArray(ctx.measurements)) ctx.measurements = [];
    return ctx.measurements;
  }
  function list(): Measurement[] {
    return ensure().map((m) => ({ ...m, points: m.points.map((p) => [p[0], p[1]] as LngLat) }));
  }
  function add(kind: MeasureKind, points: readonly LngLat[], label?: string): Measurement | null {
    const m: Measurement = { id: makeMeasureId(), kind, points: points.map((p) => [p[0], p[1]] as LngLat), label };
    if (!isMeasureValid(m)) return null;
    ensure().push(m);
    deps.render?.();
    return m;
  }
  function remove(id: string): boolean {
    const arr = ensure();
    const idx = arr.findIndex((m) => m.id === id);
    if (idx < 0) return false;
    arr.splice(idx, 1);
    deps.render?.();
    return true;
  }
  function clear() {
    ensure().length = 0;
    deps.render?.();
  }
  return { list, add, remove, clear };
}
