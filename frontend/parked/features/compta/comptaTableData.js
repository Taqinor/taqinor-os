/* APX33 — la logique PURE du tableau de la compta (tri + CSV), isolée du JSX
   pour être testable sans DOM ni bundler — même patron que
   `features/ventes/devisBoard.js`. */

// Valeur utilisée pour trier ET pour l'export : `sortValue` si la colonne en
// fournit une, sinon la valeur brute de la ligne.
export function rawValue(col, row) {
  if (typeof col.sortValue === 'function') return col.sortValue(row)
  return row?.[col.key]
}

export function compareValues(a, b) {
  if (a == null && b == null) return 0
  if (a == null) return 1
  if (b == null) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), 'fr')
}

export function sortRows(columns, rows, sort) {
  if (!sort?.key) return rows
  const col = columns.find((c) => c.key === sort.key)
  if (!col) return rows
  const copy = [...rows]
  copy.sort((a, b) => {
    const cmp = compareValues(rawValue(col, a), rawValue(col, b))
    return sort.dir === 'asc' ? cmp : -cmp
  })
  return copy
}

/* CSV construit dans le NAVIGATEUR à partir des lignes déjà chargées — aucun
   endpoint nouveau. Séparateur `;` et BOM UTF-8 : Excel FR l'ouvre sans casser
   les accents. */
export function toCsv(columns, rows) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const head = columns.map((c) => esc(c.label ?? c.key)).join(';')
  const body = rows.map((r) => columns.map((c) => esc(rawValue(c, r))).join(';'))
  return '﻿' + [head, ...body].join('\r\n')
}
