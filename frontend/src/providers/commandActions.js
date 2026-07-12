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
export const NAV_ACTIONS = GOTO_SHORTCUTS.map((s) => ({
  id: s.keys.replace(/\s+/g, '-'), // ex. 'g-d'
  label: s.label, // ex. 'Aller au tableau de bord'
  to: s.to,
  keys: s.keys, // puce de raccourci, ex. 'g d'
}))

// VX220(b) — actions de CRÉATION (lead/devis/client), même source unique que
// NAV_ACTIONS (dérivées de CREATE_SHORTCUTS) : la palette les affiche dans
// leur PROPRE section « Créer », jamais mélangées à la navigation.
export const CREATE_ACTIONS = CREATE_SHORTCUTS.map((s) => ({
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
      { type: entity.type, id: entity.id, label: entity.label || '' },
      ...prev,
    ].slice(0, RECENT_MAX)
    s.setItem(RECENT_KEY, JSON.stringify(next))
    return next
  } catch {
    return readRecentEntities()
  }
}
