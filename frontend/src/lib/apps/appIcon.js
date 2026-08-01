// ODY9 — Résolution de l'icône/accent d'une app par CLÉ de module.
// ----------------------------------------------------------------------------
// Complément de `ui/AppIcon.jsx` (présentation pure) pour les surfaces qui ne
// disposent PAS déjà d'une entrée `useInstalledApps()` — au premier chef
// l'écran Applications (ODX5), qui liste le catalogue BACKEND (y compris des
// modules sans écran frontend) et résolvait donc l'icône depuis le manifest :
// deux glyphes possibles pour la même app, exactement l'incohérence que ODY9
// supprime.
//
// La résolution lit le registre frontend (`moduleConfigs`, UX1) — la MÊME
// source que `useInstalledApps()` (ODY1) — SANS filtrage par rôle ni par
// module actif : ce n'est pas une décision de visibilité (celle-là appartient
// à ODY1), seulement « à quoi ressemble cette app ». Un module absent du
// registre renvoie `null` : l'appelant garde son repli.
import { moduleConfigs } from '../../router/moduleRoutes'

function configFor(key) {
  if (!key) return null
  return moduleConfigs.find((c) => c.key === key) || null
}

/**
 * iconNodeForApp — nœud d'icône (élément lucide) déclaré par le module dans
 * son `module.config.jsx`, ou `null` si le module n'a pas d'écran frontend.
 */
export function iconNodeForApp(key) {
  const config = configFor(key)
  const items = config?.nav?.items ?? []
  const item = items.find((it) => it?.icon)
  return item?.icon ?? null
}

/** accentForApp — clé d'accent module VX8 ('azur', 'brass'…), ou `undefined`. */
export function accentForApp(key) {
  return configFor(key)?.nav?.accent
}
