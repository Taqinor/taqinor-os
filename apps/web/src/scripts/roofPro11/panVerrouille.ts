// ACAL520 — cadenas d'un pan. PUR : un pan verrouillé refuse de bouger ses sommets, d'être
// supprimé, coté ou pivoté, en se NOMMANT. Rien à voir avec le verrou de VERSION du serveur.
import { areaLabel } from '../../lib/roofAreas';
import type { AreaRecord } from './types';

/** Le motif de refus d'un pan verrouillé, ou `null` s'il est modifiable. ACAL1430 — le pan est nommé par son RANG
 *  (`areaLabel(index)`, le nom de la liste), jamais par un `label` stocké qui peut dater d'une découpe. */
export function motifPanVerrouille(pan: Pick<AreaRecord, 'verrouille' | 'label'> | null | undefined, index = 0): string | null {
  if (!pan?.verrouille) return null;
  return `${index >= 0 ? areaLabel(index) : pan.label || areaLabel(0)} verrouillé — déverrouillez-le d’abord.`;
}
