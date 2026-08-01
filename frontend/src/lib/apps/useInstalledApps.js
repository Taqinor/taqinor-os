// ODY1 — La source de vérité « mes apps » (paradigme Odoo, en mieux —
// fondateur 2026-08-01).
// ----------------------------------------------------------------------------
// Croise, en UN SEUL endroit, les trois sources qui décidaient jusqu'ici la
// visibilité d'une app SÉPARÉMENT (et parfois pas du tout — constat vérifié
// `AppLauncher.jsx:14-16` avant ce correctif : il affichait TOUS les
// `moduleConfigs`, apps désactivées et rôles insuffisants compris) :
//
//   1. le registre         — `moduleConfigs` (UX1, router/moduleRoutes.jsx) :
//      un module « coquille » = une entrée avec une section `nav` non vide
//      (les modules routes-only comme `admin`, ou sans écran comme `ao`, ne
//      sont jamais une « app » — ils n'apparaissaient déjà pas au lanceur).
//   2. les modules actifs société — `selectModulesDesactives` (ODX6,
//      router/moduleGating.js), alimenté par `/auth/me/` au bootstrap.
//   3. les gardes rôle/permission — la RÈGLE de `useHasRole`/
//      `useHasPermission` (ARC47) : un item de nav est visible si le palier
//      (`state.auth.role`) est dans sa liste `roles` ET (sans `perm`, ou la
//      permission ERP `perm` est détenue). Une app est visible si AU MOINS un
//      de ses items l'est ; son `to` (cockpit) et son `icon` viennent du
//      PREMIER item que l'utilisateur peut réellement ouvrir — jamais du
//      premier item du config sans regarder s'il est autorisé (c'était le
//      2e trou : AppLauncher/PinnedApps ne filtraient par rôle NULLE PART).
//
// NOTE hooks : `useHasRole`/`useHasPermission` prennent une liste de rôles
// FIXE par appel et ne peuvent donc pas être invoqués une fois PAR app dans
// une boucle (violerait les règles des hooks, react-hooks/rules-of-hooks).
// Ce fichier lit `role`/`permissions` UNE fois via `useSelector` — exactement
// ce que ces deux hooks font en interne — puis rejoue leur règle en JS pur
// sur la liste des modules, à l'identique de `Sidebar.jsx`/`BottomTabBar.jsx`
// (`it.roles.includes(role) && (!it.perm || permissions.includes(it.perm))`).
//
// JAMAIS un 2ᵉ registre (contrainte Groupe ODY) : TOUTE surface qui liste des
// apps — `AppLauncher.jsx`, `PinnedApps.jsx`, et plus tard `HomeMenu`
// (ODY2), `CommandPalette`/`GlobalSearch`/`NotificationBell` (ODY27)… —
// consomme CE hook. Aucune logique de filtrage d'apps ne doit être dupliquée
// ailleurs.
import { useMemo } from 'react'
import { useSelector } from 'react-redux'
import { moduleConfigs } from '../../router/moduleRoutes'
import { selectModulesDesactives, isModuleDisabled } from '../../router/moduleGating'

const EMPTY_PERMISSIONS = []

// isItemVisible — même règle que Sidebar.jsx/BottomTabBar.jsx (gating d'un
// item de nav par palier + permission ERP fine optionnelle).
function isItemVisible(item, role, permissions) {
  return !!item?.roles?.includes(role) && (!item.perm || permissions.includes(item.perm))
}

/* ══════════════════════════════════════════════════════════════════════════
   ODY26 — L'AXE « APP VISIBLE » PAR RÔLE (décision : `Role.permissions`
   existant, AUCUN nouveau champ backend, AUCUNE migration).
   ──────────────────────────────────────────────────────────────────────────
   CONSTAT VÉRIFIÉ avant de décider : sur les 44 `module.config.jsx` du
   registre, DEUX items de nav seulement portent un `perm` (`journal_activite_
   voir`). La visibilité d'une app ne dépendait donc en pratique QUE du PALIER
   (`item.roles`), codé en dur dans les module.config — rien d'administrable.
   `Role.permissions` reste malgré tout le bon support : c'est le seul magasin
   par rôle, scopé société, éditable par l'admin (matrice VX38) et déjà
   acheminé jusqu'au front (`state.auth.permissions`) — que ce fichier LIT
   DÉJÀ. Un champ backend supplémentaire n'apporterait rien de plus ; il
   coûterait une migration et un 2ᵉ système à garder synchrone.

   CONVENTION : un code `app_<clé>_voir` par app (préfixe `app_` pour ne jamais
   collisionner avec les codes métier existants `crm_voir`, `sav_voir`…).

   SÉMANTIQUE : NARROWING OPT-IN — exactement le patron déjà documenté dans
   `apps/roles/models.py` pour `records_scope_equipe`/`records_scope_sous_arbre`
   (« un rôle SANS l'un de ces marqueurs voit tout — comportement historique
   préservé »). Un rôle qui ne porte AUCUN code `app_*_voir` voit toutes ses
   apps installées, comme aujourd'hui ; dès qu'il en porte au moins un, la
   liste devient une LISTE BLANCHE. Conséquences voulues :
     • zéro régression au déploiement (aucun rôle existant n'a ces codes) ;
     • le Directeur (qui hérite d'ALL_PERMISSIONS) n'est pas impacté, ces codes
       n'étant justement PAS dans ALL_PERMISSIONS (cf. roles/serializers.py) ;
     • une app AJOUTÉE plus tard reste visible des rôles non restreints.

   PORTÉE : c'est une restriction d'INTERFACE (quelles apps le porteur du rôle
   voit), pas une frontière de sécurité. Le gating serveur (palier + permission
   par viewset) est inchangé et reste seul juge de l'accès aux données.
   ══════════════════════════════════════════════════════════════════════════ */
const APP_PERM_PREFIX = 'app_'
const APP_PERM_SUFFIX = '_voir'

/** Code de permission « app visible » d'une clé de module (ODY26). */
export function appVisibilityPermission(key) {
  return `${APP_PERM_PREFIX}${key}${APP_PERM_SUFFIX}`
}

/** Vrai si `code` appartient à la famille ODY26 « app visible ». */
export function isAppVisibilityPermission(code) {
  return typeof code === 'string'
    && code.startsWith(APP_PERM_PREFIX)
    && code.endsWith(APP_PERM_SUFFIX)
    && code.length > APP_PERM_PREFIX.length + APP_PERM_SUFFIX.length
}

/* allowedAppKeys — liste blanche d'apps portée par des permissions, ou `null`
   quand le rôle n'est PAS restreint (aucun marqueur → visibilité historique).
   `null` et non un Set vide : « pas de restriction » et « restreint à rien »
   sont deux états différents, et seul le premier existe côté données. */
export function allowedAppKeys(permissions) {
  const codes = (permissions ?? []).filter(isAppVisibilityPermission)
  if (codes.length === 0) return null
  return new Set(codes.map(
    (c) => c.slice(APP_PERM_PREFIX.length, -APP_PERM_SUFFIX.length),
  ))
}

/* buildInstalledApps — fonction PURE (testable sans Provider Redux) : croise
   `configs` (forme de `moduleConfigs`) avec les modules désactivés et le
   rôle/permissions courants, renvoie la liste ORDONNÉE (ordre du registre —
   déjà trié par `order` puis `key`, cf. router/moduleRoutes.jsx) des apps
   visibles : `{key, label, icon, accent, to, description}`. */
export function buildInstalledApps(
  configs,
  { disabledModules = [], role, permissions = EMPTY_PERMISSIONS } = {},
) {
  // ODY26 — liste blanche d'apps portée par le rôle (`null` = pas de
  // restriction, comportement historique). Calculée UNE fois, hors de la
  // boucle.
  const autorisees = allowedAppKeys(permissions)
  return (configs ?? [])
    // routes-only (comme `admin`) ou sans écran (comme `ao`) : jamais une "app".
    .filter((c) => c?.nav?.items?.length > 0)
    // désactivée pour la société (ODX6).
    .filter((c) => !isModuleDisabled(disabledModules, c.key))
    // masquée pour CE rôle (ODY26) — après le gating société, avant le gating
    // rôle/permission par écran : une app retirée au rôle ne doit apparaître
    // NI en grille, NI en nav, NI au lanceur (toutes consomment ce hook).
    .filter((c) => !autorisees || autorisees.has(c.key))
    .map((c) => {
      const firstVisible = c.nav.items.find((it) => isItemVisible(it, role, permissions))
      if (!firstVisible) return null // rôle/permissions insuffisants pour TOUS les écrans de l'app
      return {
        key: c.key,
        label: c.nav.label,
        icon: firstVisible.icon,
        accent: c.nav.accent,
        to: firstVisible.to,
        // Pas encore déclarée dans les module.config (aucune ne le fait
        // aujourd'hui) — repli '' ; les passes ODY9/15-23 pourront ajouter
        // `nav.description` sans toucher ce fichier.
        description: c.nav.description ?? '',
      }
    })
    .filter(Boolean)
}

/**
 * useInstalledApps — hook React : « mes apps » pour la société et le rôle
 * courants (module actif ODX6 ∩ rôle/permission ARC47). Toute la logique de
 * croisement vit dans `buildInstalledApps` (pure, testée indépendamment) ;
 * ce hook se contente de lire le store et de mémoïser.
 *
 * @returns {{key:string,label:string,icon,accent:string|undefined,to:string,description:string}[]}
 */
export function useInstalledApps() {
  const disabledModules = useSelector(selectModulesDesactives)
  // Même repli que Sidebar.jsx/BottomTabBar.jsx ('normal' si état pas encore
  // chargé) — jamais une app affichée à un utilisateur sans rôle résolu.
  const role = useSelector((s) => s.auth.role) || 'normal'
  const permissions = useSelector((s) => s.auth.permissions) || EMPTY_PERMISSIONS

  return useMemo(
    () => buildInstalledApps(moduleConfigs, { disabledModules, role, permissions }),
    [disabledModules, role, permissions],
  )
}

export default useInstalledApps
