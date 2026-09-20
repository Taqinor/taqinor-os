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

/**
 * PV61 — TYPE d'obstacle. Il ne change RIEN à la géométrie du rectangle : il pilote
 * seulement le DÉGAGEMENT laissé autour (une cheminée demande plus de recul qu'une
 * antenne). Les libellés FR et le dégagement de chaque type vivent dans
 * `scripts/roofPro11/types.ts` (OBSTACLE_TYPES / CLEARANCE_BY_TYPE) — ici on ne
 * déclare que l'union, pour que la lib pure reste sans dépendance vers les scripts.
 */
export type ObstacleType = 'cheminee' | 'ventilation' | 'chien_assis' | 'edicule' | 'antenne' | 'autre';

/**
 * CAL72 — d'où vient cet obstacle. DEUX vocabulaires coexistent dans le dépôt et les DEUX
 * sont valides ici : `core.calepinage.types.Provenance` dit RELEVE/RELEVE_DOUTEUX,
 * `apps.ao.models.ObstacleAO.Provenance` dit MESURE/MESURE_DOUTEUX — ce sont les MÊMES
 * états (RELEVE ≡ MESURE, RELEVE_DOUTEUX ≡ MESURE_DOUTEUX). Le moteur (`core/calepinage/
 * obstacles.py`) refuse d'engager un compte reposant sur PLAN ou DEVINE.
 */
export type ObstacleProvenance =
  | 'RELEVE'
  | 'MESURE'
  | 'RELEVE_DOUTEUX'
  | 'MESURE_DOUTEUX'
  | 'PLAN'
  | 'DEVINE'
  | 'DECLARE_CLIENT'
  | 'ECARTE';

/** CAL72 — provenances qui rendent un compte NON engageable (miroir de
 *  `core/calepinage/obstacles.py`, cf. NON_ENGAGEABLE_PROVENANCES ci-dessous). */
export const NON_ENGAGEABLE_PROVENANCES: readonly ObstacleProvenance[] = ['PLAN', 'DEVINE'];

/** true si la provenance rend le compte NON engageable (PLAN/DEVINE). Une provenance
 *  absente n'est PAS bloquante (comportement historique — aucune provenance saisie ne
 *  doit jamais bloquer un devis qui passait hier). */
export function isNonEngageable(provenance?: ObstacleProvenance | null): boolean {
  return !!provenance && NON_ENGAGEABLE_PROVENANCES.includes(provenance);
}

export interface Obstacle {
  id: string;
  centerLng: number;
  centerLat: number;
  /** Étendue nord-sud (m). */
  lengthM: number;
  /** Étendue est-ouest (m). */
  widthM: number;
  /** PV61 — type d'obstacle (dégagement associé). Absent → dégagement par défaut. */
  type?: ObstacleType;
  /** CAL66 — hauteur SAISIE (m) de l'obstacle. Absent = obstacle PLAN, qui ne porte
   *  aucune ombre (comportement historique). Aucun défaut n'est inventé. */
  heightM?: number;
  /** CAL72 — d'où vient cet obstacle. Absent = comportement historique (aucun motif de
   *  non-engageabilité tiré de la provenance). */
  provenance?: ObstacleProvenance;
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

/** Bornes plancher/plafond d'une hauteur d'obstacle SAISIE (m) — mêmes ordres de grandeur
 *  que les dimensions au sol (OBSTACLE_MIN_DIM_M / OBSTACLE_MAX_DIM_M). */
export const OBSTACLE_MIN_HEIGHT_M = 0.1;
export const OBSTACLE_MAX_HEIGHT_M = 30;

/**
 * CAL66 — applique une hauteur SAISIE (m), bornée. `null`/`undefined`/non fini ⇒ EFFACE la
 * hauteur (retour à « obstacle plan », comportement historique) : contrairement à
 * `clampDim`, on ne remplace jamais une saisie vide par un plancher — une hauteur non
 * renseignée reste NON renseignée, jamais une valeur inventée.
 */
export function withHeight(o: Obstacle, heightM: number | null | undefined): Obstacle {
  if (heightM == null || !Number.isFinite(heightM) || heightM <= 0) {
    const { heightM: _drop, ...rest } = o;
    return rest;
  }
  return { ...o, heightM: Math.max(OBSTACLE_MIN_HEIGHT_M, Math.min(OBSTACLE_MAX_HEIGHT_M, heightM)) };
}

/** CAL72 — applique (ou efface, `null`) la provenance d'un obstacle. */
export function withProvenance(o: Obstacle, provenance: ObstacleProvenance | null | undefined): Obstacle {
  if (!provenance) {
    const { provenance: _drop, ...rest } = o;
    return rest;
  }
  return { ...o, provenance };
}

/**
 * CAL73 — duplique un obstacle : copie dimensions + type + hauteur + provenance de
 * l'original (« insupportable de tout redessiner sur une halle à 40 lanterneaux
 * identiques »), posée à un NOUVEAU centre avec un NOUVEL id (jamais deux obstacles avec
 * le même id). La provenance survit — un lanterneau dupliqué depuis un original MESURÉ
 * est lui-même MESURÉ, pas une supposition nouvelle.
 */
export function duplicatedObstacle(o: Obstacle, id: string, center: LngLat): Obstacle {
  return { ...o, id, centerLng: center[0], centerLat: center[1] };
}

/**
 * CAL73 — positions (lng/lat) d'une TRAME régulière de `cols` × `rows` copies, au pas
 * SAISI par l'utilisateur (`spacingM`, mètres, appliqué EST-OUEST et NORD-SUD), centrée
 * sur `origin`. `cols`/`rows` ≤ 0 ou `spacingM` non fini/≤ 0 ⇒ []. Aucune détection
 * automatique par vision (explicitement hors périmètre) : le pas est TOUJOURS une saisie.
 */
export function gridPositions(origin: LngLat, spacingM: number, cols: number, rows: number): LngLat[] {
  if (!Number.isFinite(spacingM) || spacingM <= 0) return [];
  if (!Number.isInteger(cols) || !Number.isInteger(rows) || cols <= 0 || rows <= 0) return [];
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  const dLng = spacingM / (DEG2M * cosLat);
  const dLat = spacingM / DEG2M;
  const out: LngLat[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      out.push([origin[0] + (c - (cols - 1) / 2) * dLng, origin[1] + (r - (rows - 1) / 2) * dLat]);
    }
  }
  return out;
}

/** CAL66 — obstruction d'ombrage en ENU (mètres autour d'une origine). Forme IDENTIQUE à
 *  `ShadeObstructionENU` de `shadingEngine.ts` ; redéclarée ici pour que la lib PURE des
 *  obstacles reste sans dépendance de module (seule sa FORME est partagée). */
export interface ObstacleShadeEntry {
  x: number;
  y: number;
  effHeightM: number;
  halfWidthM: number;
  /** CAL94 — empreinte au sol RÉELLE en ENU (le rectangle SAISI), pour que l'occultation
   *  soit calculée par lancer de rayon sur la vraie forme et non sur un cône. */
  footprint: [number, number][];
}

/**
 * CAL66 — convertit les obstacles de TOITURE en obstructions ENU prêtes pour le moteur
 * d'ombrage (`isSunBlocked` / `hourlyShadeFactors` / `pointSolarAccess`), exactement
 * comme `shadeObstructionsENU` le fait pour les ombres tracées et
 * `environmentShadeEntries` pour les objets d'environnement.
 *
 * DEUX règles d'honnêteté :
 *  - un obstacle SANS `heightM` saisie est ÉCARTÉ : sans hauteur il reste un obstacle
 *    PLAN (simple zone d'exclusion) et ne porte AUCUNE ombre — comportement strictement
 *    identique à celui d'avant CAL66, jamais une hauteur inventée ;
 *  - la hauteur d'un obstacle de toiture est DÉJÀ mesurée au-dessus du plan du toit (une
 *    cheminée de 1,2 m dépasse de 1,2 m la dalle où sont posés les modules) : on ne lui
 *    retranche donc PAS la hauteur du bâtiment, contrairement aux obstructions
 *    extérieures qui, elles, sont référencées au SOL.
 *
 * La demi-largeur du cône d'occultation est la demi-diagonale du rectangle SAISI
 * (√(L² + l²) / 2) : elle ne vient que des dimensions renseignées par l'utilisateur,
 * aucune valeur par défaut n'est introduite.
 */
export function roofObstacleShadeEntries(
  list: readonly Obstacle[] | null | undefined,
  origin: LngLat,
): ObstacleShadeEntry[] {
  if (!Array.isArray(list) || !list.length) return [];
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  const out: ObstacleShadeEntry[] = [];
  for (const o of list) {
    const h = o.heightM;
    if (typeof h !== 'number' || !Number.isFinite(h) || h <= 0) continue;
    const halfWidthM = Math.hypot(o.lengthM, o.widthM) / 2;
    const x = (o.centerLng - origin[0]) * DEG2M * cosLat;
    const y = (o.centerLat - origin[1]) * DEG2M;
    // CAL94 — le rectangle SAISI en ENU : demi-largeur EST-OUEST = widthM/2, demi-longueur
    // NORD-SUD = lengthM/2 (mêmes conventions que `obstacleRing`).
    const hw = o.widthM / 2;
    const hl = o.lengthM / 2;
    out.push({
      x,
      y,
      effHeightM: h,
      halfWidthM: halfWidthM > 0 ? halfWidthM : OBSTACLE_MIN_DIM_M / 2,
      footprint: [
        [x - hw, y - hl],
        [x + hw, y - hl],
        [x + hw, y + hl],
        [x - hw, y + hl],
      ],
    });
  }
  return out;
}
