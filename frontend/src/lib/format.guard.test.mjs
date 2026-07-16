/* ============================================================================
   VX75 — Garde statique : `formatMAD`/`formatNumber`/`formatDate`/`formatPercent`
   (lib/format.js) sont la SEULE source de vérité pour l'affichage argent/date.
   ----------------------------------------------------------------------------
   `lib/format.js` se disait déjà « une seule source de vérité » mais ~90 sites
   dans ~45 fichiers roulaient leur propre `toLocaleString` avec deux tags
   concurrents (fr-FR vs fr-MA) — d'où le bug visible CatalogueTable
   `450.00 HT` vs DevisList `450,00 MAD`. Ce test échoue (rouge) si un nouveau
   `.toLocaleString(` apparaît hors `lib/format.js` dans le code source (hors
   tests) — plus jamais de contournement silencieux.

   Node stdlib pur (fs + node:test) — zéro dépendance ajoutée, auto-découvert
   par le glob CI de node --test sur les fichiers *.test.mjs sous src/ (aucun
   câblage CI supplémentaire requis).
   ========================================================================== */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SRC_ROOT = path.resolve(__dirname, '..') // frontend/src

// Le seul fichier autorisé à appeler `toLocaleString` nativement — c'est
// l'implémentation centrale que tout le reste doit utiliser.
const ALLOWED_FILE = path.join(SRC_ROOT, 'lib', 'format.js')

// Exceptions ÉTROITES et NOMMÉES (pas un dossier, pas un pattern large) : VX75
// ne couvre que l'argent/nombre/date/pourcentage. `formatOctets` formate une
// TAILLE EN OCTETS (Ko/Mo/Go) — hors périmètre de lib/format.js, qui n'a pas
// (et n'a pas besoin d'avoir) de helper octets. Toute nouvelle entrée ici doit
// être justifiée au même titre : une unité non money/date/percent légitime.
const ALLOWED_EXCEPTIONS = new Set([
  path.join(SRC_ROOT, 'features', 'ged', 'advanced', 'shared.js'), // formatOctets — Ko/Mo/Go, pas de l'argent
])

// Extensions source scannées ; les tests (*.test.js(x)/*.test.mjs) et les
// fixtures/mocks ne sont pas la cible de cette garde (ils peuvent légitimement
// exercer `toLocaleString` nu pour vérifier un comportement Intl natif).
const SOURCE_EXT = new Set(['.js', '.jsx', '.mjs'])
const SKIP_DIRS = new Set(['node_modules', 'dist', 'build', '.git'])

function isTestFile(fileName) {
  return /\.test\.(jsx?|mjs)$/.test(fileName) || /\.stories\.(jsx?|mjs)$/.test(fileName)
}

function walk(dir, out) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue
    const full = path.join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) {
      walk(full, out)
    } else if (SOURCE_EXT.has(path.extname(entry)) && !isTestFile(entry)) {
      out.push(full)
    }
  }
  return out
}

/** Retourne la liste des fichiers (hors lib/format.js, hors tests) qui
 * appellent encore `.toLocaleString(` en dehors de la source de vérité. */
export function findStrayToLocaleString(root = SRC_ROOT) {
  const files = walk(root, [])
  const offenders = []
  for (const file of files) {
    if (file === ALLOWED_FILE || ALLOWED_EXCEPTIONS.has(file)) continue
    const content = readFileSync(file, 'utf8')
    if (content.includes('.toLocaleString(')) {
      const lines = content.split('\n')
      const hits = []
      lines.forEach((line, i) => {
        if (line.includes('.toLocaleString(')) hits.push(i + 1)
      })
      offenders.push({ file: path.relative(SRC_ROOT, file), lines: hits })
    }
  }
  return offenders
}

test('VX75 — aucun nouveau .toLocaleString( hors lib/format.js', () => {
  const offenders = findStrayToLocaleString()
  if (offenders.length > 0) {
    const detail = offenders
      .map((o) => `  - ${o.file}:${o.lines.join(',')}`)
      .join('\n')
    assert.fail(
      `${offenders.length} fichier(s) contournent lib/format.js avec un ` +
      `.toLocaleString( natif — migrer vers formatMAD/formatNumber/` +
      `formatDate/formatPercent/formatDateTime :\n${detail}`,
    )
  }
  assert.equal(offenders.length, 0)
})
