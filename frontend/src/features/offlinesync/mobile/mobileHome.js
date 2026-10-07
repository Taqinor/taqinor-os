// NTMOB6 / ALEA31 — Sélecteur de démarrage mobile. Fonctions PURES (aucun
// React, aucun réseau) — testables sous `node --test`, exécutées par
// Dashboard.jsx (le seul point d'atterrissage générique post-login).
//
// ALEA31 — LE SERVEUR EST LA SEULE TABLE. La route suggérée pour un rôle est
// calculée par `authentication.selectors.default_mobile_home_route` et servie
// par `/auth/me/` dans `mobile_home_route_suggeree`. Ce module n'en garde
// AUCUNE copie : l'ancienne table « dupliquée volontairement » avait divergé
// (le Commercial terrain atterrissait sur `/mobile/commercial`, un écran qu'il
// ne voit pas, au lieu de `/visites` ; les accueils d'équipe NTMOB25/26
// étaient refusés par la liste blanche serveur).

/**
 * Route d'accueil mobile suggérée PAR LE SERVEUR pour le compte courant.
 * @param {object|null|undefined} user - profil `/auth/me/`.
 * @returns {string} route suggérée, ou `''` (dashboard générique).
 */
export function routeSuggereeServeur(user) {
  const route = user?.mobile_home_route_suggeree
  return typeof route === 'string' ? route : ''
}

/**
 * Décide QUOI FAIRE sur ce rendu du Dashboard. Ne fait ni navigation ni appel
 * réseau — le composant exécute juste le verdict :
 *   * `{ type: 'navigate', to }` — route déjà mémorisée côté serveur ;
 *   * `{ type: 'decide', suggested }` — premier atterrissage mobile (valeur
 *     encore NULL/undefined) : le composant persiste `suggested` (la route du
 *     SERVEUR) et navigue s'il n'est pas vide ;
 *   * `null` — desktop, profil pas encore chargé, ou opt-out explicite
 *     (`mobileHomeRoute === ''`) : comportement inchangé.
 */
export function mobileHomeAction({
  isMobile, hasFullProfile, mobileHomeRoute, suggestedRoute,
}) {
  if (!isMobile || !hasFullProfile) return null
  if (mobileHomeRoute) return { type: 'navigate', to: mobileHomeRoute }
  if (mobileHomeRoute === '') return null
  return { type: 'decide', suggested: suggestedRoute || '' }
}
