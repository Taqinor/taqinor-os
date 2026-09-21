/**
 * CALX107 câblage — LE CALQUE DE FOND DU DOCUMENT EST ENFIN LU À L'OUVERTURE.
 *
 * `underlay.ts` sait lire la clé racine `underlay` (`lireUnderlay`, contrat CALX86) et
 * `mapDraw.setFond` sait la peindre — mais `deserializeLayout` ne la regardait pas et
 * personne n'appelait `setFond`. Un dossier rouvert perdait donc son fond de plan / sa
 * photo calée, alors que le document le portait.
 *
 * Ce module ne fait QUE se souvenir de ce que le document demande, pour que la page hôte
 * puisse aller chercher le FICHIER correspondant (l'atelier ne parle jamais à Django) et
 * le redonner au constructeur. Il ne peint rien et ne télécharge rien.
 *
 * Même discipline que `optimisationDocument.ts` : `prefill.ts` ne gagne qu'UNE ligne
 * d'appel, et un document sans `underlay` REMET la mémoire à « aucun fond » — sinon le
 * fond du dossier précédent déborderait sur celui-ci.
 */
import { lireUnderlay, type DocumentUnderlay } from './underlay';

/** Ce que le DERNIER document lu demandait comme fond (`null` = aucun, ou refusé). */
let fondDemande: DocumentUnderlay | null = null;
/** Le motif du refus quand le document portait un `underlay` illisible. */
let motifRefus: string | null = null;

/**
 * À L'OUVERTURE — mémorise le fond que le document demande.
 *
 * Une clé `underlay` ABSENTE n'est pas un refus : c'est « aucun fond », l'atelier
 * d'aujourd'hui exactement. Une clé PRÉSENTE mais illisible est refusée par `lireUnderlay`
 * en NOMMANT son champ, et le motif est gardé pour être dit — jamais un fond deviné.
 */
export function semerFondDepuisDocument(json: unknown): DocumentUnderlay | null {
  const brut = (json as Record<string, unknown> | null | undefined)?.underlay;
  fondDemande = null;
  motifRefus = null;
  if (brut == null) return null;
  const lu = lireUnderlay(brut);
  if (!lu.ok) {
    motifRefus = lu.motif;
    return null;
  }
  fondDemande = lu.fond;
  return fondDemande;
}

/** Le fond que le document courant demande, ou `null`. */
export function fondDuDocument(): DocumentUnderlay | null {
  return fondDemande;
}

/** Le motif du refus du dernier `underlay` illisible, ou `null`. Le motif d'un fond
 *  VALIDE mais non affichable (fichier absent) appartient à `placementDuFond` : une seule
 *  formulation dans tout l'atelier, jamais une seconde recopiée ici. */
export function motifFondRefuse(): string | null {
  return motifRefus;
}
