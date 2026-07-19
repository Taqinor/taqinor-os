// LB9-wire — KanbanView (lane LB1, board) gagne 4 props OPTIONNELLES pour ses
// empty states à deux paliers (totalLeads, onClearFilters, onNewLead,
// onImportLeads — dégrade proprement quand absentes). LeadsPage.jsx (LB4)
// câble le call-site exactement comme ChartsView. Verified against SOURCE
// (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageKanbanEmptyStateWire.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB9-wire : KanbanView reçoit totalLeads/onClearFilters/onNewLead/onImportLeads', () => {
  const idx = PAGE_SRC.indexOf("{view === 'kanban' && (")
  assert.ok(idx > 0)
  const block = PAGE_SRC.slice(idx, idx + 400)
  assert.match(block, /<KanbanView/)
  assert.match(block, /\{\.\.\.viewProps\}/)
  assert.match(block, /totalLeads=\{leads\.length\}/)
  assert.match(block, /onClearFilters=\{\(\) => setFilters\(EMPTY_FILTERS\)\}/)
  assert.match(block, /onNewLead=\{openNew\}/)
  assert.match(block, /onImportLeads=\{\(\) => setShowImport\(true\)\}/)
})

test('LB9-wire : même trio totalLeads/onClearFilters que ChartsView (cohérence des empty states)', () => {
  const chartsIdx = PAGE_SRC.indexOf('<ChartsView')
  assert.ok(chartsIdx > 0)
  const chartsBlock = PAGE_SRC.slice(chartsIdx, chartsIdx + 200)
  assert.match(chartsBlock, /totalLeads=\{leads\.length\}/)
  assert.match(chartsBlock, /onClearFilters=\{\(\) => setFilters\(EMPTY_FILTERS\)\}/)
})
