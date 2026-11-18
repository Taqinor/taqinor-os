// I134 — Actions & récents pour la palette de commandes (⌘K). Module PUR
// (aucun import React) afin de rester testable côté `node:test`. La palette
// (providers/CommandPalette.jsx) s'en sert pour :
//   (a) un mode « Actions » de navigation directe, affiché quand la requête est
//       vide et filtré à la frappe, avec une PUCE DE RACCOURCI clavier par ligne ;
//   (b) la mémoire des entités récemment ouvertes via la palette, affichée quand
//       la palette est vide.
import { GOTO_SHORTCUTS, CREATE_SHORTCUTS } from './shortcuts.js'

// Source UNIQUE de vérité : on dérive les actions de navigation des raccourcis
// « g x » déjà définis (mêmes routes, mêmes libellés, même puce). Aucune route
// inventée — chaque `to` existe déjà dans le routeur (cf. GlobalSearch/ROUTE).
// ODY28 — une entrée de GOTO_SHORTCUTS peut porter `event` au lieu de `to`
// (surface en OVERLAY sans URL, ex. le lanceur d'applications « g o ») : elle
// n'est PAS une action de navigation et n'a rien à faire dans la palette, qui
// ferait sinon `navigate(undefined)`. On ne garde que les entrées routables.
export const NAV_ACTIONS = GOTO_SHORTCUTS.filter((s) => !!s.to).map((s) => ({
  id: s.keys.replace(/\s+/g, '-'), // ex. 'g-d'
  label: s.label, // ex. 'Aller au tableau de bord'
  to: s.to,
  keys: s.keys, // puce de raccourci, ex. 'g d'
}))

// VX220(b) — actions de CRÉATION (lead/devis/client), même source unique que
// NAV_ACTIONS (dérivées de CREATE_SHORTCUTS) : la palette les affiche dans
// leur PROPRE section « Créer », jamais mélangées à la navigation.
// TCH119 — même règle que NAV_ACTIONS : une entrée à `event` (« c t », feuille de
// saisie de Tâches en overlay) n'est pas une navigation ; seules les routables.
export const CREATE_ACTIONS = CREATE_SHORTCUTS.filter((s) => !!s.to).map((s) => ({
  id: s.keys.replace(/\s+/g, '-'), // ex. 'c-l'
  label: s.label, // ex. 'Créer un lead'
  to: s.to,
  keys: s.keys, // puce de raccourci, ex. 'c l'
}))

/**
 * filterActions — sous-ensemble de NAV_ACTIONS dont le libellé ou le raccourci
 * contient la requête (insensible à la casse). Requête vide → toutes les actions
 * (mode « par défaut » de la palette).
 */
export function filterActions(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return NAV_ACTIONS
  return NAV_ACTIONS.filter(
    (a) => a.label.toLowerCase().includes(q) || a.keys.toLowerCase().includes(q),
  )
}

/** filterCreateActions — même filtre que filterActions, sur CREATE_ACTIONS. */
export function filterCreateActions(query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return CREATE_ACTIONS
  return CREATE_ACTIONS.filter(
    (a) => a.label.toLowerCase().includes(q) || a.keys.toLowerCase().includes(q),
  )
}

// Raccord F2 (Tâches) — entrées de la palette SANS raccourci clavier propre (textes.md §2.1 « Palette ») : la
// recherche dans les tâches, Nouveau projet, Faire le bilan et les onglets. Toutes sont des routes réelles de
// `features/taches/module.config.jsx` ; la palette les filtre par `isPathVisible` comme les autres (module masqué
// pour le compte → aucune entrée). « Aujourd'hui » vient déjà de « g j » (NAV_ACTIONS).
export const TACHES_ACTIONS = [
  { id: 'taches-nouveau-projet', label: 'Nouveau projet', to: '/taches/projets?nouveau=1', keys: '' },
  { id: 'taches-bilan', label: 'Faire le bilan', to: '/taches/aujourdhui?ouvrir=bilan', keys: '' },
  { id: 'taches-a-trier', label: 'À trier', to: '/taches/a-trier', keys: '' },
  { id: 'taches-projets', label: 'Projets', to: '/taches/projets', keys: '' },
  { id: 'taches-agenda', label: 'Agenda', to: '/taches/agenda', keys: '' },
]

/**
 * filterTachesActions — TACHES_ACTIONS filtrées comme filterActions, précédées de la recherche : à vide
 * « Chercher dans mes tâches », sinon « Chercher « {q} » dans mes tâches » (la requête part dans `?q=`).
 */
export function filterTachesActions(query) {
  const brut = (query || '').trim()
  const q = brut.toLowerCase()
  const chercher = brut
    ? { id: 'taches-chercher', label: `Chercher « ${brut} » dans mes tâches`, to: `/taches/recherche?q=${encodeURIComponent(brut)}`, keys: '' }
    : { id: 'taches-chercher', label: 'Chercher dans mes tâches', to: '/taches/recherche', keys: '' }
  return [chercher, ...TACHES_ACTIONS.filter((a) => !q || a.label.toLowerCase().includes(q))]
}

/**
 * filterContextActions — LW26 : filtre une liste d'actions CONTEXTUELLES
 * arbitraires (posées par un écran de détail tant qu'il est monté — ex.
 * `taqinor:lead-workspace-actions` de features/crm/workspace/LeadWorkspace.jsx)
 * par le même critère que filterActions/filterCreateActions (libellé,
 * insensible à la casse). Ces actions n'ont pas de `keys` (pas de raccourci
 * clavier dédié) — filtre donc UNIQUEMENT sur `label`. Requête vide → toutes
 * les actions fournies, inchangées ; `actions` absent/vide → [].
 */
export function filterContextActions(actions, query) {
  const list = actions || []
  const q = (query || '').trim().toLowerCase()
  if (!q) return list
  return list.filter((a) => a.label.toLowerCase().includes(q))
}

// ── Mémoire des entités récemment ouvertes via la palette ────────────────────
export const RECENT_KEY = 'taqinor.cmdk.recent'
const RECENT_MAX = 6

// Accès localStorage tolérant : pas de `window` (SSR / test sans stub) → [].
function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

export function readRecentEntities() {
  const s = storage()
  if (!s) return []
  try {
    const raw = s.getItem(RECENT_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr.slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}

/**
 * pushRecentEntity — place l'entité ouverte en tête (dédoublonnée par type+id),
 * tronque à RECENT_MAX, persiste, et renvoie la nouvelle liste. Entité invalide
 * ou stockage indisponible → renvoie la liste courante sans rien écrire.
 *
 * NTUX11 — chaque entrée porte désormais `ts` (horodatage d'ouverture,
 * `Date.now()`), champ ADDITIF : les entrées déjà en localStorage sans `ts`
 * restent lisibles (`ts` vaut simplement `undefined`) — RecentEntitiesWidget
 * l'affiche en horodatage relatif (`lib/format.js timeAgo`), le reste
 * (palette ⌘K) l'ignore, comportement inchangé.
 */
export function pushRecentEntity(entity) {
  if (!entity || entity.id == null || !entity.type) return readRecentEntities()
  const s = storage()
  if (!s) return []
  try {
    const prev = readRecentEntities().filter(
      (e) => !(e.type === entity.type && String(e.id) === String(entity.id)),
    )
    const next = [
      { type: entity.type, id: entity.id, label: entity.label || '', ts: Date.now() },
      ...prev,
    ].slice(0, RECENT_MAX)
    s.setItem(RECENT_KEY, JSON.stringify(next))
    return next
  } catch {
    return readRecentEntities()
  }
}
