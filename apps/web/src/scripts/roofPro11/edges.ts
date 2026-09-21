/**
 * CAL57 — types d'arête par segment de contour (faîtage / noue / arêtier / égout /
 * rive / inconnue). Géométrie PURE (aucun Three, aucun DOM) : le type est DÉDUIT du
 * tracé + du toit voisin, jamais saisi par défaut au hasard — et laissé « inconnue »
 * quand la déduction ne serait qu'une supposition.
 *
 * CALX93 — la noue et l'arêtier sont maintenant déduits, mais SEULEMENT quand les deux
 * pans qui se partagent l'arête ont leur azimut de fruit ET leur pente SAISIS :
 *  - arête de NIVEAU des deux côtés + fruits opposés → `faitage` (inchangé) ;
 *  - arête MONTANTE des deux côtés vers laquelle les deux pans DESCENDENT → `noue`
 *    (le creux où l'eau se rassemble) ;
 *  - arête MONTANTE des deux côtés dont les deux pans S'ÉCARTENT → `arretier` (le
 *    saillant d'où l'eau s'éloigne) ;
 *  - tout le reste (pente non saisie, pente nulle, sens mixte, arête de niveau d'un
 *    seul côté) reste `inconnue`, avec un motif NOMMÉ — jamais un type choisi au
 *    hasard entre noue et arêtier. Le motif est lisible via `deduceEdgeDetails`.
 *
 * CALX94 — un type CORRIGÉ À LA MAIN dans l'atelier (`edgesUi.ts`) porte `manuel: true` et
 * n'est plus jamais re-déduit : `fusionnerAretesSaisies` superpose les saisies (type
 * corrigé, retrait `retraitM` par arête) à la déduction, et c'est ce résultat que
 * `serializeLayout` écrit dans le document.
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
  /** CALX94 — `true` quand le type a été ÉCRIT PAR L'UTILISATEUR dans l'atelier
   *  (`edgesUi.ts`), en remplacement du type déduit. Marque de provenance : la
   *  re-déduction ne réécrit JAMAIS une arête marquée `manuel` (voir
   *  `fusionnerAretesSaisies`). Absent ou `false` = type déduit. */
  manuel?: boolean;
  /** CALX81/CALX95 — retrait SAISI pour CE segment seul (m, ≥ 0). OPTIONNEL : absent =
   *  seuls les retraits de CATÉGORIE s'appliquent (comportement d'aujourd'hui). Jamais
   *  déduit ni complété — une valeur non saisie reste ABSENTE (jamais un zéro, qui se
   *  lirait « mesuré à ras »). Consommé par `lib/roofSetbackEdge.ts`. */
  retraitM?: number;
}

/** CALX94 — libellé FRANÇAIS de chaque type d'arête, pour le sélecteur de l'atelier et
 *  tout affichage. Les six valeurs de `EdgeType`, jamais un sous-ensemble : « inconnue »
 *  est un choix valable (« je ne sais pas » reste une réponse honnête). */
export const EDGE_TYPE_LABELS: Record<EdgeType, string> = {
  faitage: 'Faîtage',
  noue: 'Noue',
  arretier: 'Arêtier',
  egout: 'Égout',
  rive: 'Rive',
  inconnue: 'Inconnue',
};

/** CALX94 — les six types, dans l'ordre d'affichage du sélecteur. */
export const EDGE_TYPES: readonly EdgeType[] = ['faitage', 'noue', 'arretier', 'egout', 'rive', 'inconnue'];

/** CALX94 — une valeur est-elle l'un des six types d'arête ? (lecture d'un document ou
 *  d'un `<select>` : rien d'autre n'est accepté, et rien n'est « corrigé » en douce). */
export function isEdgeType(v: unknown): v is EdgeType {
  return typeof v === 'string' && (EDGE_TYPES as readonly string[]).includes(v);
}

/**
 * CALX94 — fusionne ce que l'UTILISATEUR a saisi sur les arêtes (`existantes`) avec ce que
 * la déduction vient de produire (`deduites`), segment par segment :
 *  - une arête marquée `manuel: true` GARDE son type saisi (la déduction ne l'écrase
 *    jamais — sans cela, toute correction serait perdue à la sérialisation suivante) ;
 *  - un `retraitM` SAISI (CALX81) est reporté tel quel, qu'il y ait eu correction de type
 *    ou non : c'est une mesure, pas une déduction ;
 *  - une arête sans saisie prend le type DÉDUIT, inchangé ;
 *  - une saisie dont l'`index` n'existe plus dans le contour (sommet supprimé) est
 *    ABANDONNÉE — jamais rattachée à un autre segment, jamais réinventée.
 * Fonction PURE : ne mute ni `existantes` ni `deduites`. Renvoie `undefined` quand il n'y
 * a rien à écrire (aucune arête déduite), pour que l'appelant n'émette pas de clé vide.
 */
export function fusionnerAretesSaisies(
  existantes: readonly SerializedEdge[] | undefined,
  deduites: readonly SerializedEdge[] | undefined,
): SerializedEdge[] | undefined {
  if (!deduites || !deduites.length) return undefined;
  const saisieParIndex = new Map<number, SerializedEdge>();
  for (const e of existantes ?? []) {
    if (e && Number.isInteger(e.index)) saisieParIndex.set(e.index, e);
  }
  return deduites.map((d) => {
    const saisie = saisieParIndex.get(d.index);
    if (!saisie) return { index: d.index, type: d.type };
    const manuel = saisie.manuel === true && isEdgeType(saisie.type);
    const retrait =
      typeof saisie.retraitM === 'number' && Number.isFinite(saisie.retraitM) && saisie.retraitM >= 0
        ? saisie.retraitM
        : undefined;
    return {
      index: d.index,
      type: manuel ? saisie.type : d.type,
      ...(manuel ? { manuel: true as const } : {}),
      ...(retrait !== undefined ? { retraitM: retrait } : {}),
    };
  });
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
  /** CALX93 — pente SAISIE du pan (deg). OPTIONNELLE, et volontairement sans valeur de
   *  repli : absente = non saisie, et la distinction noue/arêtier s'en abstient (arête
   *  « inconnue », motif nommé) au lieu de supposer une pente.
   *  CALX94 — `serializeLayout` (`prefill.ts`) y reporte désormais la pente déjà saisie du
   *  pan, donc une noue ou un arêtier peut enfin apparaître dans le vrai document ; un
   *  appelant qui ne la passe pas laisse simplement toute arête montante « inconnue ». */
  pitchDeg?: number;
}

/** CALX93 — un type d'arête AVEC le motif qui l'explique (et, pour « inconnue », ce qui
 *  manque pour trancher). Le motif n'est PAS sérialisé : il sert à l'affichage et au
 *  diagnostic ; le document ne porte que `index`/`type` (schéma v2 inchangé). */
export interface EdgeDeductionDetail extends SerializedEdge {
  raison: string;
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

/** CALX93 — convention de dessin : en deçà de 12° d'écart, un segment est tenu pour
 *  « de niveau » sur un pan (faîtage/égout) ; au-delà, il MONTE le long de la pente.
 *  Même tolérance angulaire de dessin que l'appariement d'arêtes ci-dessus. */
const LEVEL_TOL_DEG = 12;
/** CALX93 — convention de dessin : deux fruits sont tenus pour OPPOSÉS à 12° près. */
const OPPOSITE_TOL_DEG = 12;
/** CALX93 — convention de dessin : sous un demi-mètre d'écart amont/aval entre l'arête
 *  et le barycentre du pan, on ne tranche pas de quel côté le pan descend. */
const SLOPE_SIDE_MIN_M = 0.5;

/** Écart absolu (deg, 0..180) entre deux azimuts. */
function azimuthGapDeg(a: number, b: number): number {
  const d = Math.abs((((a - b) % 360) + 360) % 360);
  return d > 180 ? 360 - d : d;
}

/** Inclinaison (deg, 0..90) d'un segment par rapport à la ligne de NIVEAU du pan :
 *  0 = le segment suit une courbe de niveau (faîtage, égout), 90 = il suit la ligne de
 *  plus grande pente. Purement plan : ne dépend PAS de la valeur de la pente. */
function segmentRiseDeg(dx: number, dy: number, facingAzimuthDeg: number): number {
  const len = Math.hypot(dx, dy);
  if (len <= 0) return 0;
  const ratio = Math.min(1, Math.abs(upSlopeCoord(dx, dy, facingAzimuthDeg)) / len);
  return Math.asin(ratio) * (180 / Math.PI);
}

/** De quel côté de l'arête le pan descend : `amont` = l'arête est en HAUT du pan (le pan
 *  s'en écarte en descendant), `aval` = l'arête est en BAS (le pan y déverse),
 *  `indecis` = écart trop faible pour trancher. */
type SlopeSide = 'amont' | 'aval' | 'indecis';

function edgeSlopeSide(
  enu: readonly [number, number][],
  facingAzimuthDeg: number,
  e1: [number, number],
  e2: [number, number],
): SlopeSide {
  let sx = 0;
  let sy = 0;
  for (const [x, y] of enu) {
    sx += x;
    sy += y;
  }
  const uCentroid = upSlopeCoord(sx / enu.length, sy / enu.length, facingAzimuthDeg);
  const uEdge = (upSlopeCoord(e1[0], e1[1], facingAzimuthDeg) + upSlopeCoord(e2[0], e2[1], facingAzimuthDeg)) / 2;
  const delta = uEdge - uCentroid;
  if (delta > SLOPE_SIDE_MIN_M) return 'amont';
  if (delta < -SLOPE_SIDE_MIN_M) return 'aval';
  return 'indecis';
}

/** Un pan voisin retenu pour un segment : son contour projeté dans le MÊME repère ENU
 *  que le pan courant, et la longueur de recouvrement qui l'a fait retenir. */
interface SharedNeighbor {
  zone: EdgeDeductionZone;
  enu: [number, number][];
  overlap: number;
}

/**
 * CALX93 — type d'une arête PARTAGÉE par deux pans en pente, déduit des seules valeurs
 * SAISIES (azimuts de fruit, pentes) et du tracé. Renvoie `inconnue` + le motif dès
 * qu'une donnée manque ou que la configuration n'est pas l'une des trois reconnues.
 */
function classifySharedEdge(
  zone: EdgeDeductionZone,
  zoneEnu: readonly [number, number][],
  neighbor: SharedNeighbor,
  e1: [number, number],
  e2: [number, number],
): { type: EdgeType; raison: string } {
  const other = neighbor.zone;
  const riseSelf = segmentRiseDeg(e2[0] - e1[0], e2[1] - e1[1], zone.facingAzimuthDeg);
  const riseOther = segmentRiseDeg(e2[0] - e1[0], e2[1] - e1[1], other.facingAzimuthDeg);
  const levelSelf = riseSelf <= LEVEL_TOL_DEG;
  const levelOther = riseOther <= LEVEL_TOL_DEG;
  const gap = azimuthGapDeg(zone.facingAzimuthDeg, other.facingAzimuthDeg);
  if (levelSelf && levelOther) {
    if (gap >= 180 - OPPOSITE_TOL_DEG) {
      return { type: 'faitage', raison: 'arête de niveau sur les deux pans, fruits opposés' };
    }
    return {
      type: 'inconnue',
      raison: `arête de niveau sur les deux pans mais fruits non opposés (${Math.round(gap)}° d'écart) : ni faîtage ni noue déductible`,
    };
  }
  if (levelSelf !== levelOther) {
    return {
      type: 'inconnue',
      raison: 'arête de niveau sur un pan et montante sur l’autre : les deux pans ne se rejoignent pas sur le même plan',
    };
  }
  // Arête montante des DEUX côtés : noue et arêtier ne se distinguent que si la pente
  // est SAISIE sur les deux pans (une pente absente ou nulle ne fait monter aucune arête).
  if (zone.pitchDeg === undefined || !Number.isFinite(zone.pitchDeg)) {
    return { type: 'inconnue', raison: 'pente non saisie sur ce pan : noue et arêtier ne se distinguent pas sans elle' };
  }
  if (other.pitchDeg === undefined || !Number.isFinite(other.pitchDeg)) {
    return { type: 'inconnue', raison: 'pente non saisie sur le pan voisin : noue et arêtier ne se distinguent pas sans elle' };
  }
  if (zone.pitchDeg <= 0 || other.pitchDeg <= 0) {
    return { type: 'inconnue', raison: 'pente saisie nulle sur l’un des deux pans : aucune arête ne monte, rien à trancher' };
  }
  const sideSelf = edgeSlopeSide(zoneEnu, zone.facingAzimuthDeg, e1, e2);
  const sideOther = edgeSlopeSide(neighbor.enu, other.facingAzimuthDeg, e1, e2);
  if (sideSelf === 'indecis' || sideOther === 'indecis') {
    return { type: 'inconnue', raison: 'arête trop proche du milieu d’un pan pour dire s’il y descend ou s’en écarte' };
  }
  if (sideSelf === 'aval' && sideOther === 'aval') {
    return { type: 'noue', raison: 'arête montante vers laquelle les deux pans descendent (creux)' };
  }
  if (sideSelf === 'amont' && sideOther === 'amont') {
    return { type: 'arretier', raison: 'arête montante dont les deux pans s’écartent en descendant (saillant)' };
  }
  return {
    type: 'inconnue',
    raison: 'un pan descend vers l’arête et l’autre s’en écarte : ni noue ni arêtier',
  };
}

/**
 * CAL57 + CALX93 — déduit le type de chaque segment du contour d'un pan ET le motif de
 * la déduction :
 *  - toit PLAT : aucun concept de faîtière/égout n'existe → tous les segments sont
 *    des rives (fait géométrique, pas une supposition) ;
 *  - toit en PENTE : un segment partagé avec un pan en pente ADJACENT (même test
 *    d'adjacence que `computeRidgeLifts`) est typé par `classifySharedEdge` —
 *    `faitage`, `noue`, `arretier`, ou `inconnue` avec ce qui manque pour trancher ;
 *    parmi les segments restants, celui dont la coordonnée amont-aval moyenne est la
 *    plus BASSE (le plus en aval de la pente) est l'égout — fait géométrique déduit de
 *    la pente saisie, pas une invention ; tout le reste reste 'inconnue' (distinguer
 *    une rive d'une arête de pignon demanderait une donnée que le document ne porte pas).
 * Quand plusieurs voisins se recouvrent sur le même segment, c'est le recouvrement le
 * plus LONG qui décide (déterministe).
 * Renvoie [] pour un contour < 3 sommets (rien à typer).
 */
export function deduceEdgeDetails(
  zone: EdgeDeductionZone,
  others: readonly EdgeDeductionZone[],
): EdgeDeductionDetail[] {
  const ring = zone.vertices;
  const n = ring.length;
  if (n < 3) return [];
  if (zone.roofType !== 'pitched') {
    return ring.map((_, i) => ({
      index: i,
      type: 'rive' as const,
      raison: 'toit plat : ni faîtage ni égout n’existent sur ce toit',
    }));
  }
  const origin = ring[0];
  const enu = ringToEnu(ring, origin);
  const neighborBySeg = new Array<SharedNeighbor | null>(n).fill(null);
  for (const other of others) {
    if (other.roofType !== 'pitched' || other.vertices.length < 3) continue;
    const otherEnu = ringToEnu(other.vertices, origin);
    for (let i = 0; i < n; i++) {
      const a1 = enu[i];
      const a2 = enu[(i + 1) % n];
      let best = 0;
      for (let j = 0; j < otherEnu.length; j++) {
        const b1 = otherEnu[j];
        const b2 = otherEnu[(j + 1) % otherEnu.length];
        const overlap = edgeOverlapM(a1, a2, b1, b2);
        if (overlap > best) best = overlap;
      }
      const current = neighborBySeg[i];
      if (best > 0 && (current === null || best > current.overlap)) {
        neighborBySeg[i] = { zone: other, enu: otherEnu, overlap: best };
      }
    }
  }
  let egoutIdx = -1;
  let minUp = Infinity;
  for (let i = 0; i < n; i++) {
    if (neighborBySeg[i]) continue;
    const [x1, y1] = enu[i];
    const [x2, y2] = enu[(i + 1) % n];
    const uMid = (upSlopeCoord(x1, y1, zone.facingAzimuthDeg) + upSlopeCoord(x2, y2, zone.facingAzimuthDeg)) / 2;
    if (uMid < minUp) {
      minUp = uMid;
      egoutIdx = i;
    }
  }
  return ring.map((_, i) => {
    const neighbor = neighborBySeg[i];
    if (neighbor) {
      const { type, raison } = classifySharedEdge(zone, enu, neighbor, enu[i], enu[(i + 1) % n]);
      return { index: i, type, raison };
    }
    if (i === egoutIdx) {
      return { index: i, type: 'egout' as const, raison: 'segment le plus en aval de la pente saisie, et non partagé' };
    }
    return {
      index: i,
      type: 'inconnue' as const,
      raison: 'segment ni partagé avec un pan voisin ni le plus en aval : rien ne le distingue d’une rive',
    };
  });
}

/**
 * CAL57 — types d'arête SÉRIALISÉS (`index`/`type` seulement : le document v2 ne porte
 * pas le motif). Même déduction que `deduceEdgeDetails`, dont c'est la projection.
 */
export function deduceEdgeTypes(zone: EdgeDeductionZone, others: readonly EdgeDeductionZone[]): SerializedEdge[] {
  return deduceEdgeDetails(zone, others).map(({ index, type }) => ({ index, type }));
}
