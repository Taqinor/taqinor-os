/**
 * PV30 — PLACEMENT LIBRE : logique PURE du second mode d'édition du calepinage.
 *
 * Le mode « lattice » (layoutVariability.ts) ne déplace un panneau que d'une CELLULE
 * validée par l'optimiseur à une autre : sûr par construction, mais impossible d'y
 * gagner de la place — les retraits de rive et les écarts entre panneaux sont ceux de
 * l'étude, point. Ce module est l'autre moitié demandée par le fondateur : le panneau
 * vit à des coordonnées CONTINUES, et ce sont des CONTRÔLES GÉOMÉTRIQUES RÉELS qui
 * disent oui ou non — plus une lattice pré-mâchée.
 *
 * TROIS CONTRAINTES DURES (jamais négociables — elles décrivent la physique) :
 *   1. le rectangle du panneau tient ENTIÈREMENT dans le contour du toit (les 4 coins
 *      dedans ET aucune arête du contour ne traverse le rectangle : un toit concave
 *      peut avoir ses 4 coins dedans et une encoche au milieu) ;
 *   2. aucun recouvrement panneau-panneau ;
 *   3. l'empreinte d'un obstacle (+ son dégagement propre) reste interdite.
 *
 * DEUX CONTRAINTES RELÂCHABLES (c'est tout l'objet du mode) :
 *   - le RETRAIT de rive (`setbackM`) ;
 *   - l'ÉCART minimal entre panneaux (`gapM`).
 * Les deux valent par défaut ce que l'étude a utilisé, et l'utilisateur a le droit de
 * les baisser — y compris à zéro. Ce n'est pas une triche cachée : l'interface affiche
 * les distances MESURÉES pendant le geste, donc réduire une marge est un acte VU.
 *
 * REPÈRE. Tout se calcule dans le repère (u, v) du pavage — u = axe long des rangées,
 * v = axe d'empilement — car TOUS les panneaux y partagent la même orientation : leurs
 * rectangles y sont alignés sur les axes, et « recouvrement » redevient une simple
 * intersection d'intervalles (exact, pas une approximation). Les positions restent
 * stockées en ENU (mètres, repère `pack.origin`) : c'est déjà la forme sérialisée des
 * panneaux, donc le placement libre n'invente AUCUN nouveau format de coordonnées.
 *
 * Module PUR : aucun DOM, aucune 3D, aucun MapLibre.
 */
import { pointInPolygon } from './roof';

/** Tolérance « pile sur la rive » (m) — même esprit que EDGE_EPS_M du pavage : le repère
 *  tourné porte un bruit flottant, sans quoi un retrait nul rejetterait la rive. */
export const FREE_EDGE_EPS_M = 1e-3;
/** Tolérance de recouvrement (m) : deux panneaux qui se touchent EXACTEMENT ne se
 *  recouvrent pas. En dessous, c'est du bruit flottant, pas un chevauchement. */
export const FREE_OVERLAP_EPS_M = 1e-6;

export type Vec2 = [number, number];

/** Un panneau posé LIBREMENT : centre ENU (m) + sa face E-O éventuelle (rendu chevron). */
export interface FreePanel {
  cx: number;
  cy: number;
  face?: 'E' | 'W';
  /** CAL80 — rotation propre du panneau (degrés), EN PLUS de l'axe de rangée (g.u/g.s) :
   *  0/absent = panneau aligné sur la rangée, comportement INCHANGÉ (le rectangle axé
   *  reste le chemin rapide partout ailleurs dans ce module — `rectOfPanel`/`checkRect`
   *  n'y touchent pas). Une valeur non nulle est lue UNIQUEMENT par les fonctions
   *  `rotate*`/`panelCornersUV` ci-dessous. */
  angleDeg?: number;
}

/** Anneau d'exclusion : empreinte ENU d'un obstacle + son dégagement propre (m). */
export interface FreeObstacle {
  ring: Vec2[];
  clearanceM: number;
}

/**
 * Contexte géométrique du pan en cours d'édition. Tout vient du pavage gagnant —
 * on ne redérive AUCUNE dimension de panneau ni aucun azimut.
 */
export interface FreeGeom {
  /** Axe long des rangées (unitaire, ENU). */
  u: Vec2;
  /** Axe d'empilement (unitaire, ENU), orthogonal à `u`. */
  s: Vec2;
  /** Largeur du panneau le long de `u` (m). */
  widthM: number;
  /** Empreinte au sol du panneau le long de `s` (m) — L·cos β, pas la longueur brute. */
  depthM: number;
  /** Contour du toit en ENU. */
  ringENU: Vec2[];
  /** Obstacles (empreinte + dégagement). */
  obstacles: FreeObstacle[];
}

/** Marges RELÂCHABLES, en mètres. */
export interface FreeMargins {
  /** Retrait de rive minimal exigé (m). 0 = panneau autorisé jusqu'au bord. */
  setbackM: number;
  /** Écart minimal entre deux panneaux (m). 0 = panneaux jointifs autorisés. */
  gapM: number;
}

/** État du placement libre : la liste ORDONNÉE des panneaux posés. L'index dans cette
 *  liste est la clé de sélection ET l'index d'instance 3D — un seul système. */
export interface FreeLayoutState {
  panels: FreePanel[];
}

/** Pourquoi un placement est refusé. Ordre = priorité d'affichage. */
export type FreeViolation = 'outline' | 'overlap' | 'obstacle' | 'setback' | 'gap';

/** Verdict d'un placement + les distances MESURÉES (pour l'affichage honnête). */
export interface FreeCheck {
  ok: boolean;
  /** Contraintes violées (vide si ok). */
  violations: FreeViolation[];
  /** Une contrainte DURE est-elle violée ? (refus non négociable). */
  hard: boolean;
  /** Distance mesurée du panneau à la rive la plus proche (m) — négative s'il déborde. */
  edgeM: number;
  /** Distance mesurée au panneau voisin le plus proche (m), ou null si seul. */
  panelM: number | null;
}

// ═══════════ repère (u, v) ═══════════

/** Axes du pavage depuis son azimut de visée (mêmes formules que `packCells`). */
export function geomAxes(azimuthDeg: number): { u: Vec2; s: Vec2 } {
  const az = (azimuthDeg * Math.PI) / 180;
  const f: Vec2 = [Math.sin(az), Math.cos(az)];
  return { u: [-f[1], f[0]], s: f };
}

/** ENU → (u, v). La base étant orthonormée, c'est une simple projection. */
export function toUV(g: FreeGeom, x: number, y: number): Vec2 {
  return [x * g.u[0] + y * g.u[1], x * g.s[0] + y * g.s[1]];
}

/** (u, v) → ENU. */
export function toENU(g: FreeGeom, uu: number, vv: number): Vec2 {
  return [uu * g.u[0] + vv * g.s[0], uu * g.u[1] + vv * g.s[1]];
}

/** Rectangle (u, v) d'un panneau centré en (cu, cv). */
export interface RectUV {
  u0: number;
  u1: number;
  v0: number;
  v1: number;
}

export function rectAt(g: FreeGeom, cu: number, cv: number): RectUV {
  const hw = g.widthM / 2;
  const hd = g.depthM / 2;
  return { u0: cu - hw, u1: cu + hw, v0: cv - hd, v1: cv + hd };
}

/** Rectangle (u, v) d'un panneau donné en ENU. */
export function rectOfPanel(g: FreeGeom, p: { cx: number; cy: number }): RectUV {
  const [cu, cv] = toUV(g, p.cx, p.cy);
  return rectAt(g, cu, cv);
}

const rectCorners = (r: RectUV): Vec2[] => [
  [r.u0, r.v0],
  [r.u1, r.v0],
  [r.u1, r.v1],
  [r.u0, r.v1],
];

// ═══════════ primitives géométriques ═══════════

/** Distance d'un point à un segment. */
function distPointSeg(p: Vec2, a: Vec2, b: Vec2): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/** Distance d'un point à la frontière d'un anneau (non signée). */
function distToRing(p: Vec2, ring: Vec2[]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    min = Math.min(min, distPointSeg(p, ring[j], ring[i]));
  }
  return min;
}

/** Les segments [p1,p2] et [p3,p4] se croisent-ils vraiment ? */
function segmentsCross(p1: Vec2, p2: Vec2, p3: Vec2, p4: Vec2): boolean {
  const d = (a: Vec2, b: Vec2, c: Vec2) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const d1 = d(p3, p4, p1);
  const d2 = d(p3, p4, p2);
  const d3 = d(p1, p2, p3);
  const d4 = d(p1, p2, p4);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}

/** Une arête de `ring` traverse-t-elle le rectangle ? (le cas du toit CONCAVE : 4 coins
 *  dedans et une encoche qui coupe quand même le panneau). */
function ringCrossesRect(ring: Vec2[], r: RectUV): boolean {
  const c = rectCorners(r);
  const edges: [Vec2, Vec2][] = [
    [c[0], c[1]],
    [c[1], c[2]],
    [c[2], c[3]],
    [c[3], c[0]],
  ];
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    for (const [a, b] of edges) if (segmentsCross(ring[j], ring[i], a, b)) return true;
  }
  return false;
}

/** Le rectangle et le polygone se recouvrent-ils (intersection d'aires) ? */
function rectMeetsPolygon(r: RectUV, poly: Vec2[]): boolean {
  if (poly.length < 3) return false;
  for (const c of rectCorners(r)) if (pointInPolygon(c, poly)) return true;
  for (const p of poly) if (p[0] >= r.u0 && p[0] <= r.u1 && p[1] >= r.v0 && p[1] <= r.v1) return true;
  return ringCrossesRect(poly, r);
}

/** Distance minimale entre le rectangle et la frontière d'un polygone (0 s'ils se coupent). */
function distRectToPolygon(r: RectUV, poly: Vec2[]): number {
  if (rectMeetsPolygon(r, poly)) return 0;
  let min = Infinity;
  const corners = rectCorners(r);
  for (const c of corners) min = Math.min(min, distToRing(c, poly));
  for (const p of poly) {
    for (let i = 0; i < 4; i++) min = Math.min(min, distPointSeg(p, corners[i], corners[(i + 1) % 4]));
  }
  return min;
}

/**
 * Séparation entre deux rectangles alignés sur les axes : 0 s'ils se recouvrent OU se
 * touchent, sinon la distance la plus courte entre eux (diagonale comprise).
 */
export function rectSeparation(a: RectUV, b: RectUV): number {
  const du = Math.max(b.u0 - a.u1, a.u0 - b.u1, 0);
  const dv = Math.max(b.v0 - a.v1, a.v0 - b.v1, 0);
  return Math.hypot(du, dv);
}

/**
 * Deux rectangles se RECOUVRENT-ils vraiment (aire commune non nulle) ? À distinguer
 * soigneusement de « séparation nulle » : deux panneaux POSÉS BORD À BORD sont à 0 m l'un
 * de l'autre sans se chevaucher — et c'est exactement la configuration que le fondateur
 * veut pouvoir obtenir en réduisant l'écart à zéro. Confondre les deux interdirait le
 * geste même que ce mode existe pour permettre.
 */
export function rectsOverlap(a: RectUV, b: RectUV): boolean {
  const du = Math.min(a.u1, b.u1) - Math.max(a.u0, b.u0);
  const dv = Math.min(a.v1, b.v1) - Math.max(a.v0, b.v0);
  return du > FREE_OVERLAP_EPS_M && dv > FREE_OVERLAP_EPS_M;
}

// ═══════════ contrôles de placement ═══════════

/** Distance SIGNÉE d'un point à la rive (+ dedans, − dehors). */
function signedInsideDist(p: Vec2, ring: Vec2[]): number {
  const d = distToRing(p, ring);
  return pointInPolygon(p, ring) ? d : -d;
}

/**
 * Vérifie un rectangle candidat contre TOUTES les contraintes, et renvoie les distances
 * mesurées. `ignore` = index des panneaux à ne pas considérer (ceux qu'on est en train de
 * déplacer). `extra` = rectangles supplémentaires déjà réservés par le même geste
 * (les autres membres du groupe à leur position d'ARRIVÉE).
 */
export function checkRect(
  state: FreeLayoutState,
  g: FreeGeom,
  r: RectUV,
  margins: FreeMargins,
  ignore: ReadonlySet<number> = new Set(),
  extra: readonly RectUV[] = [],
): FreeCheck {
  const violations: FreeViolation[] = [];
  const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));

  // — DURE 1 : entièrement dans le contour (coins dedans + aucune arête traversante) —
  let edgeM = Infinity;
  let outside = false;
  for (const c of rectCorners(r)) {
    const sd = signedInsideDist(c, ringUV);
    if (sd < edgeM) edgeM = sd;
    if (sd < -FREE_EDGE_EPS_M) outside = true;
  }
  if (outside || ringCrossesRect(ringUV, r)) violations.push('outline');

  // — DURE 2 : aucun recouvrement panneau-panneau (+ RELÂCHABLE : l'écart minimal) —
  let panelM: number | null = null;
  let overlaps = false;
  const others: RectUV[] = [];
  for (let i = 0; i < state.panels.length; i++) {
    if (ignore.has(i)) continue;
    others.push(rectOfPanel(g, state.panels[i]));
  }
  for (const e of extra) others.push(e);
  for (const o of others) {
    const sep = rectSeparation(r, o);
    if (panelM === null || sep < panelM) panelM = sep;
    if (rectsOverlap(r, o)) overlaps = true;
  }
  if (overlaps) violations.push('overlap');

  // — DURE 3 : empreinte d'obstacle + dégagement propre —
  for (const o of g.obstacles) {
    if (o.ring.length < 3) continue;
    const ringO = o.ring.map(([x, y]) => toUV(g, x, y));
    if (distRectToPolygon(r, ringO) <= o.clearanceM) {
      violations.push('obstacle');
      break;
    }
  }

  // — RELÂCHABLE : retrait de rive —
  if (!violations.includes('outline') && edgeM < margins.setbackM - FREE_EDGE_EPS_M) violations.push('setback');
  // — RELÂCHABLE : écart entre panneaux —
  if (!overlaps && panelM !== null && panelM < margins.gapM - FREE_EDGE_EPS_M) violations.push('gap');

  const hard = violations.some((v) => v === 'outline' || v === 'overlap' || v === 'obstacle');
  return { ok: violations.length === 0, violations, hard, edgeM, panelM };
}

/** Contrôle du panneau d'index `idx` s'il était posé au centre ENU donné. */
export function checkPanelAt(
  state: FreeLayoutState,
  g: FreeGeom,
  idx: number,
  cx: number,
  cy: number,
  margins: FreeMargins,
): FreeCheck {
  const [cu, cv] = toUV(g, cx, cy);
  return checkRect(state, g, rectAt(g, cu, cv), margins, new Set([idx]));
}

// ═══════════ CAL80 — rotation LIBRE d'un panneau ou d'une sélection ═══════════
// Le rectangle AXÉ (RectUV) suffit tant que tous les panneaux partagent l'axe de rangée —
// c'est le chemin rapide gardé INCHANGÉ partout au-dessus. Une rotation PROPRE au panneau
// casse cette hypothèse : les fonctions ci-dessous travaillent sur le POLYGONE à 4 coins
// (rotation générale) et retombent EXACTEMENT sur `rectAt`/`rectsOverlap` à angle 0 (mêmes
// coins, à l'ordre près) — aucune régression du chemin non tourné.

/** 4 coins (u, v) d'un panneau centré en (cu, cv), tourné de `angleDeg` (propre au panneau,
 *  EN PLUS de l'axe de rangée déjà porté par le repère (u, v)). angleDeg=0 → mêmes 4 coins
 *  que `rectAt` (à l'ordre près), donc les mêmes tests d'intersection. */
export function panelCornersUV(g: FreeGeom, cu: number, cv: number, angleDeg: number): Vec2[] {
  const hw = g.widthM / 2;
  const hd = g.depthM / 2;
  const rad = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const local: Vec2[] = [
    [-hw, -hd],
    [hw, -hd],
    [hw, hd],
    [-hw, hd],
  ];
  return local.map(([lu, lv]): Vec2 => [cu + lu * cos - lv * sin, cv + lu * sin + lv * cos]);
}

/** Axes de séparation candidats (normales des arêtes) d'un polygone convexe. */
function polyAxes(poly: Vec2[]): Vec2[] {
  const axes: Vec2[] = [];
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i];
    const b = poly[(i + 1) % poly.length];
    const edge: Vec2 = [b[0] - a[0], b[1] - a[1]];
    const len = Math.hypot(edge[0], edge[1]) || 1;
    axes.push([-edge[1] / len, edge[0] / len]); // normale unitaire
  }
  return axes;
}

/** Projection [min, max] d'un polygone sur un axe unitaire. */
function projectPoly(poly: Vec2[], axis: Vec2): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const [x, y] of poly) {
    const p = x * axis[0] + y * axis[1];
    if (p < min) min = p;
    if (p > max) max = p;
  }
  return [min, max];
}

/**
 * SAT (Separating Axis Theorem) — deux polygones CONVEXES se recouvrent-ils (aire commune
 * non nulle) ? Général (fonctionne pour tout angle) ; à angle 0 sur deux rectangles axés,
 * équivalent exact de `rectsOverlap`. Se toucher pile (séparation nulle) n'est PAS un
 * recouvrement — même tolérance que `rectsOverlap` (FREE_OVERLAP_EPS_M).
 */
export function polyOverlap(a: Vec2[], b: Vec2[]): boolean {
  const axes = [...polyAxes(a), ...polyAxes(b)];
  for (const axis of axes) {
    const [aMin, aMax] = projectPoly(a, axis);
    const [bMin, bMax] = projectPoly(b, axis);
    const gap = Math.max(bMin - aMax, aMin - bMax);
    if (gap >= -FREE_OVERLAP_EPS_M) return false; // un axe sépare (ou contact pile) → pas de recouvrement
  }
  return true;
}

/** Séparation (m) entre deux polygones convexes disjoints : 0 s'ils se recouvrent/touchent,
 *  sinon la distance minimale coin-à-arête (les deux sens — suffit pour deux convexes). */
export function polySeparation(a: Vec2[], b: Vec2[]): number {
  if (polyOverlap(a, b)) return 0;
  let min = Infinity;
  const edgesOf = (poly: Vec2[]): [Vec2, Vec2][] =>
    poly.map((p, i) => [p, poly[(i + 1) % poly.length]] as [Vec2, Vec2]);
  const distToEdges = (p: Vec2, edges: [Vec2, Vec2][]): number => {
    let d = Infinity;
    for (const [s, e] of edges) d = Math.min(d, distPointSeg(p, s, e));
    return d;
  };
  const edgesB = edgesOf(b);
  const edgesA = edgesOf(a);
  for (const p of a) min = Math.min(min, distToEdges(p, edgesB));
  for (const p of b) min = Math.min(min, distToEdges(p, edgesA));
  return min;
}

/**
 * Vérifie la rotation du panneau `idx` À SA POSITION ACTUELLE. Comme les autres contrôles de
 * ce module : DURE = sortie du contour / recouvrement / obstacle (jamais négociable) ;
 * RELÂCHABLE = retrait de rive / écart panneau (mêmes marges que le déplacement). CAL80 ne
 * refuse la rotation QUE sur une contrainte DURE réelle (`hard`) — l'appelant peut choisir de
 * l'autoriser même sous l'écart/retrait relâchable, exactement comme un déplacement.
 */
export function checkPanelRotation(
  state: FreeLayoutState,
  g: FreeGeom,
  idx: number,
  angleDeg: number,
  margins: FreeMargins,
): FreeCheck {
  if (idx < 0 || idx >= state.panels.length) return { ok: false, violations: ['outline'], hard: true, edgeM: 0, panelM: null };
  const p = state.panels[idx];
  const [cu, cv] = toUV(g, p.cx, p.cy);
  const corners = panelCornersUV(g, cu, cv, angleDeg);
  const violations: FreeViolation[] = [];
  const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));

  // — DURE 1 : entièrement dans le contour —
  let edgeM = Infinity;
  let outside = false;
  for (const c of corners) {
    const sd = signedInsideDist(c, ringUV);
    if (sd < edgeM) edgeM = sd;
    if (sd < -FREE_EDGE_EPS_M) outside = true;
  }
  // ringCrossesRect attend un RectUV AXÉ ; le panneau tourné est un polygone à 4 coins
  // quelconque, donc on rejoue directement son intersection de segments sur SES arêtes.
  const rectEdges: [Vec2, Vec2][] = corners.map((c, i) => [c, corners[(i + 1) % 4]] as [Vec2, Vec2]);
  let ringCrosses = false;
  for (let i = 0, j = ringUV.length - 1; i < ringUV.length && !ringCrosses; j = i++) {
    for (const [a, b] of rectEdges) {
      if (segmentsCross(ringUV[j], ringUV[i], a, b)) {
        ringCrosses = true;
        break;
      }
    }
  }
  if (outside || ringCrosses) violations.push('outline');

  // — DURE 2 : aucun recouvrement panneau-panneau (+ RELÂCHABLE : écart minimal) —
  let panelM: number | null = null;
  let overlaps = false;
  for (let i = 0; i < state.panels.length; i++) {
    if (i === idx) continue;
    const other = state.panels[i];
    const otherCorners = other.angleDeg
      ? panelCornersUV(g, ...toUV(g, other.cx, other.cy), other.angleDeg)
      : rectCorners(rectOfPanel(g, other));
    const sep = polySeparation(corners, otherCorners);
    if (panelM === null || sep < panelM) panelM = sep;
    if (polyOverlap(corners, otherCorners)) overlaps = true;
  }
  if (overlaps) violations.push('overlap');

  // — DURE 3 : obstacles —
  for (const o of g.obstacles) {
    if (o.ring.length < 3) continue;
    const ringO = o.ring.map(([x, y]) => toUV(g, x, y));
    // distance polygone-à-polygone (même esprit que distRectToPolygon, généralisé).
    const d = polyOverlap(corners, ringO) ? 0 : polySeparation(corners, ringO);
    if (d <= o.clearanceM) {
      violations.push('obstacle');
      break;
    }
  }

  if (!violations.includes('outline') && edgeM < margins.setbackM - FREE_EDGE_EPS_M) violations.push('setback');
  if (!overlaps && panelM !== null && panelM < margins.gapM - FREE_EDGE_EPS_M) violations.push('gap');

  const hard = violations.some((v) => v === 'outline' || v === 'overlap' || v === 'obstacle');
  return { ok: violations.length === 0, violations, hard, edgeM, panelM };
}

/**
 * Applique la rotation du panneau `idx` (ou d'un groupe, angle IDENTIQUE pour chaque membre —
 * une sélection tourne en bloc, chaque panneau autour de son PROPRE centre). TOUT OU RIEN :
 * refusée si un seul membre viole une contrainte DURE (`hard`) — jamais un chevauchement
 * réel, conformément au CAL80 : « refusée seulement si elle crée un chevauchement réel ».
 * Les contraintes RELÂCHABLES (retrait/écart) ne bloquent PAS la rotation, comme un déplacement
 * sous marge assouplie reste possible — seule une violation DURE (hard) refuse le geste.
 */
export function rotateFreePanels(
  state: FreeLayoutState,
  g: FreeGeom,
  indices: readonly number[],
  angleDeg: number,
  margins: FreeMargins,
): { ok: boolean; blocked?: FreeCheck; blockedIndex?: number } {
  const members = [...new Set(indices)].filter((i) => i >= 0 && i < state.panels.length);
  if (!members.length) return { ok: false };
  if (!Number.isFinite(angleDeg)) return { ok: false };
  for (const idx of members) {
    const chk = checkPanelRotation(state, g, idx, angleDeg, margins);
    if (chk.hard) return { ok: false, blocked: chk, blockedIndex: idx };
  }
  // Commit atomique : rien n'a été muté tant que tous les membres n'étaient pas validés.
  for (const idx of members) {
    state.panels[idx] = { ...state.panels[idx], angleDeg: ((angleDeg % 360) + 360) % 360 };
  }
  return { ok: true };
}

/** Résultat d'un déplacement libre : TOUT OU RIEN, comme en mode lattice. */
export interface FreeMoveResult {
  ok: boolean;
  /** Positions d'arrivée (même ordre que `indices`) — vide si refusé. */
  positions: { cx: number; cy: number }[];
  /** Le contrôle du PREMIER membre fautif (pour la note + le clignotement rouge). */
  blocked?: FreeCheck;
  /** Index du membre fautif. */
  blockedIndex?: number;
}

/** PV31 — un panneau et la position ABSOLUE où on veut le poser (repère ENU). */
export interface FreePlacement {
  index: number;
  cx: number;
  cy: number;
}

/**
 * PV31 — pose un lot de panneaux à des positions ABSOLUES. C'est la primitive commune du
 * déplacement : `moveFreePanels` (translation rigide) n'en est qu'un cas particulier, et
 * l'APERÇU VIVANT d'un glissé s'en sert pour rejouer le geste depuis les positions
 * d'ORIGINE à chaque image (sans jamais cumuler l'aperçu précédent, donc sans dérive).
 *
 * TOUT OU RIEN, exactement comme le mode lattice : si un seul membre viole une contrainte
 * à l'arrivée, rien n'est muté. Les membres s'ignorent entre eux à leur position de DÉPART
 * (ils la libèrent) et se voient à leur position d'ARRIVÉE (un lot ne peut pas se replier
 * sur lui-même).
 */
export function placeFreePanels(
  state: FreeLayoutState,
  g: FreeGeom,
  placements: readonly FreePlacement[],
  margins: FreeMargins,
): FreeMoveResult {
  const seen = new Set<number>();
  const wanted: FreePlacement[] = [];
  for (const p of placements) {
    if (!Number.isInteger(p.index) || p.index < 0 || p.index >= state.panels.length) continue;
    if (seen.has(p.index)) continue;
    if (!Number.isFinite(p.cx) || !Number.isFinite(p.cy)) return { ok: false, positions: [] };
    seen.add(p.index);
    wanted.push(p);
  }
  if (!wanted.length) return { ok: false, positions: [] };
  const ignore = seen;
  const placed: RectUV[] = [];
  const positions: { cx: number; cy: number }[] = [];
  for (const w of wanted) {
    const [cu, cv] = toUV(g, w.cx, w.cy);
    const r = rectAt(g, cu, cv);
    const chk = checkRect(state, g, r, margins, ignore, placed);
    if (!chk.ok) return { ok: false, positions: [], blocked: chk, blockedIndex: w.index };
    placed.push(r);
    positions.push({ cx: w.cx, cy: w.cy });
  }
  // Commit atomique : rien n'a été muté tant que tous les membres n'étaient pas validés.
  wanted.forEach((w, k) => {
    state.panels[w.index] = { ...state.panels[w.index], cx: positions[k].cx, cy: positions[k].cy };
  });
  return { ok: true, positions };
}

/**
 * Déplace un groupe de panneaux de (dx, dy) mètres ENU — RIGIDEMENT : tous les membres
 * subissent EXACTEMENT la même translation, donc une rangée reste une rangée et un
 * sous-ensemble se détache en gardant sa forme. TOUT OU RIEN : si un seul membre viole
 * une contrainte à l'arrivée, rien ne bouge et l'état n'est pas touché.
 *
 * Les membres du groupe s'ignorent entre eux à leur position de DÉPART (ils la libèrent)
 * et se voient à leur position d'ARRIVÉE (un groupe ne peut pas se replier sur lui-même).
 */
export function moveFreePanels(
  state: FreeLayoutState,
  g: FreeGeom,
  indices: readonly number[],
  dx: number,
  dy: number,
  margins: FreeMargins,
): FreeMoveResult {
  const members = [...new Set(indices)].filter((i) => i >= 0 && i < state.panels.length);
  if (!members.length) return { ok: false, positions: [] };
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return { ok: false, positions: [] };
  return placeFreePanels(
    state,
    g,
    members.map((i) => ({ index: i, cx: state.panels[i].cx + dx, cy: state.panels[i].cy + dy })),
    margins,
  );
}

/** PV31 — rectangle de sélection en ENU, coins dans n'importe quel ordre. */
export interface RectENU {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

/** PV31 — normalise les deux coins d'un cadre tracé à la souris/au doigt (le geste peut
 *  partir de n'importe quel coin, y compris vers le haut ou vers la gauche). */
export function normalizeRectENU(x0: number, y0: number, x1: number, y1: number): RectENU {
  return {
    xMin: Math.min(x0, x1),
    xMax: Math.max(x0, x1),
    yMin: Math.min(y0, y1),
    yMax: Math.max(y0, y1),
  };
}

/**
 * PV31 — panneaux dont le CENTRE tombe dans le cadre. Le critère « centre dedans » (et non
 * « panneau entièrement dedans ») est celui qu'attend un opérateur : on encadre grossièrement
 * une rangée et elle est prise, sans devoir englober chaque bord au pixel près.
 */
export function panelsInRectENU(
  panels: readonly { cx: number; cy: number }[],
  rect: RectENU,
): number[] {
  const out: number[] = [];
  for (let i = 0; i < panels.length; i++) {
    const p = panels[i];
    if (p.cx < rect.xMin || p.cx > rect.xMax || p.cy < rect.yMin || p.cy > rect.yMax) continue;
    out.push(i);
  }
  return out;
}

/** Pose un NOUVEAU panneau au point ENU visé. Refus (rien n'est ajouté) si une contrainte
 *  est violée — le verdict porte la raison, pour une note honnête. */
export function addFreePanel(
  state: FreeLayoutState,
  g: FreeGeom,
  cx: number,
  cy: number,
  margins: FreeMargins,
  face?: 'E' | 'W',
): { ok: boolean; index: number; check: FreeCheck } {
  const [cu, cv] = toUV(g, cx, cy);
  const check = checkRect(state, g, rectAt(g, cu, cv), margins);
  if (!check.ok) return { ok: false, index: -1, check };
  state.panels.push(face ? { cx, cy, face } : { cx, cy });
  return { ok: true, index: state.panels.length - 1, check };
}

/** Retire le panneau d'index `idx`. */
export function removeFreePanel(state: FreeLayoutState, idx: number): boolean {
  if (!Number.isInteger(idx) || idx < 0 || idx >= state.panels.length) return false;
  state.panels.splice(idx, 1);
  return true;
}

/**
 * Cherche un emplacement LIBRE pour un panneau de plus, en balayant le repère (u, v) au
 * pas indiqué. Sert au bouton « + » quand l'utilisateur n'a pas désigné d'endroit : on ne
 * devine jamais une position « au jugé », on prend la PREMIÈRE qui satisfait réellement
 * toutes les contraintes. Renvoie null si le toit est plein aux marges courantes.
 */
export function findFreeSpot(
  state: FreeLayoutState,
  g: FreeGeom,
  margins: FreeMargins,
  stepM = 0.1,
): { cx: number; cy: number } | null {
  const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
  if (ringUV.length < 3) return null;
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [uu, vv] of ringUV) {
    if (uu < uMin) uMin = uu;
    if (uu > uMax) uMax = uu;
    if (vv < vMin) vMin = vv;
    if (vv > vMax) vMax = vv;
  }
  const step = Number.isFinite(stepM) && stepM > 0 ? stepM : 0.1;
  // Garde-fou : un toit immense au pas de 10 cm ne doit pas figer le navigateur.
  const maxSteps = 400;
  const du = Math.max(step, (uMax - uMin) / maxSteps);
  const dv = Math.max(step, (vMax - vMin) / maxSteps);
  for (let v = vMin + g.depthM / 2; v <= vMax - g.depthM / 2; v += dv) {
    for (let u = uMin + g.widthM / 2; u <= uMax - g.widthM / 2; u += du) {
      if (checkRect(state, g, rectAt(g, u, v), margins).ok) {
        const [cx, cy] = toENU(g, u, v);
        return { cx, cy };
      }
    }
  }
  return null;
}

// ═══════════ CAL81 — aimantation + aligner/distribuer ═══════════
// Le placement libre se calait déjà sur un pas de STABILITÉ (FREE_STEP_M, freeMode.ts) mais
// sur AUCUNE arête ni aucun autre panneau — l'aimantation propose une position CANDIDATE
// (jamais imposée : hors seuil, la position demandée ressort inchangée) que l'appelant valide
// ensuite normalement via `placeFreePanels`/`moveFreePanels`.

/** Position candidate après aimantation (u, v) — `snapped` dit si au moins un axe a accroché. */
export interface SnapResult {
  cu: number;
  cv: number;
  snapped: boolean;
}

/**
 * CAL81 — propose une position aimantée pour le panneau `idx` visant (cu, cv) : accroche
 * indépendamment sur u et v au candidat le plus proche dans `thresholdM`, parmi (a) les bords
 * du toit (le panneau vient tangenter la rive) et (b) le bord d'un AUTRE panneau (bord à bord,
 * écart nul — l'utilisateur resserre ensuite lui-même s'il veut un jeu). Repère (u, v) —
 * même hypothèse que tout ce module : tous les panneaux partagent les dimensions de `g`.
 */
export function snapCandidateForPanel(
  state: FreeLayoutState,
  g: FreeGeom,
  idx: number,
  cu: number,
  cv: number,
  thresholdM: number,
): SnapResult {
  const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [u, v] of ringUV) {
    if (u < uMin) uMin = u;
    if (u > uMax) uMax = u;
    if (v < vMin) vMin = v;
    if (v > vMax) vMax = v;
  }
  const hw = g.widthM / 2;
  const hd = g.depthM / 2;
  const uTargets: number[] = [uMin + hw, uMax - hw];
  const vTargets: number[] = [vMin + hd, vMax - hd];
  for (let i = 0; i < state.panels.length; i++) {
    if (i === idx) continue;
    const [ou, ov] = toUV(g, state.panels[i].cx, state.panels[i].cy);
    uTargets.push(ou - hw - hw, ou + hw + hw);
    vTargets.push(ov - hd - hd, ov + hd + hd);
  }
  const nearest = (value: number, targets: number[]): { v: number; snapped: boolean } => {
    let best = value;
    let bestDist = Infinity;
    let snapped = false;
    for (const t of targets) {
      const d = Math.abs(t - value);
      if (d <= thresholdM && d < bestDist) {
        bestDist = d;
        best = t;
        snapped = true;
      }
    }
    return { v: best, snapped };
  };
  const su = nearest(cu, uTargets);
  const sv = nearest(cv, vTargets);
  return { cu: su.v, cv: sv.v, snapped: su.snapped || sv.snapped };
}

/**
 * CAL81 — « aligner » : cale la sélection sur l'axe du PREMIER membre — 'row' aligne v (une
 * rangée droite), 'col' aligne u (une colonne droite). TOUT OU RIEN (`placeFreePanels`) :
 * refusé si un seul membre viole une contrainte à sa nouvelle position.
 */
export function alignPanels(
  state: FreeLayoutState,
  g: FreeGeom,
  indices: readonly number[],
  axis: 'row' | 'col',
  margins: FreeMargins,
): FreeMoveResult {
  const members = [...new Set(indices)].filter((i) => i >= 0 && i < state.panels.length);
  if (members.length < 2) return { ok: false, positions: [] };
  const [refU, refV] = toUV(g, state.panels[members[0]].cx, state.panels[members[0]].cy);
  const placements: FreePlacement[] = members.map((idx) => {
    const [u, v] = toUV(g, state.panels[idx].cx, state.panels[idx].cy);
    const newU = axis === 'col' ? refU : u;
    const newV = axis === 'row' ? refV : v;
    const [cx, cy] = toENU(g, newU, newV);
    return { index: idx, cx, cy };
  });
  return placeFreePanels(state, g, placements, margins);
}

/**
 * CAL81 — « distribuer » : répartit la sélection à ÉCART ÉGAL sur l'axe u entre ses deux
 * membres extrêmes (qui ne bougent pas), chaque panneau gardant sa propre coordonnée v.
 * TOUT OU RIEN : refusé si la répartition créerait un chevauchement/une sortie de contour.
 */
export function distributePanels(
  state: FreeLayoutState,
  g: FreeGeom,
  indices: readonly number[],
  margins: FreeMargins,
): FreeMoveResult {
  const members = [...new Set(indices)].filter((i) => i >= 0 && i < state.panels.length);
  if (members.length < 3) return { ok: false, positions: [] };
  const withUV = members.map((idx) => {
    const [u, v] = toUV(g, state.panels[idx].cx, state.panels[idx].cy);
    return { idx, u, v };
  });
  withUV.sort((a, b) => a.u - b.u);
  const uMin = withUV[0].u;
  const uMax = withUV[withUV.length - 1].u;
  const step = (uMax - uMin) / (withUV.length - 1);
  const placements: FreePlacement[] = withUV.map((w, i) => {
    const newU = uMin + i * step;
    const [cx, cy] = toENU(g, newU, w.v);
    return { index: w.idx, cx, cy };
  });
  return placeFreePanels(state, g, placements, margins);
}

/** Copie PROFONDE d'un état libre (photo d'historique — jamais une référence partagée). */
export function copyFreeState(state: FreeLayoutState): FreeLayoutState {
  return { panels: state.panels.map((p) => ({ ...p })) };
}

/** État libre construit depuis des centres déjà posés (bascule depuis le mode lattice,
 *  ou hydratation d'un dossier enregistré en placement libre). */
export function freeStateFrom(panels: readonly FreePanel[]): FreeLayoutState {
  return { panels: panels.map((p) => ({ ...p })) };
}
