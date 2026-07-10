// QX12 — Notification/Dashboard deep-links that actually land: DevisList must
// read ?devis=<pk> (highlight/scroll to that quote) AND ?statut=<key>
// (pre-set the filter) on mount. Verified against the SOURCE (no node_modules
// installed in this worktree/lane — same convention as MesActivitesPage.test.mjs
// / SigneDialog.test.mjs).
//   node --test src/pages/ventes/DevisListDeepLinks.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

test('QX12 : statutFilter se pré-règle depuis ?statut= au montage', () => {
  const block = SRC.slice(
    SRC.indexOf('const [statutFilter, setStatutFilter] = useState('),
    SRC.indexOf('const [query, setQuery]'))
  assert.match(block, /searchParams\.get\('statut'\)/)
  // Une valeur inconnue retombe sur 'tous' (jamais un filtre cassé/vide).
  assert.match(block, /return s && \(s === 'tous' \|\| STATUT_DISPLAY\[s\]\) \? s : 'tous'/)
})

test('QX12 : highlightId se lit depuis ?devis= au montage', () => {
  const block = SRC.slice(
    SRC.indexOf('const [highlightId] = useState('),
    SRC.indexOf('const [highlightId] = useState(') + 400)
  assert.match(block, /searchParams\.get\('devis'\)/)
  assert.match(block, /Number\(v\)/)
})

test('QX12 : un effet fait défiler jusqu\'à la ligne ciblée une fois les devis chargés', () => {
  assert.match(SRC, /useEffect\(\(\) => \{\s*if \(!highlightId \|\| loading\) return/)
  assert.match(SRC, /getElementById\(`devis-row-\$\{highlightId\}`\)/)
  assert.match(SRC, /scrollIntoView/)
})

test('QX12 : chaque ligne du tableau porte un id DOM stable devis-row-<id>', () => {
  assert.match(SRC, /<tr id=\{`devis-row-\$\{d\.id\}`\}/)
})

test('QX12 : la ligne ciblée est visuellement distinguée (surbrillance)', () => {
  const trBlock = SRC.slice(
    SRC.indexOf('<tr id={`devis-row-${d.id}`}'),
    SRC.indexOf('<tr id={`devis-row-${d.id}`}') + 300)
  assert.match(trBlock, /highlightId === d\.id/)
})
