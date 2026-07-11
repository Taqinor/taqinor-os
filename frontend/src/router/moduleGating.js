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
