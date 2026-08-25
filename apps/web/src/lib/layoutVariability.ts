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

// ═══════════ PV25 — SÉLECTION MULTIPLE, DÉPLACEMENT DE GROUPE ET DE RANGÉE ═══════════
// Tout reste dans le MÊME cadre de sécurité que le déplacement d'un panneau : on ne fait
// que changer les INDEX de cellules occupées, et toute cellule de la lattice est valide
// par construction. Un groupe ne peut donc jamais atterrir dans un obstacle ou hors toit.

/** Rectangle de sélection en ENU (mètres). Les coins peuvent être donnés dans n'importe
 *  quel ordre : la fonction normalise. */
export interface EnuRect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/**
 * PV25 — cellules dont le CENTRE tombe dans le rectangle (marquee). Par défaut on ne
 * renvoie que les cellules OCCUPÉES (on sélectionne des panneaux, pas du vide). Indices
 * triés — l'ordre de la lattice, donc un rendu stable.
 */
export function cellsInRect(state: LayoutState, rect: EnuRect, occupiedOnly = true): number[] {
  const xMin = Math.min(rect.x0, rect.x1);
  const xMax = Math.max(rect.x0, rect.x1);
  const yMin = Math.min(rect.y0, rect.y1);
  const yMax = Math.max(rect.y0, rect.y1);
  const out: number[] = [];
  for (const c of state.cells) {
    if (occupiedOnly && !state.occupied.has(c.index)) continue;
    if (c.cx < xMin || c.cx > xMax || c.cy < yMin || c.cy > yMax) continue;
    out.push(c.index);
  }
  return out.sort((a, b) => a - b);
}

/** Résultat d'un déplacement de GROUPE : tout ou rien. */
export interface GroupMoveResult {
  ok: boolean;
  /** Cellules d'arrivée (même ordre que les membres fournis) — vide si refusé. */
  targets: number[];
  /** Pourquoi c'est refusé (diagnostic pour la note de l'interface). */
  reason?: 'empty' | 'not-occupied' | 'no-target';
}

/**
 * PV25 — déplace TOUT un groupe de panneaux de (dx, dy) mètres. Règle absolue :
 * TOUT OU RIEN. On calcule d'abord la cellule d'arrivée de CHAQUE membre (la cellule
 * libre valide la plus proche de sa position translatée, les cellules du groupe étant
 * considérées comme libérées, sans qu'aucune ne soit prise deux fois) ; si UN SEUL membre
 * n'a pas de cible valide — ou atterrit trop loin de sa position visée (`maxSnapM`) —, le
 * déplacement est REFUSÉ et l'état n'est pas touché du tout. Un demi-groupe déplacé serait
 * un calepinage que l'utilisateur n'a pas dessiné.
 */
export function moveGroup(
  state: LayoutState,
  indices: readonly number[],
  dx: number,
  dy: number,
  opts: { maxSnapM?: number } = {},
): GroupMoveResult {
  const plan = planGroupMove(state, indices, dx, dy, opts);
  if (!plan.ok) return plan;
  // Commit atomique : on n'a touché à rien tant que tous les membres n'avaient pas de cible.
  for (const i of plan.members) state.occupied.delete(i);
  for (const t of plan.targets) state.occupied.add(t);
  return { ok: plan.ok, targets: plan.targets };
}

/** Plan d'un déplacement de groupe : le résultat, plus les membres dans l'ordre des cibles. */
export interface GroupMovePlan extends GroupMoveResult {
  /** Membres dédoublonnés, dans le MÊME ordre que `targets`. Vide si refusé. */
  members: number[];
}

/**
 * PV34 — CALCUL SEUL du déplacement de groupe : mêmes règles exactes que `moveGroup`
 * (tout ou rien, cellules du groupe considérées comme libérées, aucune cellule prise
 * deux fois, refus au-delà de `maxSnapM`) mais SANS toucher à l'état. C'est ce que
 * l'APERÇU VIVANT d'un glissé appelle à chaque image : il doit montrer où le groupe
 * atterrirait sans jamais committer quoi que ce soit tant que le doigt n'est pas
 * relâché. `moveGroup` n'est plus que « ce plan, puis on l'applique » — les deux ne
 * peuvent donc pas diverger.
 */
export function planGroupMove(
  state: LayoutState,
  indices: readonly number[],
  dx: number,
  dy: number,
  opts: { maxSnapM?: number } = {},
): GroupMovePlan {
  const members = [...new Set(indices)];
  if (members.length === 0) return { ok: false, targets: [], members: [], reason: 'empty' };
  for (const i of members) if (!state.occupied.has(i)) return { ok: false, targets: [], members: [], reason: 'not-occupied' };
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return { ok: false, targets: [], members: [], reason: 'no-target' };
  const maxSnap = Number.isFinite(opts.maxSnapM as number) ? (opts.maxSnapM as number) : Infinity;

  const group = new Set(members);
  const taken = new Set<number>();
  const targets: number[] = [];
  for (const i of members) {
    const cell = state.cells[i];
    const wantX = cell.cx + dx;
    const wantY = cell.cy + dy;
    let best = -1;
    let bestD = Infinity;
    for (const c of state.cells) {
      // Cible admissible : une cellule libre, ou une cellule du groupe (qui se libère),
      // et jamais une cellule déjà attribuée à un autre membre.
      if (taken.has(c.index)) continue;
      if (state.occupied.has(c.index) && !group.has(c.index)) continue;
      const d = (c.cx - wantX) ** 2 + (c.cy - wantY) ** 2;
      if (d < bestD) {
        bestD = d;
        best = c.index;
      }
    }
    if (best < 0 || Math.sqrt(bestD) > maxSnap) return { ok: false, targets: [], members: [], reason: 'no-target' };
    taken.add(best);
    targets.push(best);
  }
  return { ok: true, targets, members };
}

/** Tolérance (m) par défaut pour considérer deux panneaux sur la MÊME rangée. */
export const ROW_EPSILON_M = 0.5;

/**
 * PV25 — les panneaux de la MÊME RANGÉE que `index` : les cellules OCCUPÉES dont le
 * centre partage la même coordonnée `cy` à `epsilonM` près (les rangées sont empilées
 * selon cet axe). Inclut `index` lui-même. Rangée vide (index non occupé) → [].
 */
export function rowMembers(state: LayoutState, index: number, epsilonM = ROW_EPSILON_M): number[] {
  if (!state.occupied.has(index)) return [];
  const ref = state.cells[index];
  if (!ref) return [];
  const out: number[] = [];
  for (const c of state.cells) {
    if (!state.occupied.has(c.index)) continue;
    if (Math.abs(c.cy - ref.cy) <= epsilonM) out.push(c.index);
  }
  return out.sort((a, b) => a - b);
}

/**
 * PV25 — glisse une RANGÉE ENTIÈRE de `dx` mètres. Le déplacement est CONTRAINT à l'axe
 * de la rangée (aucune composante en `y`) : une rangée reste une rangée, on ne la fait pas
 * dériver entre deux pas d'espacement solaire. Tout ou rien, comme `moveGroup`.
 */
export function moveRowBy(
  state: LayoutState,
  index: number,
  dx: number,
  opts: { maxSnapM?: number; epsilonM?: number } = {},
): GroupMoveResult {
  const members = rowMembers(state, index, opts.epsilonM ?? ROW_EPSILON_M);
  if (!members.length) return { ok: false, targets: [], reason: 'not-occupied' };
  return moveGroup(state, members, dx, 0, { maxSnapM: opts.maxSnapM });
}

/**
 * PV25 — azimut nudgé de `deltaDeg`, ramené dans [0, 360). PURE : la valeur sert au
 * ré-calcul (le calepinage suit la nouvelle face), jamais arrondie à un pas imposé —
 * l'appelant choisit son incrément.
 */
export function nudgeAzimuthDeg(currentDeg: number, deltaDeg: number): number {
  const base = Number.isFinite(currentDeg) ? currentDeg : 0;
  const d = Number.isFinite(deltaDeg) ? deltaDeg : 0;
  return ((base + d) % 360 + 360) % 360;
}

/**
 * PV28 — la disposition courante DIVERGE-T-ELLE de l'optimum ? On compare l'occupation
 * réelle à celle que produirait `resetToOptimal(optimalCount)` (les `optimalCount`
 * premières cellules). Vrai dès qu'un panneau a été ajouté, retiré ou déplacé à la main :
 * c'est le signal qu'un ré-agencement automatique DÉTRUIRAIT un travail manuel, et donc
 * qu'il faut demander confirmation AVANT. Pas de notion de « panneau verrouillé » : on
 * ne fige rien, on prévient.
 */
export function hasManualEdits(state: LayoutState | null | undefined, optimalCount: number): boolean {
  if (!state) return false;
  const n = Math.max(0, Math.min(state.cells.length, Math.trunc(Number.isFinite(optimalCount) ? optimalCount : 0)));
  if (state.occupied.size !== n) return true;
  for (let i = 0; i < n; i++) if (!state.occupied.has(i)) return true;
  return false;
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
