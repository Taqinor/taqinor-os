/* ============================================================================
   NTPRT8/20/27 — Portée d'un compte PORTAIL externe (client / fournisseur /
   partenaire) et routage du shell dédié.
   ----------------------------------------------------------------------------
   Logique PURE (aucun import React/store) : le routeur, le shell et les tests
   partagent la MÊME source de vérité. La portée fait autorité côté SERVEUR
   (`CustomUser.portee`, NTPRT1, exposée en LECTURE SEULE par /auth/me/) — ces
   helpers ne font que la LIRE pour aiguiller l'interface. La vraie garde
   d'accès reste backend (NTPRT5 : un compte portail reçoit 403 sur toute route
   interne) ; ici on évite juste à l'utilisateur d'atterrir sur un écran ERP
   vide qu'il n'a pas le droit de charger.

   Par défaut TOUT compte est `interne` : un compte sans champ `portee` (jeton
   ancien, réponse partielle) est traité comme INTERNE — jamais comme un
   portail privilégié.
   ========================================================================== */

export const PORTEE_INTERNE = 'interne'
export const PORTEE_CLIENT = 'portail_client'
export const PORTEE_FOURNISSEUR = 'portail_fournisseur'
export const PORTEE_PARTENAIRE = 'portail_partenaire'

/** Portée → racine du shell portail correspondant. */
export const PORTAL_HOME = {
  [PORTEE_CLIENT]: '/portail/client',
  [PORTEE_FOURNISSEUR]: '/portail/fournisseur',
  [PORTEE_PARTENAIRE]: '/portail/partenaire',
}

/** Portée → champ d'id de rattachement servi par /auth/me/ (NTPRT1). */
export const PORTAL_SCOPE_FIELD = {
  [PORTEE_CLIENT]: 'portail_client_id',
  [PORTEE_FOURNISSEUR]: 'portail_fournisseur_id',
  [PORTEE_PARTENAIRE]: 'portail_partenaire_id',
}

/** Portée d'un utilisateur, `interne` par défaut (valeur inconnue incluse). */
export function porteeDe(user) {
  const p = user && typeof user === 'object' ? user.portee : null
  return Object.prototype.hasOwnProperty.call(PORTAL_HOME, p)
    ? p
    : PORTEE_INTERNE
}

/** Vrai si l'utilisateur est un compte PORTAIL externe (jamais un interne). */
export function isPortalUser(user) {
  return porteeDe(user) !== PORTEE_INTERNE
}

/** Racine du shell portail de cet utilisateur, ou `null` s'il est interne. */
export function portalHomePath(user) {
  return PORTAL_HOME[porteeDe(user)] || null
}

/** Id de l'entité (client/fournisseur/partenaire) rattachée, ou `null`. */
export function portalScopeId(user) {
  const field = PORTAL_SCOPE_FIELD[porteeDe(user)]
  if (!field || !user) return null
  const value = user[field]
  return value === undefined || value === null ? null : value
}

/** Vrai si `pathname` appartient à l'espace portail (quel que soit le scope). */
export function isPortalPath(pathname) {
  return typeof pathname === 'string'
    && (pathname === '/portail' || pathname.startsWith('/portail/'))
}

/**
 * Vrai si `user` a le droit d'entrer dans le shell portail de portée `portee`.
 * Un compte portail d'UNE portée n'entre jamais dans le shell d'une AUTRE
 * (un fournisseur ne voit pas l'espace client) — lecture volontairement
 * stricte : on exige l'égalité exacte, jamais « portail quelconque ».
 */
export function peutEntrerDansPortail(user, portee) {
  return porteeDe(user) === portee && portee !== PORTEE_INTERNE
}
