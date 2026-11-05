/**
 * Chemins statiques partagés des routes /en|ar/produits/<slug> (WAUD87) : une seule définition
 * du getStaticPaths pour les deux wrappers de locale (anti-duplicata littéral).
 */
import { FICHES } from './fiches';

export function fichesStaticPaths() {
  return FICHES.map((f) => ({ params: { slug: f.slug }, props: { fiche: f } }));
}
