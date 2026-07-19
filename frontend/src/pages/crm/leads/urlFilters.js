// LB22 — URL partageable (blueprint D5/I7) : module PUR encode/decode
// `filters` + `view` ↔ URLSearchParams. Zéro dépendance React — testable
// avec `node --test`.
//
// N'écrit/NE LIT que les clés qu'il gère (les clés de EMPTY_FILTERS +
// `view`) : `?lead=`/`?new=`/`?equipe=` (deep-links existants — lien fiche
// VX/onOpenDuplicate, raccourci clavier « c l », VX236 lien équipe) ne sont
// JAMAIS touchés — `writeFiltersToParams` ne fait que set/delete SES propres
// clés sur une copie du `URLSearchParams` reçu, tout le reste survit
// intact ; `readFiltersFromParams`/`readViewFromParams` ne lisent jamais que
// les leurs.
import { EMPTY_FILTERS } from '../../../features/crm/stages.js'

export const DEFAULT_VIEW = 'kanban'
export const VALID_VIEWS = ['kanban', 'liste', 'calendrier', 'graphique', 'carte', 'prevision']

const FILTER_KEYS = Object.keys(EMPTY_FILTERS)

// Vrai si l'URL porte au moins UNE des clés de filtre gérées ici — sert à
// décider la priorité URL > localStorage > défauts au premier chargement
// (LeadsPage.jsx) : une URL collée (même partielle) gagne toujours sur les
// filtres persistés. La vue (`?view=`) est décidée séparément
// (`readViewFromParams` renvoie `null` si absente) : un lien qui ne porte
// QUE des filtres ne doit pas réinitialiser une vue déjà choisie, et
// inversement.
export function hasUrlFilterState(params) {
  return FILTER_KEYS.some((k) => params.has(k))
}

// Filtres dérivés de l'URL, complétés par EMPTY_FILTERS pour les clés
// absentes — jamais par localStorage : quand l'URL est la source retenue,
// elle l'est pour TOUTES les clés (comportement reproductible, jamais un
// mélange URL+localStorage sur une même page).
export function readFiltersFromParams(params) {
  const filters = { ...EMPTY_FILTERS }
  for (const key of FILTER_KEYS) {
    if (!params.has(key)) continue
    const raw = params.get(key)
    filters[key] = typeof EMPTY_FILTERS[key] === 'boolean' ? raw === 'true' : raw
  }
  return filters
}

// Vue dérivée de `?view=` — `null` si absente ou invalide (l'appelant garde
// alors sa propre valeur par défaut/localStorage).
export function readViewFromParams(params) {
  const v = params.get('view')
  return VALID_VIEWS.includes(v) ? v : null
}

// Nouveau URLSearchParams (jamais de mutation de `params`) : pose les clés
// de filtres NON-défaut + `view` (omise quand elle vaut DEFAULT_VIEW, pour
// une URL courte par défaut), retire celles qui reviennent au défaut, et
// laisse TOUT le reste (lead/new/equipe, toute clé future inconnue)
// parfaitement intact — on ne touche jamais que les clés qu'on gère.
export function writeFiltersToParams(params, filters, view) {
  const next = new URLSearchParams(params)
  const f = { ...EMPTY_FILTERS, ...(filters ?? {}) }
  for (const key of FILTER_KEYS) {
    const value = f[key]
    const isDefault = value === EMPTY_FILTERS[key] || value == null || value === ''
    if (isDefault) next.delete(key)
    else next.set(key, String(value))
  }
  if (!view || view === DEFAULT_VIEW) next.delete('view')
  else next.set('view', view)
  return next
}

export default {
  DEFAULT_VIEW,
  VALID_VIEWS,
  hasUrlFilterState,
  readFiltersFromParams,
  readViewFromParams,
  writeFiltersToParams,
}
