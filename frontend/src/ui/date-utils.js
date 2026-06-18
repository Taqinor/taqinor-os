/* G24 — Maths de calendrier pures (zéro dépendance, testables en .mjs).
   Toutes les fonctions raisonnent sur l'heure LOCALE et ne mutent jamais
   leurs arguments. La couche d'affichage (DatePicker) délègue le formatage
   fr-FR / jj-mm-aaaa à `lib/format.js`. */

const DAY_MS = 24 * 60 * 60 * 1000

/** Lundi=0 … Dimanche=6 (la semaine FR commence le lundi). */
export function weekdayMondayFirst(date) {
  return (date.getDay() + 6) % 7
}

/** Date locale à minuit (sans heure) — base de toute comparaison de jour. */
export function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** Aujourd'hui à minuit (heure locale). */
export function today() {
  return startOfDay(new Date())
}

/** Deux dates tombent-elles le même jour calendaire ? */
export function isSameDay(a, b) {
  if (!a || !b) return false
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

/** Même mois ET même année ? */
export function isSameMonth(a, b) {
  if (!a || !b) return false
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
}

/** Nombre de jours dans le mois (month: 0–11). */
export function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate()
}

/** Ajoute `n` jours (n négatif autorisé), renvoie une nouvelle Date à minuit. */
export function addDays(date, n) {
  const d = startOfDay(date)
  d.setDate(d.getDate() + n)
  return d
}

/** Ajoute `n` mois en préservant au mieux le jour (clamp en fin de mois court). */
export function addMonths(date, n) {
  const y = date.getFullYear()
  const m = date.getMonth() + n
  const targetY = y + Math.floor(m / 12)
  const targetM = ((m % 12) + 12) % 12
  const day = Math.min(date.getDate(), daysInMonth(targetY, targetM))
  return new Date(targetY_safe(targetY), targetM, day)
}
// Évite -0 et conserve un entier propre pour l'année.
function targetY_safe(y) { return y | 0 }

/** Nombre de jours pleins entre deux dates (b - a), basé sur minuit local. */
export function diffDays(a, b) {
  return Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / DAY_MS)
}

/**
 * Grille du mois affiché : 6 semaines × 7 jours (42 cellules), commençant au
 * lundi de la semaine du 1er. Chaque cellule porte sa date et `inMonth`.
 */
export function buildMonthGrid(year, month) {
  const first = new Date(year, month, 1)
  const lead = weekdayMondayFirst(first) // jours du mois précédent à afficher
  const startCell = addDays(first, -lead)
  const cells = []
  for (let i = 0; i < 42; i += 1) {
    const date = addDays(startCell, i)
    cells.push({ date, inMonth: date.getMonth() === month && date.getFullYear() === year })
  }
  return cells
}

/**
 * Une date est-elle désactivée ? Bornes `min`/`max` (incluses) + prédicat
 * libre `disabled(date) => bool`. Toutes optionnelles.
 */
export function isDateDisabled(date, { min, max, disabled } = {}) {
  const d = startOfDay(date)
  if (min && d.getTime() < startOfDay(min).getTime()) return true
  if (max && d.getTime() > startOfDay(max).getTime()) return true
  if (typeof disabled === 'function' && disabled(d)) return true
  return false
}

/** La date tombe-t-elle dans l'intervalle [start, end] (bornes incluses) ? */
export function isWithinRange(date, start, end) {
  if (!start || !end) return false
  const t = startOfDay(date).getTime()
  const a = startOfDay(start).getTime()
  const b = startOfDay(end).getTime()
  const lo = Math.min(a, b)
  const hi = Math.max(a, b)
  return t >= lo && t <= hi
}

/**
 * Applique un clic sur une cellule à un intervalle en cours de sélection.
 * - rien sélectionné, ou intervalle complet → démarre un nouvel intervalle.
 * - un seul bord posé → ferme l'intervalle (réordonne si on clique avant).
 * Renvoie toujours `{ start, end }` (end peut rester null).
 */
export function applyRangeSelection(range, date) {
  const d = startOfDay(date)
  const { start, end } = range || {}
  if (!start || (start && end)) {
    return { start: d, end: null }
  }
  // un seul bord posé → on ferme
  if (d.getTime() < startOfDay(start).getTime()) {
    return { start: d, end: start }
  }
  return { start, end: d }
}

/** Parse "HH:mm" → { h, m } (0–23 / 0–59) ou null si invalide. */
export function parseTime(value) {
  if (typeof value !== 'string') return null
  const m = value.trim().match(/^(\d{1,2}):(\d{2})$/)
  if (!m) return null
  const h = Number(m[1])
  const min = Number(m[2])
  if (h < 0 || h > 23 || min < 0 || min > 59) return null
  return { h, m: min }
}

/** Formate { h, m } (ou h,m séparés) en "HH:mm" zéro-padé. */
export function formatTime(h, m) {
  if (typeof h === 'object' && h !== null) { m = h.m; h = h.h }
  const hh = String(Math.max(0, Math.min(23, h | 0))).padStart(2, '0')
  const mm = String(Math.max(0, Math.min(59, m | 0))).padStart(2, '0')
  return `${hh}:${mm}`
}

/** Liste de créneaux "HH:mm" sur 24 h, pas configurable (défaut 30 min). */
export function timeOptions(stepMinutes = 30) {
  const step = Math.max(1, stepMinutes | 0)
  const out = []
  for (let total = 0; total < 24 * 60; total += step) {
    out.push(formatTime(Math.floor(total / 60), total % 60))
  }
  return out
}

/** Libellés courts des jours (lundi-first) pour l'en-tête du calendrier. */
export const WEEKDAY_LABELS = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']

/** Noms de mois fr-FR (capitalisés), index 0–11. */
export const MONTH_LABELS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
