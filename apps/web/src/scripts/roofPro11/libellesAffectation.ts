/**
 * ACAL729 — les clés et libellés d'affectation (chaîne / MPPT) d'un module, sortis de `scene3d.ts`
 * (fichier-mur : il ne grossit pas) pour que l'atelier les lise sans importer la scène. `scene3d.ts`
 * les ré-exporte sous leurs noms d'origine.
 */
import type { AffectationMode, AffectationRow } from './scene3d';
import { registreAtelier } from './numerotation'; // R3 (visuel lot 7) — les `n` du document, lus

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
 * R3 (visuel lot 7) — les numéros STABLES (`panels[].n`) d'un pan, dans l'ordre du document : MÊME
 * règle que le serveur (`production.py::numeros_des_modules`). `[]` dès qu'un panneau n'en porte pas
 * un entier > 0 ou que deux portent le même : le rang reprend alors la main, des deux côtés.
 */
export function numerosStablesDuPan(panels: readonly unknown[] | null | undefined): number[] {
  if (!Array.isArray(panels) || !panels.length) return [];
  const numeros: number[] = [];
  for (const panneau of panels) {
    const n = (panneau as { n?: unknown } | null)?.n;
    if (typeof n !== 'number' || !Number.isInteger(n) || n <= 0) return [];
    numeros.push(n);
  }
  return new Set(numeros).size === numeros.length ? numeros : [];
}

/**
 * ACAL286 — identifiant de module `<pan>#<n>` de CHAQUE cellule de lattice posée, indexé
 * PAR CELLULE (la forme que `affectationColorFn` attend). Les cellules occupées du pan, triées,
 * suivent l'ordre de `geometry.panels` que `serializeLayout` écrit ; le serveur nomme le module de
 * rang r par le `n` du r-ième panneau (`production.py::cle_de_module`).
 * R3 (visuel lot 7) — `n` vient du document absorbé par l'atelier (`registreAtelier.modules`, LECTURE
 * seule) : nommer par le rang ne retrouvait plus aucune ligne servie dès que le compteur avait grandi
 * (`area-2#2236…` servis, `area-2#1…` cherchés : aucun module teinté). Repli sur le rang, inchangé :
 * document sans numéros valides, ou nombre de panneaux du document ≠ cellules à l'écran (pose pas encore
 * enregistrée, estimateur public sans document).
 */
export function identifiantsModulesParCellule(
  cellules: readonly number[],
  libelle: string,
  numeros: readonly number[] = numerosStablesDuPan(registreAtelier.modules(libelle)),
): string[] {
  const ids: string[] = [];
  const triees = [...cellules].sort((a, b) => a - b);
  const stables = numeros.length === triees.length ? numeros : null;
  triees.forEach((cellule, i) => {
    ids[cellule] = `${libelle}#${stables ? stables[i] : i + 1}`;
  });
  return ids;
}
