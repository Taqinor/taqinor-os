/**
 * PV26 — HISTORIQUE (annuler / rétablir) de la disposition personnalisée.
 *
 * Modèle par SNAPSHOT, pas par commande inverse : chaque action de l'éditeur (ajouter,
 * retirer, déplacer un panneau, un groupe, une rangée, remplir, réinitialiser…) est
 * précédée d'une PHOTO de l'occupation (`Set<number>` des cellules posées), copiée en
 * profondeur. Annuler = ré-appliquer la photo précédente. C'est le seul modèle sûr ici :
 * l'occupation est un petit ensemble d'entiers, et une commande inverse devrait connaître
 * la sémantique de chaque geste (un déplacement de groupe refusé, un re-snap après
 * recalcul…) — une source de bugs pour rien.
 *
 * Le tampon est CIRCULAIRE (`limit`, 50 par défaut) : au-delà, la photo la plus ANCIENNE
 * est oubliée — l'historique ne peut pas grossir indéfiniment pendant une longue session
 * d'édition. Une nouvelle action VIDE la pile « rétablir » (on repart de la nouvelle
 * branche, comportement universel des éditeurs).
 *
 * Module PUR : aucun DOM, aucune carte, aucun état global — testé hors navigateur.
 */

/** Photo d'une occupation : la liste TRIÉE des index de cellules posées (JSON-sûre). */
export type LayoutSnapshot = number[];

export interface LayoutHistory {
  /** Enregistre l'état AVANT une action (à appeler juste avant de muter). Vide le redo. */
  push: (occupied: ReadonlySet<number>) => void;
  /** Y a-t-il quelque chose à annuler / rétablir ? */
  canUndo: () => boolean;
  canRedo: () => boolean;
  /** Annule : renvoie l'occupation à ré-appliquer (et empile `current` côté redo), ou null. */
  undo: (current: ReadonlySet<number>) => LayoutSnapshot | null;
  /** Rétablit : renvoie l'occupation à ré-appliquer (et empile `current` côté undo), ou null. */
  redo: (current: ReadonlySet<number>) => LayoutSnapshot | null;
  /** PV29 — JETTE la dernière photo empilée SANS la rejouer et SANS toucher au « rétablir ».
   *  Sert exactement à un cas : l'action a été photographiée puis REFUSÉE (déplacement de
   *  groupe/rangée qui ne tient pas). Un geste refusé n'a rien changé, donc il n'a rien à
   *  annuler — sans ça, « annuler » consomme un pas pour ne rien faire et « rétablir »
   *  s'allume pour rien. Renvoie true si une photo a été jetée. */
  drop: () => boolean;
  /** Oublie tout (changement de toit / de zone / sortie du mode disposition). */
  clear: () => void;
  /** Profondeur des deux piles (diagnostic + tests). */
  size: () => { undo: number; redo: number };
}

/** Profondeur par défaut du tampon circulaire. */
export const LAYOUT_HISTORY_LIMIT = 50;

/** Copie PROFONDE d'une occupation (jamais une référence partagée avec l'état vivant). */
function snapshotOf(occupied: ReadonlySet<number>): LayoutSnapshot {
  return [...occupied].sort((a, b) => a - b);
}

export function createLayoutHistory(limit: number = LAYOUT_HISTORY_LIMIT): LayoutHistory {
  const cap = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : LAYOUT_HISTORY_LIMIT;
  let undoStack: LayoutSnapshot[] = [];
  let redoStack: LayoutSnapshot[] = [];

  return {
    push(occupied) {
      undoStack.push(snapshotOf(occupied));
      // Tampon circulaire : au-delà de `cap`, la photo la PLUS ANCIENNE est oubliée.
      if (undoStack.length > cap) undoStack = undoStack.slice(undoStack.length - cap);
      // Une nouvelle action ouvre une nouvelle branche : plus rien à rétablir.
      redoStack = [];
    },
    canUndo: () => undoStack.length > 0,
    canRedo: () => redoStack.length > 0,
    undo(current) {
      const prev = undoStack.pop();
      if (!prev) return null;
      redoStack.push(snapshotOf(current));
      if (redoStack.length > cap) redoStack = redoStack.slice(redoStack.length - cap);
      return prev;
    },
    redo(current) {
      const next = redoStack.pop();
      if (!next) return null;
      undoStack.push(snapshotOf(current));
      if (undoStack.length > cap) undoStack = undoStack.slice(undoStack.length - cap);
      return next;
    },
    drop() {
      // On ne touche PAS à `redoStack` : `push` l'avait déjà vidé, et le geste refusé n'a
      // rien produit à rétablir. C'est toute la différence avec `undo`.
      return undoStack.pop() !== undefined;
    },
    clear() {
      undoStack = [];
      redoStack = [];
    },
    size: () => ({ undo: undoStack.length, redo: redoStack.length }),
  };
}
