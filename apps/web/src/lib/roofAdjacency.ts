/**
 * Adjacence des pans de toiture + inférence d'azimut de façade (lib PURE).
 *
 * MÉTHODE
 * -------
 * Le constructeur 3D de toit laisse l'utilisateur tracer plusieurs « zones »
 * (anneaux de points [lng, lat]). Quand on ajoute un SECOND pan connecté sur un
 * toit en pente, chaque pan ne doit PAS retomber sur le sud (180°) par défaut :
 * les deux pans doivent se rejoindre sur une faîtière commune. Ce module, à
 * partir des anneaux tracés, trouve l'arête PARTAGÉE (ou la plus proche) entre
 * deux zones adjacentes et en déduit un `facingAzimuthDeg` cohérent :
 *
 *   • PIGNON / GABLE (deux pans)        → les pans regardent À L'OPPOSÉ de la
 *     faîtière partagée : azimuts opposés (~180° d'écart), chacun normal à
 *     l'arête partagée et orienté vers l'extérieur (loin du centroïde du pan).
 *   • CONTINUATION / MONO-PENTE         → même direction de pente que le voisin :
 *     le nouveau pan COPIE le `facingAzimuthDeg` du voisin.
 *
 * On distingue pignon vs mono-pente par la géométrie : si les deux centroïdes
 * de zone sont de PART ET D'AUTRE de l'arête partagée → pignon ; s'ils sont du
 * MÊME côté (extension collinéaire / continuation du plan) → mono-pente.
 *
 * Si aucune arête partagée/proche n'est trouvée, on renvoie `connected:false`
 * et le repli sud (180°) : l'appelant laisse alors l'utilisateur choisir.
 *
 * CONVENTION D'AZIMUT
 * -------------------
 * Degrés horaires depuis le NORD : 0 = Nord, 90 = Est, 180 = Sud, 270 = Ouest
 * (identique à roofPro2.ts). Le `facingAzimuthDeg` est la direction VERS LE BAS
 * de la pente (là où regarde le pan). Toujours normalisé dans [0, 360).
 *
 * PROJECTION
 * ----------
 * Les arêtes lng/lat sont converties en mètres locaux (mise à l'échelle de la
 * longitude par cos(lat)) pour calculer correctement caps/normales/distances —
 * même approche equirectangulaire locale que roof.ts / roofPro2.ts.
 *
 * Aucune dépendance, aucun DOM, aucune carte, aucun Three.js → testé
 * unitairement (tests/roofAdjacency.test.ts). Numbers in, numbers out.
 */

/** Coordonnée [longitude, latitude] (ordre GeoJSON), comme roof.ts. */
export type LngLat = [number, number];

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;
const WGS84_RADIUS = 6378137; // m
const DEG2M = DEG2RAD * WGS84_RADIUS; // mètres par degré (axe nord/sud)

/** Azimut de repli (plein sud) quand aucune adjacence n'est trouvée. */
export const FALLBACK_FACING_DEG = 180;

/** Arête partagée (ou la plus proche) entre deux zones, en lng/lat. */
export interface SharedEdge {
  /** Premier sommet de l'arête (coordonnée [lng, lat]). */
  p1: LngLat;
  /** Second sommet de l'arête (coordonnée [lng, lat]). */
  p2: LngLat;
  /** Longueur de l'arête en mètres. */
  lengthM: number;
}

/** Résultat de l'inférence d'adjacence/façade pour une zone. */
export interface AdjacencyResult {
  /** Une arête partagée/proche a-t-elle été trouvée ? */
  connected: boolean;
  /** Confiance de l'inférence dans [0, 1]. */
  confidence: number;
  /** Azimut de façade inféré pour la zone interrogée (repli 180° = sud). */
  facingAzimuthDeg: number;
  /** L'arête partagée détectée, ou null si non connecté. */
  sharedEdge: SharedEdge | null;
  /** Type d'adjacence détecté : pignon, mono-pente, ou aucun. */
  kind: AdjacencyKind;
}

/** Nature géométrique de l'adjacence détectée. */
export type AdjacencyKind = 'gable' | 'mono-pente' | 'none';

/** Options de tolérance pour la détection d'arête partagée. */
export interface AdjacencyOptions {
  /**
   * Distance maximale (mètres) entre les deux arêtes pour les considérer
   * coïncidentes. Défaut 1,5 m (tracé satellite imprécis).
   */
  maxGapM?: number;
  /**
   * Écart d'orientation maximal (degrés) pour considérer deux arêtes
   * quasi-collinéaires (en valeur absolue, modulo 180°). Défaut 12°.
   */
  maxAngleDeg?: number;
  /**
   * Longueur de recouvrement minimale (mètres) requise sur l'arête partagée.
   * Défaut 0,5 m — évite de coller deux zones qui ne se touchent qu'en un coin.
   */
  minOverlapM?: number;
}

const DEFAULTS: Required<AdjacencyOptions> = {
  maxGapM: 1.5,
  maxAngleDeg: 12,
  minOverlapM: 0.5,
};

// ————————————————————————————————————————————————————————————————
// Helpers géométriques (plan local en mètres)
// ————————————————————————————————————————————————————————————————

type Vec2 = [number, number];

/** Normalise un azimut en degrés dans [0, 360). */
export function normalizeAzimuthDeg(deg: number): number {
  if (!Number.isFinite(deg)) return FALLBACK_FACING_DEG;
  let a = deg % 360;
  if (a < 0) a += 360;
  // Évite -0 et la valeur 360 exacte issue de l'arrondi.
  if (a === 360) a = 0;
  return a;
}

/** Centroïde lng/lat (moyenne des sommets) d'un anneau. */
function centroidLngLat(ring: LngLat[]): LngLat {
  let lng = 0;
  let lat = 0;
  for (const [x, y] of ring) {
    lng += x;
    lat += y;
  }
  return [lng / ring.length, lat / ring.length];
}

/**
 * Projette une coordonnée lng/lat en mètres locaux (origine + cos(lat) sur la
 * longitude) — même projection equirectangulaire locale que roof.ts.
 */
function makeProjector(originLng: number, originLat: number): (p: LngLat) => Vec2 {
  const cosLat = Math.cos(originLat * DEG2RAD);
  return ([lng, lat]: LngLat): Vec2 => [
    (lng - originLng) * DEG2M * cosLat,
    (lat - originLat) * DEG2M,
  ];
}

function sub(a: Vec2, b: Vec2): Vec2 {
  return [a[0] - b[0], a[1] - b[1]];
}

function add(a: Vec2, b: Vec2): Vec2 {
  return [a[0] + b[0], a[1] + b[1]];
}

function scale(a: Vec2, k: number): Vec2 {
  return [a[0] * k, a[1] * k];
}

function dot(a: Vec2, b: Vec2): number {
  return a[0] * b[0] + a[1] * b[1];
}

function len(a: Vec2): number {
  return Math.hypot(a[0], a[1]);
}

/** Distance d'un point au segment [a, b] (plan métrique). */
function distPointSegment(p: Vec2, a: Vec2, b: Vec2): number {
  const ab = sub(b, a);
  const len2 = dot(ab, ab);
  if (len2 === 0) return len(sub(p, a));
  let t = dot(sub(p, a), ab) / len2;
  t = Math.max(0, Math.min(1, t));
  return len(sub(p, add(a, scale(ab, t))));
}

/**
 * Cap (azimut, degrés depuis le nord) d'un vecteur métrique local
 * (x = est, y = nord). atan2(est, nord) = angle horaire depuis le nord.
 */
function vecToAzimuthDeg(v: Vec2): number {
  return normalizeAzimuthDeg(Math.atan2(v[0], v[1]) * RAD2DEG);
}

/** Différence angulaire de DIRECTION d'arête, repliée dans [0, 90]. */
function edgeAngleDiffDeg(d1: Vec2, d2: Vec2): number {
  const a1 = Math.atan2(d1[1], d1[0]) * RAD2DEG;
  const a2 = Math.atan2(d2[1], d2[0]) * RAD2DEG;
  let diff = Math.abs(a1 - a2) % 180; // les arêtes sont non-orientées (mod 180°)
  if (diff > 90) diff = 180 - diff;
  return diff;
}

interface EdgeMetric {
  ai: Vec2; // sommet a (mètres)
  bi: Vec2; // sommet b (mètres)
  aLngLat: LngLat;
  bLngLat: LngLat;
  dir: Vec2; // a → b
  lengthM: number;
}

/** Itère les arêtes d'un anneau (fermé implicitement) en versions métrique + lng/lat. */
function edges(ring: LngLat[], project: (p: LngLat) => Vec2): EdgeMetric[] {
  const out: EdgeMetric[] = [];
  const n = ring.length;
  for (let i = 0; i < n; i++) {
    const aLngLat = ring[i];
    const bLngLat = ring[(i + 1) % n];
    const ai = project(aLngLat);
    const bi = project(bLngLat);
    const dir = sub(bi, ai);
    const lengthM = len(dir);
    if (lengthM <= 0) continue; // ignore les arêtes dégénérées
    out.push({ ai, bi, aLngLat, bLngLat, dir, lengthM });
  }
  return out;
}

/**
 * Longueur de recouvrement (mètres) entre deux arêtes quasi-collinéaires :
 * on projette les 4 extrémités sur la direction de l'arête 1 et on mesure
 * l'intersection des deux intervalles [min,max].
 */
function overlapLengthM(e1: EdgeMetric, e2: EdgeMetric): number {
  const axis = scale(e1.dir, 1 / e1.lengthM); // direction unitaire de e1
  const proj = (p: Vec2): number => dot(sub(p, e1.ai), axis);
  const a1 = 0;
  const b1 = e1.lengthM;
  const p2a = proj(e2.ai);
  const p2b = proj(e2.bi);
  const lo2 = Math.min(p2a, p2b);
  const hi2 = Math.max(p2a, p2b);
  const lo = Math.max(Math.min(a1, b1), lo2);
  const hi = Math.min(Math.max(a1, b1), hi2);
  return Math.max(0, hi - lo);
}

// ————————————————————————————————————————————————————————————————
// API publique
// ————————————————————————————————————————————————————————————————

/**
 * Trouve l'arête PARTAGÉE/PROCHE entre deux zones : la paire d'arêtes (une par
 * anneau) la plus proche, quasi-collinéaire, quasi-coïncidente et avec un
 * recouvrement suffisant. Renvoie l'arête commune (segment de recouvrement
 * exprimé sur l'arête de `zone`), l'écart mesuré et le recouvrement, ou null.
 *
 * Pur : numbers in, numbers out.
 */
export function findSharedEdge(
  zone: LngLat[],
  neighbour: LngLat[],
  options: AdjacencyOptions = {},
): {
  sharedEdge: SharedEdge;
  gapM: number;
  overlapM: number;
  zoneEdge: EdgeMetricPublic;
  neighbourEdge: EdgeMetricPublic;
} | null {
  if (!isRing(zone) || !isRing(neighbour)) return null;
  const opts = { ...DEFAULTS, ...options };

  // Projecteur commun centré sur le centroïde de la zone interrogée.
  const c = centroidLngLat(zone);
  const project = makeProjector(c[0], c[1]);

  const zEdges = edges(zone, project);
  const nEdges = edges(neighbour, project);
  if (zEdges.length === 0 || nEdges.length === 0) return null;

  let best:
    | {
        zoneEdge: EdgeMetric;
        nbEdge: EdgeMetric;
        gapM: number;
        overlapM: number;
      }
    | null = null;

  for (const ze of zEdges) {
    for (const ne of nEdges) {
      const angle = edgeAngleDiffDeg(ze.dir, ne.dir);
      if (angle > opts.maxAngleDeg) continue;

      // Écart = distance moyenne des extrémités de l'arête voisine à l'arête
      // de la zone (et réciproquement), pour être robuste aux longueurs
      // différentes des deux arêtes.
      const gap =
        (distPointSegment(ne.ai, ze.ai, ze.bi) +
          distPointSegment(ne.bi, ze.ai, ze.bi) +
          distPointSegment(ze.ai, ne.ai, ne.bi) +
          distPointSegment(ze.bi, ne.ai, ne.bi)) /
        4;
      if (gap > opts.maxGapM) continue;

      const overlap = overlapLengthM(ze, ne);
      if (overlap < opts.minOverlapM) continue;

      // On préfère le plus grand recouvrement, puis le plus petit écart.
      if (
        best === null ||
        overlap > best.overlapM + 1e-9 ||
        (Math.abs(overlap - best.overlapM) <= 1e-9 && gap < best.gapM)
      ) {
        best = { zoneEdge: ze, nbEdge: ne, gapM: gap, overlapM: overlap };
      }
    }
  }

  if (best === null) return null;

  const sharedEdge: SharedEdge = {
    p1: best.zoneEdge.aLngLat,
    p2: best.zoneEdge.bLngLat,
    lengthM: best.zoneEdge.lengthM,
  };

  return {
    sharedEdge,
    gapM: best.gapM,
    overlapM: best.overlapM,
    zoneEdge: toPublicEdge(best.zoneEdge),
    neighbourEdge: toPublicEdge(best.nbEdge),
  };
}

/** Vue publique (lng/lat + mètres) d'une arête détectée. */
export interface EdgeMetricPublic {
  aLngLat: LngLat;
  bLngLat: LngLat;
  lengthM: number;
}

function toPublicEdge(e: EdgeMetric): EdgeMetricPublic {
  return { aLngLat: e.aLngLat, bLngLat: e.bLngLat, lengthM: e.lengthM };
}

/**
 * Infère la façade (`facingAzimuthDeg`) d'une `zone` étant donné une `neighbour`
 * adjacente. `neighbourFacingDeg` (si connu) permet à la mono-pente de la
 * copier. Détecte pignon vs continuation par la géométrie.
 *
 * Retourne toujours un résultat ; si aucune arête partagée n'est trouvée,
 * `connected:false`, `sharedEdge:null`, `kind:'none'` et le repli sud (180°).
 *
 * Pur : numbers in, numbers out.
 */
export function inferZoneFacing(
  zone: LngLat[],
  neighbour: LngLat[],
  neighbourFacingDeg?: number,
  options: AdjacencyOptions = {},
): AdjacencyResult {
  const opts = { ...DEFAULTS, ...options };
  const found = findSharedEdge(zone, neighbour, opts);

  if (found === null) {
    return {
      connected: false,
      confidence: 0,
      facingAzimuthDeg: FALLBACK_FACING_DEG,
      sharedEdge: null,
      kind: 'none',
    };
  }

  // Projection métrique centrée sur le centroïde de la zone interrogée.
  const cZoneLngLat = centroidLngLat(zone);
  const project = makeProjector(cZoneLngLat[0], cZoneLngLat[1]);

  const a = project(found.sharedEdge.p1);
  const b = project(found.sharedEdge.p2);
  const edgeDir = sub(b, a);
  const edgeLen = len(edgeDir) || 1;
  const edgeUnit = scale(edgeDir, 1 / edgeLen);
  // Normale unitaire à l'arête (deux candidates : ±[−dy, dx]).
  const normal: Vec2 = [-edgeUnit[1], edgeUnit[0]];

  const cZone = project(cZoneLngLat); // ≈ [0,0]
  const cNb = project(centroidLngLat(neighbour));
  const mid: Vec2 = scale(add(a, b), 0.5);

  // Côté signé de chaque centroïde par rapport à l'arête (le long de la normale).
  const sideZone = dot(sub(cZone, mid), normal);
  const sideNb = dot(sub(cNb, mid), normal);

  // DESCENTE DE PENTE : le pan descend de la faîtière partagée VERS son propre
  // corps (donc vers son centroïde) et au-delà. C'est cette direction-là que
  // regarde le pan. On choisit donc la normale qui pointe VERS le côté du
  // centroïde de la zone (même côté que le centroïde, pas l'opposé).
  const downSlope: Vec2 = sideZone >= 0 ? normal : scale(normal, -1);
  const gableFacing = vecToAzimuthDeg(downSlope);

  // Distance des centroïdes à l'arête → confiance et robustesse du signe.
  const distZone = Math.abs(sideZone);
  const distNb = Math.abs(sideNb);

  // PIGNON vs CONTINUATION
  // ----------------------
  // Critère GÉOMÉTRIQUE (celui prescrit) : centroïdes de PART ET D'AUTRE de
  // l'arête (signes opposés, tous deux nets) → pignon ; MÊME côté / extension
  // collinéaire → mono-pente. Deux pans convexes non chevauchants qui partagent
  // une arête PLEINE se retrouvent presque toujours de part et d'autre ; le cas
  // « même côté » correspond aux extensions en L / collinéaires.
  const SIDE_EPS_M = 0.25; // sous ce seuil le centroïde est « sur » l'arête → ambigu
  const oppositeSidesGeom =
    sideZone * sideNb < 0 && distZone > SIDE_EPS_M && distNb > SIDE_EPS_M;

  // Critère par la FAÇADE du voisin (lève l'ambiguïté quand elle est connue) :
  // on regarde si le voisin DESCEND VERS l'arête partagée (sa façade traverse
  // l'arête vers le pan interrogé → CONTINUATION : même pente) ou s'il descend
  // À L'OPPOSÉ de l'arête (l'arête est sa faîtière → PIGNON).
  let kind: AdjacencyKind;
  let facingAzimuthDeg: number;

  const hasNbFacing =
    neighbourFacingDeg !== undefined && Number.isFinite(neighbourFacingDeg);

  if (hasNbFacing) {
    // Normale unitaire orientée de l'arête VERS le pan interrogé (côté zone).
    const towardZone: Vec2 = sideZone >= 0 ? normal : scale(normal, -1);
    const az = normalizeAzimuthDeg(neighbourFacingDeg as number) * DEG2RAD;
    const nbFacingVec: Vec2 = [Math.sin(az), Math.cos(az)]; // [est, nord]
    // Si la façade du voisin pointe vers le pan interrogé (composante positive
    // sur towardZone), le voisin descend en traversant l'arête → continuation.
    const continues = dot(nbFacingVec, towardZone) > Math.cos(60 * DEG2RAD);
    if (continues) {
      kind = 'mono-pente';
      facingAzimuthDeg = normalizeAzimuthDeg(neighbourFacingDeg as number);
    } else {
      kind = 'gable';
      facingAzimuthDeg = gableFacing;
    }
  } else if (oppositeSidesGeom) {
    kind = 'gable';
    facingAzimuthDeg = gableFacing;
  } else {
    // Même côté / collinéaire et façade voisine inconnue → continuation, on
    // retombe sur la descente géométrique du pan (faute de mieux).
    kind = 'mono-pente';
    facingAzimuthDeg = gableFacing;
  }

  return {
    connected: true,
    confidence: computeConfidence(found, kind, distZone, distNb, opts),
    facingAzimuthDeg,
    sharedEdge: found.sharedEdge,
    kind,
  };
}

/**
 * Confiance dans [0, 1] : combine la qualité géométrique de l'arête partagée
 * (écart faible, recouvrement long) et la netteté de la décision pignon/pente
 * (centroïdes bien décollés de l'arête).
 */
function computeConfidence(
  found: { gapM: number; overlapM: number },
  kind: AdjacencyKind,
  distZone: number,
  distNb: number,
  opts: Required<AdjacencyOptions>,
): number {
  // Qualité d'arête : écart proche de 0 → 1 ; écart = maxGap → 0.
  const gapScore = clamp01(1 - found.gapM / opts.maxGapM);
  // Recouvrement : 1 m de recouvrement → bonne confiance, sature à 4 m.
  const overlapScore = clamp01(found.overlapM / 4);
  // Netteté de la décision : centroïdes bien décollés de l'arête (≥ 1 m → net).
  const minDist = Math.min(distZone, distNb);
  const sharpness = clamp01(minDist / 1);

  // Pondération : l'arête compte le plus ; on borne pour rester < 1 en cas
  // limite et > 0 dès qu'on est « connecté ».
  const base = 0.5 * gapScore + 0.3 * overlapScore + 0.2 * sharpness;
  // Une mono-pente sans neighbourFacing reste plausible mais moins certaine.
  const conf = kind === 'none' ? 0 : Math.max(0.05, base);
  return clamp01(conf);
}

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function isRing(ring: unknown): ring is LngLat[] {
  return Array.isArray(ring) && ring.length >= 3;
}

/**
 * Variante pratique pour le constructeur 3D : infère la façade d'une zone
 * candidate face à PLUSIEURS zones existantes ; renvoie le meilleur résultat
 * connecté (recouvrement le plus long), sinon le repli sud. `neighbourFacings`
 * (parallèle à `neighbours`) fournit la façade connue de chaque voisin pour
 * permettre la copie mono-pente.
 *
 * Pur : numbers in, numbers out.
 */
export function inferZoneFacingAmong(
  zone: LngLat[],
  neighbours: LngLat[][],
  neighbourFacings: (number | undefined)[] = [],
  options: AdjacencyOptions = {},
): AdjacencyResult {
  let best: AdjacencyResult | null = null;
  let bestOverlap = -1;

  for (let i = 0; i < neighbours.length; i++) {
    const res = inferZoneFacing(zone, neighbours[i], neighbourFacings[i], options);
    if (!res.connected) continue;
    const overlap = res.sharedEdge ? res.sharedEdge.lengthM : 0;
    if (best === null || overlap > bestOverlap) {
      best = res;
      bestOverlap = overlap;
    }
  }

  return (
    best ?? {
      connected: false,
      confidence: 0,
      facingAzimuthDeg: FALLBACK_FACING_DEG,
      sharedEdge: null,
      kind: 'none',
    }
  );
}
