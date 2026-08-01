// NTMOB6 — Sélecteur de démarrage par rôle : calcule la route d'accueil
// mobile PAR DÉFAUT pour un rôle donné. Fonction PURE (aucun React, aucun
// réseau) — testable sous `node --test`, réutilisée par Dashboard.jsx (le
// seul point d'atterrissage générique post-login). Reflète le même mapping
// que le sélecteur serveur (`authentication.selectors.
// default_mobile_home_route`) — petite table dupliquée volontairement pour
// rester un module frontend pur (même patron que PRIORITY_ORDER dans
// CommercialHome.jsx).
//
// Technicien → `/ma-journee` (déjà existant, F22) ; Commercial → NTMOB4
// (`/mobile/commercial`) ; Directeur/Administrateur → NTMOB5
// (`/mobile/cockpit`) ; tout autre rôle → `''` (dashboard générique,
// comportement inchangé). Les variantes « responsable » (Commercial
// responsable, Technicien responsable) retombent sur l'accueil de base de
// leur famille via un préfixe — aucun accueil dédié n'existe encore pour
// elles (NTMOB25/26).
const BY_EXACT_ROLE = {
  Directeur: '/mobile/cockpit',
  Administrateur: '/mobile/cockpit',
}

const BY_ROLE_PREFIX = [
  ['Technicien', '/ma-journee'],
  ['Commercial', '/mobile/commercial'],
]

/**
 * @param {string|null|undefined} roleNom - nom du Role fin (ex. « Commercial »).
 * @param {string|null|undefined} roleTier - palier de menu hérité
 *   (`admin`/`responsable`/`normal`), repli pour les comptes sans Role fin.
 * @returns {string} route mobile suggérée, ou `''` (dashboard générique).
 */
export function defaultMobileHomeRoute(roleNom, roleTier) {
  const nom = roleNom || ''
  if (BY_EXACT_ROLE[nom]) return BY_EXACT_ROLE[nom]
  const match = BY_ROLE_PREFIX.find(([prefix]) => nom.startsWith(prefix))
  if (match) return match[1]
  if (!nom && roleTier === 'admin') return '/mobile/cockpit'
  return ''
}
