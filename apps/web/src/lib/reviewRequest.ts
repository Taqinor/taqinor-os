/**
 * W341 — Milestone review-request asset : le message WhatsApp pré-rempli
 * (`wa.me/<numéro-client>`) que l'équipe Taqinor envoie à J+14/21 après une
 * installation, pour demander un avis Google — timé sur un MILESTONE plutôt
 * qu'immédiatement après la mise en service (la recherche montre que la
 * demande différée convertit mieux qu'une demande à chaud).
 *
 * C'est la couche QUAND/COMMENT posée sur la couche « claim » de WG5 :
 * WG5 confirme la fiche Google Business Profile et renseigne
 * `GOOGLE_RATING.url` (src/lib/testimonials.ts) ; ce fichier construit le
 * message que l'équipe envoie une fois cette URL disponible. Tant que
 * `GOOGLE_RATING` est `null` (ou sans `.url`), `hasReviewRequestUrl()` renvoie
 * `false` et `reviewRequestWhatsappLink` renvoie `null` — AUCUNE URL n'est
 * jamais inventée ou substituée par un lien générique « laissez un avis ».
 *
 * Usage prévu : un outil interne (ex. une page de suivi chantier future, ou
 * un simple rappel dans le process SAV) appelle
 * `reviewRequestWhatsappLink(clientPhone, clientFirstName)` à J+14/21 et
 * envoie le wa.me/ résultant si non-null.
 */
import { GOOGLE_RATING } from './testimonials';
import { whatsappLink } from './whatsapp';

/** Fenêtre de milestone recommandée (jours après mise en service). */
export const REVIEW_REQUEST_WINDOW_DAYS = { min: 14, max: 21 } as const;

/** `true` seulement quand WG5 a fourni une vraie URL d'avis Google. */
export function hasReviewRequestUrl(): boolean {
  return typeof GOOGLE_RATING?.url === 'string' && GOOGLE_RATING.url.trim().length > 0;
}

/**
 * Compose le message « Comment ça s'est passé ? » avec le lien d'avis Google
 * — jamais de placeholder, jamais de lien générique fabriqué : tant que
 * `GOOGLE_RATING.url` n'existe pas (WG5 non livré), renvoie `null`.
 *
 * @param clientPhone   Numéro WhatsApp du client (chiffres, indicatif pays —
 *                      même format que `whatsappLink`). Requis : ce message
 *                      cible TOUJOURS un client précis, jamais un compositeur
 *                      générique (contrairement à whatsappReferralLink).
 * @param clientFirstName Prénom du client pour personnaliser le message
 *                        (optionnel — le message reste naturel sans).
 */
export function reviewRequestWhatsappLink(clientPhone: string, clientFirstName?: string): string | null {
  if (!hasReviewRequestUrl()) return null;
  const url = GOOGLE_RATING!.url!.trim();
  const name = clientFirstName?.trim();
  const greeting = name ? `Bonjour ${name},` : 'Bonjour,';
  const msg =
    `${greeting} ça fait maintenant quelques semaines que votre installation solaire ` +
    `tourne — comment ça s'est passé ? Si vous êtes satisfait(e), un avis Google nous aiderait ` +
    `énormément à être trouvés par d'autres foyers comme le vôtre : ${url} ` +
    `Merci beaucoup, l'équipe Taqinor.`;
  return whatsappLink(clientPhone, msg);
}
