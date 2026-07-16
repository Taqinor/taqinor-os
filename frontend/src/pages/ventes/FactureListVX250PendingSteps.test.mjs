// VX250 — La fiche annonce son état : « en attente de… ». Verified against
// SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/FactureListVX250PendingSteps.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'FactureList.jsx'), 'utf8')

test('PendingStepsIndicator : une facture à acompte PARTIEL affiche « Solde restant », lecture PURE (isPartiallyPaid déjà défini)', () => {
  assert.match(SRC, /const isPartiallyPaid = f =>/)
  assert.match(SRC, /\{isPartiallyPaid\(f\) && \(/)
  assert.match(SRC, /Solde restant : \{formatMAD\(f\.montant_du\)\}/)
})

test('le bandeau reste une lecture PURE — jamais un dispatch/mutation', () => {
  const start = SRC.indexOf('{isPartiallyPaid(f) && (')
  const end = SRC.indexOf(')}', start)
  const block = SRC.slice(start, end)
  assert.doesNotMatch(block, /dispatch\(/)
})

test('?q= est désormais lu au montage (le lien pré-filtré de RelationCounters/LIST_ROUTE.facture fonctionne réellement)', () => {
  assert.match(SRC, /const \[search, setSearch\]\s*= useState\(\(\) => searchParams\.get\('q'\) \?\? ''\)/)
})
