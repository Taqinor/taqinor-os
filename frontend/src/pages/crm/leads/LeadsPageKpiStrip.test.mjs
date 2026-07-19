// LB24 — LeadsPage monte LeadsKpiStrip entre l'en-tête et FilterBar, câblé
// sur le MÊME état `filters`/`setFilters` que le reste de la page (invariant
// D6-I7 : un seul état de filtres). Verified against SOURCE (no node_modules
// in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageKpiStrip.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB24 : LeadsPage importe LeadsKpiStrip', () => {
  assert.match(PAGE_SRC, /import LeadsKpiStrip from '\.\/LeadsKpiStrip'/)
})

test('LB24 : LeadsKpiStrip est monté AVANT FilterBar, câblé sur filters/setFilters/leads', () => {
  const kpiIdx = PAGE_SRC.indexOf('<LeadsKpiStrip')
  const filterBarIdx = PAGE_SRC.indexOf('<FilterBar filters={filters} setFilters={setFilters} leads={leads} />')
  assert.ok(kpiIdx > 0 && filterBarIdx > 0)
  assert.ok(kpiIdx < filterBarIdx, 'LeadsKpiStrip doit précéder FilterBar (rangée cockpit)')
  const block = PAGE_SRC.slice(kpiIdx, filterBarIdx)
  assert.match(block, /leads=\{leads\}/)
  assert.match(block, /filters=\{filters\}/)
  assert.match(block, /setFilters=\{setFilters\}/)
  assert.match(block, /myUsername=\{currentUser\?\.username\}/)
})
