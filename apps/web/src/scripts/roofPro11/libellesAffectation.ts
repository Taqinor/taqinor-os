/**
 * ACAL729 — les clés et libellés d'affectation (chaîne / MPPT) d'un module, sortis de `scene3d.ts`
 * (fichier-mur : il ne grossit pas) pour que l'atelier les lise sans importer la scène. `scene3d.ts`
 * les ré-exporte sous leurs noms d'origine.
 */
import type { AffectationMode, AffectationRow } from './scene3d';

/** Clé de groupe d'une ligne, selon le mode. `null` = module NON affecté.
 *  En mode MPPT la clé porte l'onduleur : deux onduleurs ont chacun leur entrée 1. */
export function affectationGroupKey(row: AffectationRow, mode: AffectationMode): string | null {
  if (mode === 'chaine') {
    return row.chaine == null ? null : `c${row.chaine}`;
  }
  if (row.mppt == null) return null;
  return `o${row.onduleur ?? 1}m${row.mppt}`;
}

/** Libellé lisible d'un groupe, pour la légende. */
export function affectationGroupLabel(row: AffectationRow, mode: AffectationMode): string {
  if (mode === 'chaine') return row.chaine == null ? 'Non affecté' : `Chaîne ${row.chaine}`;
  if (row.mppt == null) return 'Non affecté';
  return row.onduleur == null ? `MPPT ${row.mppt}` : `Onduleur ${row.onduleur} — MPPT ${row.mppt}`;
}

/** Libellé d'un module AFFECTÉ pour une phrase (« chaîne 2 »), `null` s'il ne l'est pas (rien d'inventé). */
export function libelleModuleAffecte(row: AffectationRow, mode: AffectationMode): string | null {
  if (affectationGroupKey(row, mode) == null) return null;
  const l = affectationGroupLabel(row, mode);
  return l.charAt(0).toLowerCase() + l.slice(1);
}

/**
 * ACAL286 — identifiant de module `<pan>#<rang>` de CHAQUE cellule de lattice posée, indexé
 * PAR CELLULE (la forme que `affectationColorFn` attend). Le rang est la position 1-based de la
 * cellule parmi les cellules occupées du pan, triées : c'est l'ordre de `geometry.panels` que
 * `serializeLayout` écrit, donc celui dont le serveur nomme ses modules (`chaines.py`).
 */
export function identifiantsModulesParCellule(cellules: readonly number[], libelle: string): string[] {
  const ids: string[] = [];
  [...cellules].sort((a, b) => a - b).forEach((cellule, i) => {
    ids[cellule] = `${libelle}#${i + 1}`;
  });
  return ids;
}
