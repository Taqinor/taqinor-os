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

/** Copie PROFONDE d'un état libre (photo d'historique — jamais une référence partagée). */
export function copyFreeState(state: FreeLayoutState): FreeLayoutState {
  return { panels: state.panels.map((p) => ({ ...p })) };
}

/** État libre construit depuis des centres déjà posés (bascule depuis le mode lattice,
 *  ou hydratation d'un dossier enregistré en placement libre). */
export function freeStateFrom(panels: readonly FreePanel[]): FreeLayoutState {
  return { panels: panels.map((p) => ({ ...p })) };
}
