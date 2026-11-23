/**
 * Demande croisée (ACAL562) — à la fin du tracé d'un pan, les retraits de la société se posent AVANT le premier
 * pavage : le premier `recalc` d'un pan neuf lit déjà ses arêtes retraitées, il n'est pas refait juste après.
 * Rend la ligne d'état à dire (types d'arête inconnus) ou `null`.
 */
import { type Ctx } from './context';
import { poserRetraitsSurPanActif } from './retraitsSociete';

export function poserRetraitsPuisRecalculer(ctx: Ctx, recalc: () => void): string | null {
  const info = poserRetraitsSurPanActif(ctx);
  recalc();
  return info;
}
