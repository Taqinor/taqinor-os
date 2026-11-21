// ACAL520 — cadenas d'un pan. PUR : un pan verrouillé refuse de bouger ses sommets, d'être
// supprimé, coté ou pivoté, en se NOMMANT. Rien à voir avec le verrou de VERSION du serveur.
import { areaLabel } from '../../lib/roofAreas';
import type { AreaRecord } from './types';

/** Le motif de refus d'un pan verrouillé, ou `null` s'il est modifiable. `index` sert à le nommer
 *  quand il n'a pas de libellé (« Pan 1 »). */
export function motifPanVerrouille(pan: Pick<AreaRecord, 'verrouille' | 'label'> | null | undefined, index = 0): string | null {
  if (!pan?.verrouille) return null;
  return `${pan.label || areaLabel(index)} verrouillé — déverrouillez-le d’abord.`;
}
