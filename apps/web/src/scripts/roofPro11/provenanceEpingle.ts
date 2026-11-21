// ═══════════ ACAL193 — PROVENANCE DE L'ÉPINGLE (D-ACAL-13) ═══════════
// Sorti de `prefill.ts` (ACAL593 : un fichier de 2 000 lignes ou plus ne grossit pas) — à
// l'identique : `serializeLayout` l'appelle toujours en dernier.
import { type LngLat } from '../../lib/roof';
import { type Ctx } from './context';

const copieJson = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

/** L'épingle DÉPLACÉE À LA MAIN dans cette session, par scène (le contexte vivant de
 *  l'atelier) — hors du type `Ctx` : c'est un état de geste, pas une couche du document. */
const epinglesDeplacees = new WeakMap<object, { lat: number; lng: number }>();

/** ACAL193 — le dessinateur a déplacé l'épingle à la main : la scène passe `pinSource` à
 *  'manuel' et le prochain document porte CETTE épingle. Une coordonnée non finie est
 *  ignorée (jamais une épingle inventée). */
export function deplacerEpingleALaMain(ctx: Ctx, lngLat: LngLat): void {
  const [lng, lat] = lngLat;
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
  epinglesDeplacees.set(ctx as object, { lat, lng });
}

/** ACAL193 — oublie le déplacement (nouveau lead, effacement complet de la scène). */
export function oublierEpingleDeplacee(ctx: Ctx): void {
  epinglesDeplacees.delete(ctx as object);
}

/** ACAL193 — `pinSource` / `repereAcquitte` du document RELU, réémis octet-identiques ;
 *  une épingle déplacée à la main dans la session pose `pin` + `pinSource: 'manuel'`. Un
 *  document qui ne porte aucune des deux clés repart sans elles (rien d'inventé). */
export function emettreProvenanceEpingle<T extends object>(layout: T, ctx: Ctx): T {
  const relu = ctx.documentRelu ?? null;
  const sortie = layout as unknown as Record<string, unknown>;
  if (relu && typeof relu === 'object') {
    if ('pinSource' in relu) sortie.pinSource = copieJson(relu.pinSource);
    if ('repereAcquitte' in relu) sortie.repereAcquitte = copieJson(relu.repereAcquitte);
  }
  const deplacee = epinglesDeplacees.get(ctx as object);
  if (deplacee) {
    sortie.pin = { ...deplacee };
    sortie.pinSource = 'manuel';
  }
  return layout;
}
