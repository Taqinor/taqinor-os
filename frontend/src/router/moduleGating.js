/* ODX6 — Gating de la navigation et des routes par module actif/désactivé.
   ----------------------------------------------------------------------------
   Source unique de vérité : la liste `modules_desactives` servie par
   `/auth/me/` (état `ModuleToggle` côté backend, ODX3), stockée dans
   `auth.modulesDesactives`. Défaut = liste VIDE ⇒ aucun module masqué, nav et
   routing strictement identiques à aujourd'hui tant qu'aucun toggle n'existe.

   Une SECTION de nav ou une ROUTE de module porte une clé `key` = la clé du
   module (ex. 'flotte', 'stock'). Les sections/routes SANS `key` (Dashboard,
   Messages, Administration, Paramètres…) ne sont jamais masquées : ce sont des
   surfaces globales/fondation, pas des modules togglables.

   Ces helpers sont volontairement de PURES fonctions (aucune dépendance React) :
   les composants les alimentent via `useSelector(selectModulesDesactives)`, le
   routeur via un lecteur synchrone du store (cf. router/index.jsx). */

// Sélecteur Redux : liste (repli tableau vide stable) des clés désactivées.
export const selectModulesDesactives = (state) =>
  state.auth.modulesDesactives || []

// Vrai si `key` est explicitement désactivée pour la société courante.
// `key` absente/nulle → jamais désactivée (surface globale).
export function isModuleDisabled(disabled, key) {
  if (!key) return false
  return (disabled || []).includes(key)
}

// Filtre une liste de sections de nav : retire toute section dont la clé de
// module est désactivée. Ne mute jamais l'entrée (retourne une nouvelle liste).
export function filterNavSections(sections, disabled) {
  const off = disabled || []
  if (off.length === 0) return sections // chemin par défaut : aucune copie.
  return sections.filter((s) => !isModuleDisabled(off, s.key))
}

/* ════════════════════════════════════════════════════════════════════════════
   WIR171 — Gating d'un ITEM de nav / d'une ROUTE par palier + permission ERP.
   ────────────────────────────────────────────────────────────────────────────
   Source UNIQUE de la règle : `roleLoader` (router/index.jsx), la Sidebar,
   la BottomTabBar, `appNavItems` (lib/apps/ActiveAppContext) et
   `buildInstalledApps` (lib/apps/useInstalledApps) l'appellent tous ici —
   plus aucune copie de la règle ailleurs.

   Deux sémantiques, choisies PAR ENTRÉE, parce que le serveur en a deux :

   1. DÉFAUT (inchangé) — ET strict `palier × permission`. C'est le miroir des
      gardes serveur SANS repli légacy : `CanViewAoRentabilite`
      (apps/ao/permissions.py — AOF2 : « AUCUN repli historique », sinon la
      fuite de marge se rouvre) et `CanViewActivityLog` (apps/audit/views.py,
      qui exclut délibérément l'admin légacy sans rôle fin). Ne JAMAIS relâcher
      cette branche.

   2. `permRepliPalier: true` — miroir EXACT de `HasPermissionOrLegacy`
      (backend/django_core/authentication/permissions.py) :
        • compte portant un RÔLE FIN → la PERMISSION décide, SEULE. Le palier
          ne restreint plus : un « Commercial » relève du palier 'normal'
          (authentication/role_tiers.py) tout en portant `litige_voir`,
          `contrat_voir`, `qhse_voir`, `projet_voir`, `kb_voir` — le serveur
          lui répond 200, la coquille doit donc lui montrer l'écran.
        • compte LÉGACY (aucun rôle fin) → repli sur le palier historique
          responsable/admin (`user.is_responsable`), comportement inchangé
          pour demo_admin / demo_resp.
      C'est pourquoi ce n'est PAS un simple ET : un ET fermerait la porte aux
      comptes légacy responsable/admin, dont `/auth/me/` ne sert AUCUNE
      permission (`UserSerializer.get_permissions` renvoie `[]` sans rôle).

   Signal « rôle fin » côté client : la liste de permissions servie est NON
   VIDE. `get_permissions()` ne renvoie des codes QUE pour un compte portant un
   Role ; un compte légacy reçoit `[]`. Aucun champ supplémentaire n'est donc
   nécessaire, et aucune signature d'appelant ne change.
   ══════════════════════════════════════════════════════════════════════════ */

// Paliers historiques de `IsResponsableOrAdmin` / `user.is_responsable`.
export const PALIERS_LEGACY = ['responsable', 'admin']

/**
 * Vrai si l'entrée (item de nav ou route de module, forme `{roles, perm,
 * permRepliPalier}`) est autorisée pour le palier + les permissions courants.
 * PURE — testable sans React ni store.
 */
export function estAutoriseEntree(entree, tier, permissions) {
  if (!entree) return false
  const roles = entree.roles || []
  const perms = permissions || []
  if (!entree.perm) return roles.includes(tier)
  if (entree.permRepliPalier) {
    return perms.length > 0
      ? perms.includes(entree.perm)
      : PALIERS_LEGACY.includes(tier)
  }
  return roles.includes(tier) && perms.includes(entree.perm)
}
