/**
 * CALX114 câblage — L'OBJECTIF D'OPTIMISATION VOYAGE PAR LE DOCUMENT.
 *
 * `optimizer.ts` porte déjà l'objectif SAISI (`poserChoixOptimisation` /
 * `choixOptimisationCourant`) et les deux balayages le lisent au même endroit — mais
 * PERSONNE ne le lisait dans le document ni ne l'y écrivait. L'objectif choisi à l'écran
 * était donc perdu au rechargement, exactement comme la hauteur de bâtiment de CAL60.
 *
 * Ce module est ce crochet-là, et rien d'autre. `optimizer.ts` n'est pas modifié (il ne
 * lit ni n'écrit le document, c'est sa discipline) et `prefill.ts` ne gagne que DEUX
 * lignes d'appel — toute la logique est ici.
 *
 * ÉQUIVALENCE : tant qu'aucun objectif n'est saisi, `ecrireOptimisationDansDocument` ne
 * pose AUCUNE clé — un document d'hier repart octet pour octet. Rien n'est traduit ni
 * complété : un fragment hors contrat est déposé tel quel et c'est
 * `resoudreCibleOptimisation` qui le REFUSE en le nommant (jamais un objectif de repli).
 */
import { choixOptimisationCourant, poserChoixOptimisation } from './optimizer';
import { type ChoixOptimisation } from '../../lib/estimatorBrainV6';

/** La clé RACINE du contrat CALX88. Une seule formulation dans tout l'atelier. */
export const CLE_OPTIMISATION = 'optimisation';

/** Le fragment `optimisation` d'un document, ou `null` — jamais un objet fabriqué. */
export function lireOptimisationDuDocument(json: unknown): ChoixOptimisation | null {
  const brut = (json as Record<string, unknown> | null | undefined)?.[CLE_OPTIMISATION];
  if (!brut || typeof brut !== 'object' || Array.isArray(brut)) return null;
  return brut as ChoixOptimisation;
}

/**
 * À L'OUVERTURE — dépose dans l'optimiseur l'objectif que le document porte. Un document
 * sans `optimisation` REMET l'optimiseur à « aucun objectif saisi » : sans cela, l'objectif
 * du dossier précédent (état de module partagé) déborderait sur le dossier suivant.
 * Renvoie ce qui a été déposé (`null` = aucun objectif saisi).
 */
export function semerOptimisationDepuisDocument(json: unknown): ChoixOptimisation | null {
  const choix = lireOptimisationDuDocument(json);
  poserChoixOptimisation(choix);
  return choix;
}

/**
 * À LA SÉRIALISATION — écrit l'objectif COURANT dans le document (mutation en place, même
 * patron que `numeroterDocument`/`ecrireModulesDansDocument`). Aucun objectif saisi ⇒
 * aucune clé posée, et une clé déjà présente dans le document repris est RETIRÉE : le
 * document dit ce que l'atelier applique, jamais un objectif fantôme.
 * Renvoie `true` si la clé est présente en sortie.
 */
export function ecrireOptimisationDansDocument(layout: unknown): boolean {
  const cible = layout as Record<string, unknown> | null | undefined;
  if (!cible || typeof cible !== 'object') return false;
  const choix = choixOptimisationCourant();
  if (!choix) {
    delete cible[CLE_OPTIMISATION];
    return false;
  }
  cible[CLE_OPTIMISATION] = { ...choix };
  return true;
}
