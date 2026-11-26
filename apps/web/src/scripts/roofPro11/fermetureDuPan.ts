/**
 * Demande croisée (ACAL562) — à la fin du tracé d'un pan, les retraits de la société se posent AVANT le premier
 * pavage : le premier `recalc` d'un pan neuf lit déjà ses arêtes retraitées, il n'est pas refait juste après.
 * Rend la ligne d'état à dire (types d'arête inconnus) ou `null`.
 *
 * ACAL1330 (D-ACAL-75 « rejouer ») — un pan rouvert AVEC sa pose enregistrée (`planRejoue`) ne reçoit pas les
 * retraits de la société : ils re-pavaient le pan plus petit à l'ouverture et la pose relue y perdait des panneaux
 * (calepinage 5 : 60 enregistrés, 55 à l'écran, un « Enregistrer » aurait écrit 55). Les pans neufs les reçoivent.
 */
import { type Ctx } from './context';
import { poserRetraitsSurPanActif } from './retraitsSociete';

export function poserRetraitsPuisRecalculer(ctx: Ctx, recalc: () => void, planRejoue = false): string | null {
  const info = planRejoue ? null : poserRetraitsSurPanActif(ctx);
  recalc();
  return info;
}
