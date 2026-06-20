/**
 * Contexte partagé qui ponte la fermeture (« god closure ») de
 * `initRoofToolPro8` vers les modules roofPro11 extraits (split modulaire
 * 2026-06-20). Chaque champ d'état MUTABLE est exposé par accesseur
 * (get/set) afin que le code resté dans `roof-tool-pro11.ts` continue d'utiliser
 * ses `let` bruts tandis que les modules extraits lisent/écrivent via `ctx.*` —
 * comportement INCHANGÉ.
 *
 * L'interface grandit module par module ; on n'ajoute ici QUE ce qu'un module
 * extrait référence réellement.
 */
import { type SvgBox } from '../../lib/productionWindow';
import { type SpecificDateProfile } from '../../lib/productionEngine';

export interface Ctx {
  // — Constantes de rendu graphes (figées au boot) —
  readonly svgBox: SvgBox;

  // — État de la fenêtre de production (mutable) —
  /** Index 0–11 du mois sélectionné dans la fenêtre de production. */
  prodMonth: number;
  /** Profil de la date précise (mis à l'échelle) ou null = jour TYPE du mois. */
  prodSpecificDate: SpecificDateProfile | null;
}
