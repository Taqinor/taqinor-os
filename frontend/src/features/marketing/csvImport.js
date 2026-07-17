/* ============================================================================
   NTMKT5 — Import CSV de contacts : parsing + mapping de colonnes PURS
   (testables au node, aucune dépendance nouvelle).
   ----------------------------------------------------------------------------
   Parseur CSV minimal RFC-4180 (guillemets, virgules échappées, CRLF/LF) —
   miroir en lecture de `ui/datatable/csv.js` (écriture). `buildLignesImport`
   projette les lignes parsées vers la forme attendue par
   `marketing/listes-diffusion/<id>/importer/` : `{destinataire, contact_ref}`.
   ========================================================================== */

// Parse un texte CSV en { headers: string[], rows: string[][] }.
export function parseCsv(text) {
  const content = (text || '').replace(/^﻿/, '') // BOM éventuel
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < content.length; i++) {
    const ch = content[i]
    if (inQuotes) {
      if (ch === '"') {
        if (content[i + 1] === '"') { field += '"'; i++ } else { inQuotes = false }
      } else {
        field += ch
      }
      continue
    }
    if (ch === '"') { inQuotes = true; continue }
    if (ch === ',') { row.push(field); field = ''; continue }
    if (ch === '\r') continue
    if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ''; continue }
    field += ch
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row) }
  const nonEmpty = rows.filter(r => r.some(c => c !== ''))
  const [headers, ...body] = nonEmpty
  return { headers: headers || [], rows: body }
}

// Construit les lignes prêtes pour `marketing/listes-diffusion/<id>/importer/`
// à partir des lignes parsées + du mapping utilisateur (index de colonne).
export function buildLignesImport(rows, mapping) {
  const idxDest = mapping?.destinataire
  const idxRef = mapping?.contact_ref
  if (idxDest === '' || idxDest === undefined || idxDest === null) return []
  return (rows || [])
    .map(r => ({
      destinataire: (r[idxDest] || '').trim(),
      contact_ref: idxRef !== '' && idxRef !== undefined && idxRef !== null
        ? (r[idxRef] || '').trim() : '',
    }))
    .filter(l => l.destinataire)
}
