/**
 * W69 — LOGIQUE PURE de la VARIABILITÉ de disposition (« Personnaliser la disposition »)
 * de l'estimateur toiture pro-11. Tout ici est testable HORS DOM et HORS 3D : la
 * construction de la LATTICE de placements valides (les cellules que l'optimiseur a déjà
 * validées), l'occupation, le SNAP d'un déplacement vers la cellule VIDE valide la plus
 * proche, le rejet des cibles invalides (hors lattice / cellule occupée), l'ajout et la
 * suppression d'un panneau, et la réinitialisation à la disposition optimale.
 *
 * GARANTIE « valide par construction » : la lattice est exactement la liste des
 * `PackedPanel` produite par `packCells` (estimatorBrainV2) — chaque cellule est DÉJÀ
 * garantie dans le polygone tracé, à l'intérieur du retrait de rive, et hors zone
 * d'obstacle (avec dégagement), pas de chevauchement, coplanaire en pente, pas de rangée
 * préservé sur le plat. Donc TOUTE cellule de la lattice est physiquement valide, et un
 * déplacement qui ne fait que CHANGER l'index de cellule occupée ne peut JAMAIS produire
 * une disposition impossible. Le SNAP rejette par construction tout ce qui n'est pas une
 * cellule de la lattice.
 *
 * La PRODUCTION/les économies ne sont PAS recalculées ici : déplacer des panneaux dans le
 * MÊME plan laisse le rendement par panneau INCHANGÉ (même inclinaison/azimut/GPS) — seul
 * le NOMBRE change la production, par le chemin PVGIS-par-comptage existant. Ce module ne
 * renvoie donc que des INDEX de cellules + un comptage ; l'appelant recompute via l'engine.
 */

/** Une cellule de la lattice = un emplacement de panneau valide (coordonnées ENU). */
export interface LatticeCell {
  /** Index stable de la cellule dans la lattice (0-based, ordre du pavage). */
  index: number;
  /** Centre ENU (mètres) — le même repère que `PackedPanel.cx/cy`. */
  cx: number;
  cy: number;
  /** Sens de la pente pour le rendu Est-Ouest (chevrons), repris tel quel. */
  face?: 'E' | 'W';
}

/** Source minimale d'une cellule (compatible `PackedPanel` d'estimatorBrainV2). */
export interface PackedLike {
  cx: number;
  cy: number;
  face?: 'E' | 'W';
}

/**
 * État d'une disposition personnalisable : la lattice complète (toutes les cellules
 * valides qui tiennent sur ce toit) + l'ensemble des index OCCUPÉS. Au départ, les
 * `initialCount` premières cellules sont occupées (la disposition de l'optimiseur).
 */
export interface LayoutState {
  cells: LatticeCell[];
  /** Index occupés (sous-ensemble de [0, cells.length)). */
  occupied: Set<number>;
}

/** Construit la lattice à partir des cellules pavées (toutes valides par construction). */
export function buildLattice(packed: PackedLike[]): LatticeCell[] {
  return packed.map((p, index) => ({ index, cx: p.cx, cy: p.cy, face: p.face }));
}

/**
 * Crée l'état initial : lattice = `packed` (toutes les cellules qui tiennent), et les
 * `initialCount` PREMIÈRES cellules occupées (la disposition optimale, dans l'ordre du
 * pavage). `initialCount` borné à [0, lattice.length].
 */
export function createLayoutState(packed: PackedLike[], initialCount: number): LayoutState {
  const cells = buildLattice(packed);
  const n = Math.max(0, Math.min(cells.length, Math.trunc(Number.isFinite(initialCount) ? initialCount : 0)));
  const occupied = new Set<number>();
  for (let i = 0; i < n; i++) occupied.add(i);
  return { cells, occupied };
}

/** Nombre de panneaux posés (cellules occupées). */
export function occupiedCount(state: LayoutState): number {
  return state.occupied.size;
}

/** Index occupés, triés (ordre stable pour le rendu). */
export function occupiedIndices(state: LayoutState): number[] {
  return [...state.occupied].sort((a, b) => a - b);
}

/** Index VIDES (cellules valides non occupées), triés. */
export function emptyIndices(state: LayoutState): number[] {
  const out: number[] = [];
  for (const c of state.cells) if (!state.occupied.has(c.index)) out.push(c.index);
  return out;
}

/** Une cellule existe-t-elle dans la lattice ? (index dans [0, length)). */
export function isLatticeCell(state: LayoutState, index: number): boolean {
  return Number.isInteger(index) && index >= 0 && index < state.cells.length;
}

/** Une cellule est-elle VALIDE comme cible (existe ET vide) ? */
export function isValidEmptyTarget(state: LayoutState, index: number): boolean {
  return isLatticeCell(state, index) && !state.occupied.has(index);
}

/** Distance ENU² entre deux cellules (au carré : suffit pour comparer/trier). */
function dist2(a: LatticeCell, b: { cx: number; cy: number }): number {
  const dx = a.cx - b.cx;
  const dy = a.cy - b.cy;
  return dx * dx + dy * dy;
}

/**
 * Cellule de la lattice la plus proche d'un point ENU (toutes cellules confondues).
 * Renvoie son index, ou -1 si la lattice est vide. Sert au raycast → snap.
 */
export function nearestCell(state: LayoutState, x: number, y: number): number {
  let best = -1;
  let bestD = Infinity;
  for (const c of state.cells) {
    const d = dist2(c, { cx: x, cy: y });
    if (d < bestD) {
      bestD = d;
      best = c.index;
    }
  }
  return best;
}

/**
 * Cellule VIDE valide la plus proche d'un point ENU. Renvoie son index, ou -1 s'il
 * n'existe aucune cellule vide. C'est la cible d'un déplacement : on ne peut atterrir
 * QUE sur une cellule vide valide → toute position atteignable est valide par construction.
 */
export function nearestEmptyCell(state: LayoutState, x: number, y: number): number {
  let best = -1;
  let bestD = Infinity;
  for (const c of state.cells) {
    if (state.occupied.has(c.index)) continue;
    const d = dist2(c, { cx: x, cy: y });
    if (d < bestD) {
      bestD = d;
      best = c.index;
    }
  }
  return best;
}

/** Résultat d'un déplacement : la cellule cible (snap) et si le déplacement a réussi. */
export interface MoveResult {
  ok: boolean;
  /** Cellule d'arrivée (snap) — −1 si aucun déplacement possible. */
  toIndex: number;
}

/**
 * Déplace le panneau de la cellule `fromIndex` vers la cellule VIDE valide la plus proche
 * du point ENU visé (raycast → snap). Le déplacement n'aboutit QUE sur une cellule vide
 * valide ; sinon il échoue (snap-back, l'appelant garde l'ancienne position). Si la cible
 * la plus proche est la cellule de départ elle-même (rien de plus proche de vide), le
 * panneau reste sur place (ok=true, toIndex=fromIndex). MUTE l'état en cas de succès.
 */
export function movePanelToPoint(state: LayoutState, fromIndex: number, x: number, y: number): MoveResult {
  if (!state.occupied.has(fromIndex)) return { ok: false, toIndex: -1 };
  // Cible = la cellule VIDE valide la plus proche, AUTRES cellules que celle de départ
  // (la cellule de départ reste occupée pendant la recherche). Aucune autre cellule vide
  // (toit plein) → snap-back : le panneau reste sur place et le déplacement échoue (signal
  // « rien de libre » pour le retour visuel rouge).
  const target = nearestEmptyCell(state, x, y);
  if (target < 0) return { ok: false, toIndex: fromIndex };
  state.occupied.delete(fromIndex);
  state.occupied.add(target);
  return { ok: true, toIndex: target };
}

/**
 * Déplace explicitement vers `toIndex` (mode tap-cible / clavier). N'aboutit QUE si
 * `toIndex` est une cellule VIDE valide ET `fromIndex` occupée. MUTE l'état en cas de
 * succès. Cibles invalides (hors lattice, occupées) → rejet (ok=false), aucun changement.
 */
export function movePanelToCell(state: LayoutState, fromIndex: number, toIndex: number): MoveResult {
  if (!state.occupied.has(fromIndex)) return { ok: false, toIndex: -1 };
  if (fromIndex === toIndex) return { ok: true, toIndex };
  if (!isValidEmptyTarget(state, toIndex)) return { ok: false, toIndex: -1 };
  state.occupied.delete(fromIndex);
  state.occupied.add(toIndex);
  return { ok: true, toIndex };
}

/**
 * AJOUTE un panneau sur la cellule VIDE valide `index`. Rejet si la cellule n'existe pas,
 * est déjà occupée, ou si le plafond `cap` (besoin/footprint) est atteint. `cap` ≤ 0 =
 * aucun plafond explicite (on reste borné par la lattice de toute façon). MUTE en cas de
 * succès. Renvoie le nouveau comptage et si l'ajout a réussi.
 */
export function addPanel(state: LayoutState, index: number, cap = 0): { ok: boolean; count: number } {
  if (!isValidEmptyTarget(state, index)) return { ok: false, count: state.occupied.size };
  if (cap > 0 && state.occupied.size >= cap) return { ok: false, count: state.occupied.size };
  state.occupied.add(index);
  return { ok: true, count: state.occupied.size };
}

/**
 * AJOUTE un panneau sur la PREMIÈRE cellule vide valide (la plus basse dans l'ordre du
 * pavage) — utile pour le bouton « + » qui n'a pas de cible précise. Mêmes garde-fous.
 */
export function addFirstEmpty(state: LayoutState, cap = 0): { ok: boolean; count: number } {
  const empties = emptyIndices(state);
  if (empties.length === 0) return { ok: false, count: state.occupied.size };
  return addPanel(state, empties[0], cap);
}

/**
 * SUPPRIME le panneau de la cellule `index` (doit être occupée). MUTE en cas de succès.
 * On autorise à descendre jusqu'à 0 (la production/les économies baissent honnêtement —
 * l'appelant signale alors que la disposition ne couvre plus le besoin).
 */
export function removePanel(state: LayoutState, index: number): { ok: boolean; count: number } {
  if (!state.occupied.has(index)) return { ok: false, count: state.occupied.size };
  state.occupied.delete(index);
  return { ok: true, count: state.occupied.size };
}

/**
 * SUPPRIME le panneau le plus HAUT dans l'ordre du pavage (la dernière cellule occupée) —
 * utile pour le bouton « − » sans sélection. Renvoie le nouveau comptage.
 */
export function removeLast(state: LayoutState): { ok: boolean; count: number } {
  const occ = occupiedIndices(state);
  if (occ.length === 0) return { ok: false, count: 0 };
  return removePanel(state, occ[occ.length - 1]);
}

/**
 * RÉINITIALISE la disposition à l'optimum : les `optimalCount` premières cellules
 * occupées, le reste vide (l'ordre du pavage = la disposition de l'optimiseur). MUTE
 * l'état. `optimalCount` borné à [0, length].
 */
export function resetToOptimal(state: LayoutState, optimalCount: number): void {
  const n = Math.max(0, Math.min(state.cells.length, Math.trunc(Number.isFinite(optimalCount) ? optimalCount : 0)));
  state.occupied.clear();
  for (let i = 0; i < n; i++) state.occupied.add(i);
}

/**
 * WJ20 — REMPLISSAGE AUTOMATIQUE : occupe TOUTES les cellules valides de la lattice
 * (le toit entier, moins retraits de rive + zones d'obstacle, déjà exclus par
 * construction). Un seul geste remplace le placement manuel panneau-par-panneau : la
 * lattice EST exactement le pavage géométrique validé par l'optimiseur, donc « tout
 * remplir » = poser un panneau sur chaque emplacement physiquement valide, sans jamais
 * dépasser la surface utile (Σ empreintes ≤ surface utile, garanti par la lattice).
 *
 * Renvoie le comptage résultant (= cells.length). MUTE l'état. Aucun chiffre inventé :
 * on ne fait qu'ajouter des cellules DÉJÀ validées par le packing. Le besoin (bill) ne
 * borne PAS ce remplissage — c'est l'action « poser le maximum qui tient » ; l'appelant
 * signale si cela dépasse le besoin (surproduction non rémunérée) via ses readouts.
 */
export function fillAll(state: LayoutState): { ok: boolean; count: number } {
  const before = state.occupied.size;
  for (const c of state.cells) state.occupied.add(c.index);
  return { ok: state.occupied.size > before, count: state.occupied.size };
}

/**
 * INVARIANT de cohérence : tout index occupé est une cellule valide de la lattice, et le
 * comptage ne dépasse jamais la taille de la lattice (le plafond footprint/besoin tient
 * par construction puisque la lattice = le pavage capé). Utilisé par les tests + une
 * garde défensive côté appelant.
 */
export function layoutIsValid(state: LayoutState, cap = 0): boolean {
  if (state.occupied.size > state.cells.length) return false;
  for (const idx of state.occupied) {
    if (!isLatticeCell(state, idx)) return false;
  }
  if (cap > 0 && state.occupied.size > cap) return false;
  return true;
}
