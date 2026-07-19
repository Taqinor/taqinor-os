// WIR69 — (a) suivi d'adoption sur changement de route + (b) téléchargement PDF
// du journal d'administration. Vérification de SOURCE (JSX, pas de node_modules
// dans ce lane — cf. pages/rapports-integrite.test.mjs pour la convention).
//   node --test src/features/adminops/adminops-wir69.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (...p) => readFileSync(join(HERE, ...p), 'utf8')
const TRACKER = read('..', '..', 'components', 'layout', 'UsageTracker.jsx')
const LAYOUT = read('..', '..', 'components', 'layout', 'Layout.jsx')
const API = read('adminopsApi.js')
const SETTINGS = read('AdminSettingsPage.jsx')

test('(a) UsageTracker trace une visite via adminopsApi.trackerUsage sur changement de pathname', () => {
  assert.match(TRACKER, /useLocation\(\)/)
  assert.match(TRACKER, /adminopsApi\.trackerUsage\(module, pathname\)/)
  // Débounce : ne re-trace pas le même pathname.
  assert.match(TRACKER, /pathname === last\.current/)
})

test('(a) le Layout monte UsageTracker', () => {
  assert.match(LAYOUT, /import UsageTracker from '\.\/UsageTracker'/)
  assert.match(LAYOUT, /<UsageTracker \/>/)
})

test('(b) adminopsApi expose journalAdminPdf en blob', () => {
  assert.match(API, /journalAdminPdf:[\s\S]*?journal-admin[\s\S]*?responseType: 'blob'/)
})

test('(b) l’écran Administration a un bouton de téléchargement du journal PDF', () => {
  assert.match(SETTINGS, /adminopsApi\.journalAdminPdf\(\)/)
  assert.match(SETTINGS, /Télécharger le journal \(PDF\)/)
})
