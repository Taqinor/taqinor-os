// LB23 — recherche débouncée (blueprint D5/I7) : l'input de recherche garde
// un état local et pousse `setFilters` seulement après 250ms de pause,
// annulé au démontage/à la frappe suivante ; se resynchronise IMMÉDIATEMENT
// quand `filters.q` change depuis l'extérieur (Effacer les filtres, vue
// enregistrée, URL collée). Verified against SOURCE (no node_modules in
// this worktree/lane).
//   node --test src/pages/crm/leads/FilterBar.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'FilterBar.jsx'), 'utf8')

test('LB23 : état local searchLocal initialisé depuis filters.q', () => {
  assert.match(SRC, /const \[searchLocal, setSearchLocal\] = useState\(filters\.q\)/)
})

test('LB23 : resynchronisation immédiate quand filters.q change depuis l’extérieur', () => {
  const idx = SRC.indexOf('setSearchLocal(filters.q)')
  assert.ok(idx > 0, 'effet de resynchronisation introuvable')
  const block = SRC.slice(Math.max(0, idx - 60), idx + 80)
  assert.match(block, /useEffect\(\(\) => \{/)
  assert.match(block, /\}, \[filters\.q\]\)/)
})

test('LB23 : le push vers setFilters est débouncé 250ms et annulé au démontage/frappe suivante', () => {
  const start = SRC.indexOf('if (searchLocal === filters.q) return undefined')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 350)
  assert.match(block, /setTimeout\(\(\) => setFilters\(\(f\) => \(\{ \.\.\.f, q: searchLocal \}\)\), 250\)/)
  assert.match(block, /return \(\) => clearTimeout\(t\)/)
  assert.match(block, /\}, \[searchLocal\]\)/)
})

test('LB23 : le champ de recherche est contrôlé par searchLocal (jamais filters.q directement)', () => {
  const start = SRC.indexOf('placeholder="Rechercher nom, téléphone, email…"')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 200)
  assert.match(block, /value=\{searchLocal\}/)
  assert.match(block, /onChange=\{\(e\) => setSearchLocal\(e\.target\.value\)\}/)
  assert.doesNotMatch(block, /value=\{filters\.q\}/)
})
