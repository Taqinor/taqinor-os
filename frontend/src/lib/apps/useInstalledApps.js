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

/* buildInstalledApps — fonction PURE (testable sans Provider Redux) : croise
   `configs` (forme de `moduleConfigs`) avec les modules désactivés et le
   rôle/permissions courants, renvoie la liste ORDONNÉE (ordre du registre —
   déjà trié par `order` puis `key`, cf. router/moduleRoutes.jsx) des apps
   visibles : `{key, label, icon, accent, to, description}`. */
export function buildInstalledApps(
  configs,
  { disabledModules = [], role, permissions = EMPTY_PERMISSIONS } = {},
) {
  return (configs ?? [])
    // routes-only (comme `admin`) ou sans écran (comme `ao`) : jamais une "app".
    .filter((c) => c?.nav?.items?.length > 0)
    // désactivée pour la société (ODX6).
    .filter((c) => !isModuleDisabled(disabledModules, c.key))
    .map((c) => {
      const firstVisible = c.nav.items.find((it) => isItemVisible(it, role, permissions))
      if (!firstVisible) return null // rôle/permissions insuffisants pour TOUS les écrans de l'app
      return {
        key: c.key,
        label: c.nav.label,
        // APX1 — un module PEUT déclarer son icône d'app (`nav.icon`) : le
        // glyphe devient alors indépendant de l'ORDRE de ses items. Sans ce
        // champ (cas de tous les autres modules aujourd'hui), repli EXACT sur
        // le comportement ODY1 : l'icône du premier item réellement ouvrable.
        icon: c.nav.icon ?? firstVisible.icon,
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
