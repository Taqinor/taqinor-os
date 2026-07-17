// NTUX3 — Filtres avancés composables ET/OU (2 niveaux max). Module PUR
// (aucun import React), appliqué EN MÉMOIRE sur les données déjà chargées
// par `<DataTable>` — aucun nouvel endpoint backend. Sérialisé dans
// `SavedView.configuration.filtres` (NTUX1) au format
// `{ op: 'AND'|'OR', conditions: [...] }` où chaque condition est soit une
// feuille `{ field, operator, value }`, soit un GROUPE imbriqué (niveau 2 max
// — un groupe imbriqué ne contient QUE des feuilles, jamais un 3e niveau).
import { resolveRelativeRange } from '../../lib/relativeDates.js'

export const OPERATORS_BY_TYPE = {
  text: [
    { id: 'contains', label: 'contient' },
    { id: 'not_contains', label: 'ne contient pas' },
    { id: 'eq', label: 'égal' },
    { id: 'empty', label: 'vide' },
    { id: 'not_empty', label: 'non vide' },
  ],
  number: [
    { id: 'eq', label: '=' },
    { id: 'neq', label: '≠' },
    { id: 'gt', label: '>' },
    { id: 'lt', label: '<' },
    { id: 'between', label: 'entre' },
  ],
  date: [
    { id: 'before', label: 'avant' },
    { id: 'after', label: 'après' },
    { id: 'between', label: 'entre' },
    // NTUX4 — presets de date relative, résolus à l'affichage (jamais
    // persistés comme dates absolues) : cf. lib/relativeDates.js.
    { id: 'relative', label: 'période relative' },
  ],
  select: [
    { id: 'is', label: 'est' },
    { id: 'is_not', label: "n'est pas" },
    { id: 'in', label: 'dans' },
  ],
}

// Opérateurs qui n'ont besoin d'AUCUNE valeur saisie (feuille valide sans `value`).
const NO_VALUE_OPERATORS = new Set(['empty', 'not_empty'])

export function operatorsForType(type) {
  return OPERATORS_BY_TYPE[type] || OPERATORS_BY_TYPE.text
}

export function emptyCondition(field, type = 'text') {
  return { field, operator: operatorsForType(type)[0].id, value: '' }
}

export function emptyGroup(op = 'AND') {
  return { op, conditions: [] }
}

export function isGroup(node) {
  return !!node && Array.isArray(node.conditions)
}

function resolveValue(row, field, columns) {
  const col = columns.find((c) => c.id === field)
  if (!col) return row?.[field]
  return col.accessor ? col.accessor(row) : row?.[field]
}

/** Évalue une CONDITION FEUILLE sur une ligne. `value` peut être une paire
 *  [min, max] pour `between`, ou déjà résolue en {debut, fin} pour une date
 *  relative (NTUX4 — résolution faite par l'appelant AVANT évaluation). */
function matchLeaf(row, condition, columns) {
  const raw = resolveValue(row, condition.field, columns)
  const { operator, value } = condition
  if (operator === 'empty') return raw === null || raw === undefined || raw === ''
  if (operator === 'not_empty') return !(raw === null || raw === undefined || raw === '')

  if (operator === 'contains' || operator === 'not_contains') {
    const hay = String(raw ?? '').toLowerCase()
    const needle = String(value ?? '').toLowerCase()
    const has = needle !== '' && hay.includes(needle)
    return operator === 'contains' ? has : !has
  }
  if (operator === 'eq') return String(raw ?? '') === String(value ?? '')
  if (operator === 'neq') return Number(raw) !== Number(value)
  if (operator === 'gt') return Number(raw) > Number(value)
  if (operator === 'lt') return Number(raw) < Number(value)
  if (operator === 'between') {
    const [min, max] = Array.isArray(value) ? value : [null, null]
    const n = raw instanceof Date ? raw.getTime() : Number(raw)
    const lo = min instanceof Date ? min.getTime() : (min != null && min !== '' ? Number(min) : null)
    const hi = max instanceof Date ? max.getTime() : (max != null && max !== '' ? Number(max) : null)
    if (lo != null && n < lo) return false
    if (hi != null && n > hi) return false
    return true
  }
  if (operator === 'before') return new Date(raw).getTime() < new Date(value).getTime()
  if (operator === 'after') return new Date(raw).getTime() > new Date(value).getTime()
  if (operator === 'relative') {
    // NTUX4 — RÉÉVALUÉ à CHAQUE appel (jamais une borne mise en cache) : une
    // vue sauvegardée avec « ce trimestre » montre toujours le trimestre
    // COURANT, jamais celui de la date de sauvegarde.
    const range = resolveRelativeRange(value)
    if (!range) return true
    const t = new Date(raw).getTime()
    return t >= range.debut.getTime() && t <= range.fin.getTime()
  }
  if (operator === 'is') return String(raw ?? '') === String(value ?? '')
  if (operator === 'is_not') return String(raw ?? '') !== String(value ?? '')
  if (operator === 'in') {
    const list = Array.isArray(value) ? value : []
    return list.map(String).includes(String(raw ?? ''))
  }
  return true
}

/** Évalue un GROUPE (ou une feuille) sur une ligne — récursif, mais la
 *  profondeur reste bornée à 2 niveaux par construction de l'UI
 *  (FilterBuilder.jsx n'autorise pas de sous-groupe DANS un sous-groupe). */
export function evaluateNode(row, node, columns) {
  if (!node) return true
  if (isGroup(node)) {
    if (node.conditions.length === 0) return true
    const results = node.conditions.map((c) => evaluateNode(row, c, columns))
    return node.op === 'OR' ? results.some(Boolean) : results.every(Boolean)
  }
  return matchLeaf(row, node, columns)
}

/** Filtre `rows` selon le groupe racine. Groupe vide/absent → aucune ligne
 *  exclue (comportement neutre, comme un filtre non appliqué). */
export function applyFilterGroup(rows, group, columns) {
  if (!group || !isGroup(group) || group.conditions.length === 0) return rows
  return rows.filter((row) => evaluateNode(row, group, columns))
}

/** Une condition feuille est "complète" (prête à filtrer) : opérateur choisi,
 *  et une valeur saisie sauf pour les opérateurs sans valeur. */
export function isLeafComplete(leaf) {
  if (!leaf || !leaf.field || !leaf.operator) return false
  if (NO_VALUE_OPERATORS.has(leaf.operator)) return true
  if (leaf.operator === 'between') {
    const [min, max] = Array.isArray(leaf.value) ? leaf.value : []
    return (min != null && min !== '') || (max != null && max !== '')
  }
  if (leaf.operator === 'in') return Array.isArray(leaf.value) && leaf.value.length > 0
  return leaf.value != null && leaf.value !== ''
}

export function leafNeedsValue(operator) {
  return !NO_VALUE_OPERATORS.has(operator)
}
