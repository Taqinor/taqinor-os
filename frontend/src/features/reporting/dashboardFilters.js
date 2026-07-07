// XPLT9 — Filtre global de dashboard en cascade.
//
// FG381 (`core.Dashboard`) sauvegarde des widgets dans `layout` (JSON opaque,
// aucune table dédiée) mais chaque widget se filtre seul aujourd'hui. Ce
// module ajoute un jeu de filtres GLOBAUX (plage de dates, commercial, canal,
// catégorie produit) persistés dans `layout.globalFilters` — une clé
// additive du même JSON, donc AUCUNE migration — et propagés en paramètres à
// chaque widget/requête, sauf ceux qui ont explicitement opté out
// (`widget.optOutGlobalFilters === true`).
//
// Fonctions PURES (aucun réseau/React) : lecture/écriture de la clé dans un
// `layout` existant, et calcul des paramètres effectifs à envoyer à un
// widget donné. `coreApi.dashboards.updateLayout(id, layout)` est le seul
// point d'écriture réseau (câblé par le composant `DashboardFilterBar`).

export const DEFAULT_GLOBAL_FILTERS = {
  dateFrom: '',
  dateTo: '',
  commercial: '',
  canal: '',
  categorieProduit: '',
}

// Lit les filtres globaux mémorisés dans le layout d'un dashboard (tolérant :
// un layout vide/mal formé renvoie les valeurs par défaut, jamais une
// exception).
export function readGlobalFilters(layout) {
  const stored = layout && typeof layout === 'object' ? layout.globalFilters : null
  if (!stored || typeof stored !== 'object') return { ...DEFAULT_GLOBAL_FILTERS }
  return { ...DEFAULT_GLOBAL_FILTERS, ...stored }
}

// Renvoie un nouveau layout avec les filtres globaux mis à jour, en
// préservant tout le reste du JSON (widgets, disposition…) — ne mute jamais
// l'objet reçu.
export function writeGlobalFilters(layout, filters) {
  const base = layout && typeof layout === 'object' ? layout : {}
  return { ...base, globalFilters: { ...DEFAULT_GLOBAL_FILTERS, ...filters } }
}

// Ne garde que les filtres réellement définis (non vides), pour ne pas
// polluer les requêtes de query params vides.
function compact(filters) {
  return Object.fromEntries(
    Object.entries(filters || {}).filter(([, v]) => v != null && v !== ''),
  )
}

// Calcule les paramètres effectifs pour UN widget donné : fusionne les
// filtres globaux (si le widget n'a pas opté out) avec les paramètres
// propres du widget — un paramètre propre au widget l'emporte toujours sur
// le filtre global de même clé (le widget garde la main sur ses propres
// réglages fins).
export function effectiveParamsForWidget(widget, globalFilters) {
  const ownParams = (widget && widget.params) || {}
  if (widget?.optOutGlobalFilters) return { ...ownParams }
  return { ...compact(globalFilters), ...ownParams }
}

// Calcule les paramètres effectifs pour TOUS les widgets d'un layout — sert
// à recharger tous les widgets d'un coup quand un filtre global change.
export function effectiveParamsForAllWidgets(layout, globalFilters) {
  const widgets = (layout && Array.isArray(layout.widgets)) ? layout.widgets : []
  return widgets.map((w) => ({
    id: w.id,
    optedOut: !!w.optOutGlobalFilters,
    params: effectiveParamsForWidget(w, globalFilters),
  }))
}

// Vrai si au moins un filtre global est actif (utile pour afficher un badge
// "filtres actifs" / un bouton "réinitialiser").
export function hasActiveFilters(filters) {
  return Object.keys(compact(filters)).length > 0
}
