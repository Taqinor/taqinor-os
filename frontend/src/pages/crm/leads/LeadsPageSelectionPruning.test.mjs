// LB8 — la sélection est élaguée contre la liste FILTRÉE, pas contre tous les
// leads chargés (bug recon2-03 #6, blueprint I5). Avant ce fix, un lead
// sélectionné puis masqué par un filtre restait bulk-actionnable EN
// INVISIBLE (l'utilisateur ne le voyait plus mais une action en masse
// l'affectait quand même). Verified against SOURCE + la logique PURE réelle
// de pruneSelection (bulk.js, zéro dépendance — importable sans node_modules
// dans ce worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageSelectionPruning.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { pruneSelection } from '../../../features/crm/bulk.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB8 : LeadsPage.jsx élague visibleSelected contre `filtered`, plus contre `leads`', () => {
  const start = PAGE_SRC.indexOf('const visibleSelected = useMemo(')
  assert.ok(start > 0)
  const block = PAGE_SRC.slice(start, start + 250)
  assert.match(block, /pruneSelection\(selected, filtered\.map\(\(l\) => l\.id\)\)/)
  assert.match(block, /\[selected, filtered\]/)
  assert.doesNotMatch(block, /pruneSelection\(selected, leads\.map/)
})

test('LB8 : scénario DoD — 3 sélectionnés, filtre n\'en montre qu\'1 → la barre bulk n\'agit que sur celui-là', () => {
  const selected = new Set([1, 2, 3])
  // Filtrer réduit `filtered` à un seul lead visible (id 1) — `leads` (non
  // filtré) contient toujours les 3.
  const filtered = [{ id: 1 }]
  const visibleSelected = pruneSelection(selected, filtered.map((l) => l.id))
  assert.equal(visibleSelected.size, 1)
  assert.deepEqual([...visibleSelected], [1])
})

test('LB8 : scénario DoD — retirer le filtre fait réapparaître les 3 sélectionnés (selected N\'EST PAS muté)', () => {
  const selected = new Set([1, 2, 3])
  // Étape 1 : filtré à 1 seul visible.
  const filteredNarrow = [{ id: 1 }]
  pruneSelection(selected, filteredNarrow.map((l) => l.id))
  // `selected` (l'état BRUT React) est un Set DÉRIVÉ, jamais muté par
  // pruneSelection (fonction pure — retourne toujours un NOUVEAU Set).
  assert.deepEqual([...selected].sort(), [1, 2, 3])
  // Étape 2 : filtre retiré, les 3 leads redeviennent visibles.
  const filteredAll = [{ id: 1 }, { id: 2 }, { id: 3 }]
  const visibleSelected = pruneSelection(selected, filteredAll.map((l) => l.id))
  assert.deepEqual([...visibleSelected].sort(), [1, 2, 3])
})

test('LB8 : un lead sélectionné puis SUPPRIMÉ (disparu de `leads` ET `filtered`) reste correctement élagué', () => {
  const selected = new Set([1, 2, 3])
  const filtered = [{ id: 1 }, { id: 3 }] // le lead 2 a été supprimé/archivé hors vue
  const visibleSelected = pruneSelection(selected, filtered.map((l) => l.id))
  assert.deepEqual([...visibleSelected].sort(), [1, 3])
})
