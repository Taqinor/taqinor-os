/**
 * PV34 — LOGIQUE PURE de la SÉLECTION de panneaux dans l'éditeur de calepinage.
 *
 * Pourquoi ce module existe (ordre fondateur du 25/08 : « i cannot select a group of
 * pannels or a raw ») : la sélection par cadre livrée en PV31 ne retenait que les
 * panneaux dont le CENTRE tombait dans le rectangle (`cellsInRect`,
 * `panelsInRectENU`). Encadrer GROSSIÈREMENT une rangée — le geste qu'un opérateur
 * fait réellement — n'attrapait donc rien dès que le cadre effleurait les panneaux
 * sans avaler leurs centres. On raisonne ici sur l'EMPRISE RÉELLE du panneau : est
 * sélectionné tout panneau que le cadre TRAVERSE.
 *
 * Tout est pur et testable hors DOM / hors 3D : aucune dépendance, aucun état.
 * Les deux modes d'édition (lattice « emplacements validés » et placement libre)
 * partagent ces fonctions — un panneau n'est ici qu'un centre ENU, et l'empreinte
 * (axes + dimensions) vient du plan de pavage courant (`FreeGeom`).
 */

/** Vecteur ENU (mètres) — même convention que `lib/freeLayout.ts`. */
export type Vec2 = [number, number];

/** Un centre de panneau en ENU (mètres) : la seule chose dont la sélection a besoin. */
export interface PanelCenter {
  cx: number;
  cy: number;
}

/** Cadre de sélection en ENU (mètres), coins déjà normalisés. */
export interface SelectRect {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

/**
 * EMPRISE d'un panneau : les deux axes du pavage (unitaires, ENU) et les dimensions
 * du panneau le long de chacun. C'est exactement le sous-ensemble de `FreeGeom` dont
 * la sélection a besoin — on ne duplique aucune trigonométrie, l'appelant passe le
 * `FreeGeom` du plan courant tel quel.
 */
export interface PanelFootprint {
  /** Axe long des rangées (unitaire, ENU). */
  u: Vec2;
  /** Axe d'empilement des rangées (unitaire, ENU), orthogonal à `u`. */
  s: Vec2;
  /** Largeur du panneau le long de `u` (m). */
  widthM: number;
  /** Empreinte au sol du panneau le long de `s` (m). */
  depthM: number;
}

/** Normalise les deux coins d'un cadre tracé à la souris (n'importe quel sens). */
export function normalizeSelectRect(x0: number, y0: number, x1: number, y1: number): SelectRect {
  return {
    xMin: Math.min(x0, x1),
    xMax: Math.max(x0, x1),
    yMin: Math.min(y0, y1),
    yMax: Math.max(y0, y1),
  };
}

/** Une empreinte est-elle exploitable ? (axes non dégénérés, dimensions > 0). */
function usableFootprint(fp: PanelFootprint | null | undefined): fp is PanelFootprint {
  if (!fp) return false;
  if (!Number.isFinite(fp.widthM) || !Number.isFinite(fp.depthM)) return false;
  if (!(fp.widthM > 0) || !(fp.depthM > 0)) return false;
  const [ux, uy] = fp.u ?? [NaN, NaN];
  const [sx, sy] = fp.s ?? [NaN, NaN];
  if (![ux, uy, sx, sy].every((v) => Number.isFinite(v))) return false;
  return ux * ux + uy * uy > 0 && sx * sx + sy * sy > 0;
}

/** Le centre tombe-t-il DANS le cadre ? (critère historique PV25/PV31, conservé comme
 *  repli quand le plan ne décrit pas d'empreinte de panneau). */
export function centerInRect(p: PanelCenter, rect: SelectRect): boolean {
  return p.cx >= rect.xMin && p.cx <= rect.xMax && p.cy >= rect.yMin && p.cy <= rect.yMax;
}

/**
 * PV34 — le cadre TRAVERSE-t-il le panneau ? Théorème des axes séparateurs entre le
 * cadre (aligné sur les axes ENU, c'est le geste écran) et le panneau (rectangle
 * ORIENTÉ selon les axes du pavage). Quatre axes suffisent : les deux du cadre et les
 * deux du panneau. Un simple contact compte comme une traversée — encadrer « juste au
 * bord » d'une rangée doit la prendre, pas la rater d'un centimètre.
 */
export function panelCrossesRect(p: PanelCenter, rect: SelectRect, fp: PanelFootprint | null): boolean {
  if (!Number.isFinite(p?.cx) || !Number.isFinite(p?.cy)) return false;
  if (!usableFootprint(fp)) return centerInRect(p, rect);
  const rcx = (rect.xMin + rect.xMax) / 2;
  const rcy = (rect.yMin + rect.yMax) / 2;
  const rhx = (rect.xMax - rect.xMin) / 2;
  const rhy = (rect.yMax - rect.yMin) / 2;
  const hu = fp.widthM / 2;
  const hs = fp.depthM / 2;
  const axes: Vec2[] = [[1, 0], [0, 1], fp.u, fp.s];
  for (const [ax, ay] of axes) {
    const norm = Math.hypot(ax, ay);
    if (!(norm > 0)) continue;
    const nx = ax / norm;
    const ny = ay / norm;
    // Rayon du cadre (boîte alignée) projeté sur l'axe.
    const rectR = Math.abs(nx) * rhx + Math.abs(ny) * rhy;
    // Rayon du panneau (boîte orientée) projeté sur l'axe.
    const panelR = hu * Math.abs(nx * fp.u[0] + ny * fp.u[1]) + hs * Math.abs(nx * fp.s[0] + ny * fp.s[1]);
    const gap = Math.abs((p.cx - rcx) * nx + (p.cy - rcy) * ny);
    if (gap > rectR + panelR) return false; // axe séparateur trouvé : aucun contact
  }
  return true;
}

/**
 * PV34 — index des panneaux TRAVERSÉS par le cadre, triés. `fp` nul (plan sans
 * empreinte exploitable) → repli exact sur le critère « centre dans le cadre », donc
 * strictement le comportement d'avant.
 */
export function panelsCrossingRect(
  panels: readonly PanelCenter[],
  rect: SelectRect,
  fp: PanelFootprint | null,
): number[] {
  const out: number[] = [];
  for (let i = 0; i < panels.length; i++) {
    if (panelCrossesRect(panels[i], rect, fp)) out.push(i);
  }
  return out;
}

/** Comment un nouveau lot de panneaux entre dans la sélection courante. */
export type SelectionMode = 'replace' | 'add' | 'toggle';

/**
 * PV34 — applique un lot de panneaux à la sélection courante. `replace` = clic nu,
 * `add` = cadre tracé en gardant le modificateur (on AJOUTE au groupe, on ne repart
 * pas de zéro), `toggle` = Ctrl/⌘ + clic sur un panneau (entre/sort du groupe).
 * Résultat toujours dédoublonné et trié : l'ordre de la sélection ne doit jamais
 * dépendre de l'ordre des gestes.
 */
export function applySelectionGesture(
  current: readonly number[],
  hits: readonly number[],
  mode: SelectionMode,
): number[] {
  if (mode === 'replace') return [...new Set(hits)].sort((a, b) => a - b);
  const next = new Set(current);
  if (mode === 'add') {
    for (const h of hits) next.add(h);
  } else {
    for (const h of hits) {
      if (next.has(h)) next.delete(h);
      else next.add(h);
    }
  }
  return [...next].sort((a, b) => a - b);
}

/**
 * PV34 — membres de la RANGÉE du panneau `index` : ceux qui partagent sa coordonnée
 * d'EMPILEMENT (projection sur l'axe `s` du pavage) à `toleranceM` près. Fonctionne
 * pour les deux modes puisqu'elle ne lit que des centres + les axes du plan — et
 * reste correcte sur un toit dont les rangées ne sont pas alignées sur le nord.
 * Sans empreinte exploitable, repli sur la coordonnée `cy` (les rangées de la lattice
 * s'empilent selon cet axe — critère historique `rowMembers`).
 */
export function rowMembersOf(
  panels: readonly PanelCenter[],
  index: number,
  fp: PanelFootprint | null,
  toleranceM?: number,
): number[] {
  if (!Number.isInteger(index) || index < 0 || index >= panels.length) return [];
  const ref = panels[index];
  if (!ref) return [];
  const useFp = usableFootprint(fp);
  const tol = Number.isFinite(toleranceM as number) && (toleranceM as number) > 0
    ? (toleranceM as number)
    : useFp
      ? (fp as PanelFootprint).depthM / 2
      : 0.5;
  const proj = (p: PanelCenter): number =>
    useFp ? p.cx * (fp as PanelFootprint).s[0] + p.cy * (fp as PanelFootprint).s[1] : p.cy;
  const refV = proj(ref);
  const out: number[] = [];
  for (let i = 0; i < panels.length; i++) {
    const p = panels[i];
    if (!Number.isFinite(p?.cx) || !Number.isFinite(p?.cy)) continue;
    if (Math.abs(proj(p) - refV) <= tol) out.push(i);
  }
  return out;
}

/**
 * PV34 — le point ENU tombe-t-il sur la ZONE DE CALEPINAGE ? (boîte englobante des
 * centres fournis, élargie de `marginM`). Sert à trancher un geste ambigu : un glissé
 * qui PART du toit trace un cadre de sélection ; un glissé qui part d'ailleurs reste
 * un déplacement de carte. Liste vide → false (rien à sélectionner, la carte garde
 * tous ses gestes).
 */
export function pointInLayoutArea(
  panels: readonly PanelCenter[],
  x: number,
  y: number,
  marginM = 0,
): boolean {
  if (!panels.length || !Number.isFinite(x) || !Number.isFinite(y)) return false;
  const m = Number.isFinite(marginM) && marginM > 0 ? marginM : 0;
  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  for (const p of panels) {
    if (!Number.isFinite(p?.cx) || !Number.isFinite(p?.cy)) continue;
    if (p.cx < xMin) xMin = p.cx;
    if (p.cx > xMax) xMax = p.cx;
    if (p.cy < yMin) yMin = p.cy;
    if (p.cy > yMax) yMax = p.cy;
  }
  if (!Number.isFinite(xMin) || !Number.isFinite(yMin)) return false;
  return x >= xMin - m && x <= xMax + m && y >= yMin - m && y <= yMax + m;
}
