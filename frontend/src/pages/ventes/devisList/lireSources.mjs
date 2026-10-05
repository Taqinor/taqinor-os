// SPL203 — utilitaire de TEST : la source de la liste des devis.
//
// DevisList.jsx est découpé (move only) en fichiers sous devisList/ (DevisRow,
// puis les flux PDF / envoi et l'en-tête). Les gardes de source qui épinglaient
// une chaîne de DevisList.jsx lisent désormais la concaténation de DevisList.jsx
// ET de devisList/*.{js,jsx} (ordre stable : DevisList.jsx d'abord, puis les
// fichiers du dossier par ordre alphabétique) — elles suivent le code où qu'il
// vive, sans jamais s'affaiblir. Les tests (*.test.*) et ce fichier (.mjs) sont
// exclus.
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const ICI = dirname(fileURLToPath(import.meta.url))

export function fichiersSourcesDevisList() {
  const dossier = readdirSync(ICI)
    .filter((f) => /\.(js|jsx)$/.test(f) && !f.includes('.test.'))
    .sort()
    .map((f) => join(ICI, f))
  return [join(ICI, '..', 'DevisList.jsx'), ...dossier]
}

export function lireSourcesDevisList() {
  return fichiersSourcesDevisList().map((f) => readFileSync(f, 'utf8')).join('\n')
}
