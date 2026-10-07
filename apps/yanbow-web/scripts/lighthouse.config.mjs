// YBW16 — configuration de la porte Lighthouse (source unique des seuils).
//
// Seuil : 97 sur les QUATRE catégories, sur CHAQUE URL du registre
// `src/i18n/pages.ts` présente dans `dist/` (donc les langues actives
// seulement), profil MOBILE (défaut Lighthouse : émulation + bridage simulé).
// L'ensemble complet (accueil, deux pages produit, rendez-vous, FR et EN) est
// asserté en YBW80, quand ces pages existent. Tant que la page sonde existe,
// elle est mesurée aussi (pour que la porte mesure dès maintenant un vrai rendu).

/** Seuil appliqué à chaque catégorie, sur chaque URL. */
export const SCORE_FLOOR = 97;

/** Catégories notées. */
export const CATEGORIES = ['performance', 'accessibility', 'best-practices', 'seo'];

/** LCP maximal (ms, mesure simulée mobile). */
export const LCP_MAX_MS = 2500;

/** CLS maximal, mesuré dans une passe où les polices sont BLOQUÉES (pire cas du repli). */
export const CLS_MAX_POLICES_BLOQUEES = 0.02;

/** Motifs bloqués pour la passe « polices bloquées ». */
export const MOTIFS_POLICES = ['*.woff2', '*.woff', '*.ttf', '*.otf'];

/**
 * Audits ignorés, chacun avec sa raison :
 * - `is-crawlable` : le site est VOLONTAIREMENT fermé (X-Robots-Tag noindex,
 *   porte de lancement YBW12) tant que Reda ne l'ouvre pas ; cette fermeture
 *   est vérifiée par ses propres tests (YBW12) et par le contrôle de lancement
 *   (YBW85). La compter ici ferait échouer la porte pour une raison voulue.
 */
export const AUDITS_IGNORES = ['is-crawlable'];
