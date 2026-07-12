/* ============================================================================
   H33 — Sérialisation CSV côté client (fallback d'export sans backend).
   ----------------------------------------------------------------------------
   Logique PURE : prend des lignes + une description de colonnes et renvoie une
   chaîne CSV RFC-4180. Le composant injecte un callback `onExport` si un
   endpoint serveur existe ; sinon il appelle `rowsToCSV` + déclenche un
   téléchargement Blob. Aucun code backend ici.
   ========================================================================== */

/** BOM UTF-8 (U+FEFF) — préfixe pour qu'Excel (fr) ouvre les accents. */
export const UTF8_BOM = String.fromCharCode(0xfeff)

/** Échappe une cellule CSV (guillemets si virgule, guillemet, saut de ligne).
 *  ERR97 — Garde anti-injection de formules : une cellule commençant par
 *  `=` `+` `-` `@` est interprétée comme une formule par Excel/Sheets. On
 *  préfixe alors une apostrophe pour neutraliser l'exécution (technique OWASP),
 *  AVANT le quoting RFC-4180. */
export function escapeCSVCell(value, { delimiter = ',' } = {}) {
  if (value === null || value === undefined) return ''
  let str = String(value)
  if (/^[=+\-@]/.test(str)) str = `'${str}`
  if (str.includes('"') || str.includes(delimiter) || /[\r\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/**
 * Construit le CSV. `columns` = [{ id, header, exportValue?(row)->any }].
 * Par défaut la valeur exportée est `row[id]`. `bom` ajoute le BOM UTF-8 pour
 * qu'Excel (fr) ouvre correctement les accents.
 */
export function rowsToCSV(rows, columns, { delimiter = ',', bom = true, eol = '\r\n' } = {}) {
  const cols = columns || []
  const headerCells = cols.map((c) => escapeCSVCell(c.header ?? c.id, { delimiter }))
  const lines = [headerCells.join(delimiter)]
  for (const row of rows || []) {
    const cells = cols.map((c) => {
      const raw = typeof c.exportValue === 'function' ? c.exportValue(row) : row?.[c.id]
      return escapeCSVCell(raw, { delimiter })
    })
    lines.push(cells.join(delimiter))
  }
  const body = lines.join(eol)
  return bom ? UTF8_BOM + body : body
}

/**
 * VX110 — Sérialise en TSV (séparé par tabulations), SANS BOM. C'est exactement
 * ce qu'Excel/Sheets produisent au copier : collé dans une feuille, chaque `\t`
 * crée une colonne et chaque ligne une rangée — collage aligné gratuit, sans
 * passer par un fichier. Réutilise `escapeCSVCell` (garde anti-injection ERR97)
 * avec le délimiteur tabulation, donc une cellule contenant une tabulation ou un
 * saut de ligne est correctement quotée.
 */
export function rowsToTSV(rows, columns, { eol = '\r\n' } = {}) {
  return rowsToCSV(rows, columns, { delimiter: '\t', bom: false, eol })
}

/** Nom de fichier d'export horodaté : « base-2026-06-18.csv ». */
export function exportFileName(base = 'export', { ext = 'csv', date = new Date() } = {}) {
  const d = date instanceof Date && !Number.isNaN(date.getTime()) ? date : new Date()
  const stamp = [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0'),
  ].join('-')
  const safe = String(base).replace(/[^\w-]+/g, '-').replace(/^-+|-+$/g, '') || 'export'
  return `${safe}-${stamp}.${ext}`
}
