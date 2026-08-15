/* WIR171 — Sémantique d'autorisation d'un item de nav / d'une route.
   ----------------------------------------------------------------------------
   SOURCE UNIQUE, partagée par les quatre endroits qui décidaient jusqu'ici
   chacun dans leur coin (`router/index.jsx` roleLoader, `Sidebar.jsx` chemin
   legacy, `lib/apps/ActiveAppContext.jsx` mode Apps, `lib/apps/useInstalledApps.js`
   grille du Menu d'accueil) — tous avec la MÊME règle codée en dur :

       roles.includes(palier) && (!perm || permissions.includes(perm))

   c'est-à-dire un ET strict entre le palier de menu et la permission ERP fine.
   Or le serveur ne décide PAS comme ça. La garde de lecture des modules
   Litiges / Contrats / QHSE / Projets / KB est
   `authentication.permissions.HasPermissionOrLegacy(<x>_voir)` :

     - compte portant un RÔLE FIN  → c'est la permission qui décide (un
       Commercial est au palier de menu « normal » mais porte bien
       `litige_voir`, accordé aux 7 rôles — d'où les `roles` élargis à
       « normal » sur ces modules, pour que le palier ne l'écarte plus) ;
     - compte HÉRITÉ sans rôle fin → la permission n'existe pas (la liste est
       vide côté /auth/me/) et le serveur retombe sur `user.is_responsable`.

   Un ET strict côté écran rendait donc les 5 modules INVISIBLES au Commercial
   alors que le serveur lui répondait 200. Déclarer simplement `perm` avec des
   `roles` élargis n'aurait pas suffi non plus : le compte hérité (permissions
   vides) aurait perdu un accès qu'il avait — d'où le repli explicite.

   CONTRAT : un item qui ne déclare PAS `permLegacyRoles` garde EXACTEMENT
   l'ancien comportement (ET strict). C'est voulu — toutes les gardes ne sont
   pas des `HasPermissionOrLegacy` : `journal_activite_voir` (audit/views.py)
   EXCLUT délibérément l'admin hérité sans rôle fin, et ne doit surtout pas
   hériter d'un repli palier.

   Forme d'un item/route :
     { roles: ['normal','responsable','admin'],
       perm: 'litige_voir',
       permLegacyRoles: ['responsable','admin'] }   // = user.is_responsable

   PURE : aucune dépendance React/Redux, testable telle quelle. */

/** Référence stable — jamais un littéral recréé à chaque appel. */
const AUCUNE = []

/**
 * @param {{roles?: string[], perm?: string, permLegacyRoles?: string[]}} item
 * @param {{tier?: string, roleNom?: string|null, permissions?: string[]}} contexte
 * @returns {boolean}
 */
export function itemAutorise(item, contexte) {
  if (!item) return false
  const roles = item.roles || AUCUNE
  const { perm, permLegacyRoles } = item
  const ctx = contexte || {}
  const tier = ctx.tier || 'normal'
  const roleNom = ctx.roleNom || null
  const permissions = ctx.permissions || AUCUNE

  // Aucune permission exigée → gating par palier seul (comportement historique).
  if (!perm) return roles.includes(tier)

  // Repli « compte hérité » (miroir de HasPermissionOrLegacy) : sans rôle fin,
  // la permission n'est pas exigible — le serveur retombe sur le palier.
  if (permLegacyRoles && !roleNom) return permLegacyRoles.includes(tier)

  // Rôle fin, ou garde STRICTE sans repli déclaré : palier ∩ permission.
  return roles.includes(tier) && permissions.includes(perm)
}

export default itemAutorise
