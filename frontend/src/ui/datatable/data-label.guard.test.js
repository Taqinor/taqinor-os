// VX50 — garde CI anti-régression : sous 768px, `.data-table` se replie en
// cartes qui n'affichent le nom du champ que via `content: attr(data-label)`
// (index.css). Un fichier de page qui rend un tableau `className="data-table"`
// avec des `<td>` mais AUCUN `data-label` produit une pile de valeurs nues sur
// mobile (bug FactureList/RelancesPage corrigé par VX50). Ce test statique
// (fs + regex, ZÉRO dépendance) échoue si un tel fichier réapparaît.
//
// Runnable en Node pur : `node --test src/ui/datatable/data-label.guard.test.js`
// (extension .js, exclue du glob vitest `src/**/*.test.jsx` — voir
// vitest.config.js — donc jamais double-exécuté).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
// frontend/src/ui/datatable → frontend/src
const SRC_DIR = join(__dirname, '..', '..')
const PAGES_DIR = join(SRC_DIR, 'pages')

// VX50 corrige FactureList.jsx + RelancesPage.jsx (portée de la tâche). Ces
// deux fichiers préexistants ont le MÊME bug (table.data-table + <td> sans
// data-label) mais sont HORS PÉRIMÈTRE ici — à corriger dans une tâche dédiée
// (voir docs/PLAN2.md/ERROR_PLAN.md) ; whitelist temporaire et EXPLICITE pour
// que la garde reste verte sans masquer une VRAIE régression ailleurs.
const PRE_EXISTING_EXCEPTIONS = new Set([
  join(PAGES_DIR, 'admin', 'TenantsConsole.jsx'),
  join(PAGES_DIR, 'ventes', 'VentesKanban.jsx'),
])

// Liste récursive des fichiers .jsx sous src/pages/**.
function listJsxFiles(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      out.push(...listJsxFiles(full))
    } else if (entry.endsWith('.jsx') && !entry.endsWith('.test.jsx')) {
      out.push(full)
    }
  }
  return out
}

test('tout fichier de page rendant un tableau data-table avec des <td> porte au moins un data-label', () => {
  const files = listJsxFiles(PAGES_DIR)
  const offenders = []

  for (const file of files) {
    if (PRE_EXISTING_EXCEPTIONS.has(file)) continue
    const content = readFileSync(file, 'utf8')
    if (!content.includes('className="data-table')) continue
    const hasTd = /<td[\s>]/.test(content)
    if (!hasTd) continue
    const hasDataLabel = /data-label=/.test(content)
    if (!hasDataLabel) offenders.push(file)
  }

  assert.deepEqual(
    offenders, [],
    `Fichier(s) avec table.data-table + <td> mais ZÉRO data-label (carte mobile `
    + `sans libellé lisible) : ${offenders.join(', ')}`,
  )
})

test('sanity — au moins un fichier de page utilise réellement data-table (le test précédent ne passe pas par défaut d\'absence)', () => {
  const files = listJsxFiles(PAGES_DIR)
  const withDataTable = files.filter(
    (f) => readFileSync(f, 'utf8').includes('className="data-table'),
  )
  assert.ok(withDataTable.length > 0, 'aucun fichier pages/** ne rend .data-table — vérifier le scan')
})
