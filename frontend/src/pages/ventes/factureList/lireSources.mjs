// SPL211 — utilitaire de TEST : la source de la liste des factures.
//
// FactureList.jsx est découpé (move only) en fichiers sous factureList/ (FactureRow,
// factureHelpers). Les gardes de source qui épinglaient
// une chaîne de FactureList.jsx lisent désormais la concaténation de FactureList.jsx
// ET de factureList/*.{js,jsx} (ordre stable : FactureList.jsx d'abord, puis les
// fichiers du dossier par ordre alphabétique) — elles suivent le code où qu'il
// vive, sans jamais s'affaiblir. Les tests (*.test.*) et ce fichier (.mjs) sont
// exclus.
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const ICI = dirname(fileURLToPath(import.meta.url))

export function fichiersSourcesFactureList() {
  const dossier = readdirSync(ICI)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.includes('.test.'))
    .sort()
    .map((f) => join(ICI, f))
  return [join(ICI, '..', 'FactureList.jsx'), ...dossier]
}

export function lireSourcesFactureList() {
  return fichiersSourcesFactureList().map((f) => readFileSync(f, 'utf8')).join('\n')
}
