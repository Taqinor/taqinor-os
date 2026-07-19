// LB7 — plus de refetch intégral après un PATCH mono-lead + fin des catch
// muets (bugs recon2-03 #5/#11, blueprint I1/I8). `updateLead.fulfilled`
// (crmSlice.js) remplace déjà le lead au COMPLET dans le store — un refetch
// après onInlineSave/reassign/archive/restore d'UN SEUL lead était une perte
// réseau pure. Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageNoOverfetch.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const LIST_SRC = readFileSync(join(HERE, 'views/ListView.jsx'), 'utf8')

test('LB7 : onInlineSave ne refetch plus après un PATCH mono-lead', () => {
  const start = PAGE_SRC.indexOf('const onInlineSave = useCallback(')
  assert.ok(start > 0)
  const end = PAGE_SRC.indexOf('}, [dispatch])', start)
  const body = PAGE_SRC.slice(start, end)
  assert.doesNotMatch(body, /refetch\(\)/)
  assert.match(body, /dispatch\(updateLead\(\{ id: lead\.id, data: \{ \[field\]: value \} \}\)\)\.unwrap\(\)/)
})

test('LB7 : reassign ne refetch plus et toaste en échec (bugs #5/#11)', () => {
  const start = PAGE_SRC.indexOf('const reassign = useCallback(')
  assert.ok(start > 0)
  const end = PAGE_SRC.indexOf('}, [dispatch])', start)
  const body = PAGE_SRC.slice(start, end)
  assert.doesNotMatch(body, /refetch\(\)/)
  assert.match(body, /toastError\('La réassignation a échoué/)
})

test('LB7 : exportFiltered/exportSelection toastent en échec (bug #11, catch silencieux tué)', () => {
  const filteredStart = PAGE_SRC.indexOf('const exportFiltered = async () => {')
  const filteredBody = PAGE_SRC.slice(filteredStart, filteredStart + 400)
  assert.doesNotMatch(filteredBody, /\/\* ignore \*\//)
  assert.match(filteredBody, /toastError\('Export indisponible/)

  const selectionStart = PAGE_SRC.indexOf('const exportSelection = async () => {')
  const selectionBody = PAGE_SRC.slice(selectionStart, selectionStart + 400)
  assert.match(selectionBody, /toastError\('Export indisponible/)
})

test('LB7 : viewProps embarque toujours onRefetch — reste légitime pour bulk/import/merge/Signé/création', () => {
  const start = PAGE_SRC.indexOf('const viewProps = useMemo(() => ({')
  const block = PAGE_SRC.slice(start, start + 700)
  assert.match(block, /onRefetch: refetch,/)
  // Les cas légitimes restent câblés : runBulk (bulk), onSaved (création),
  // onAnyMerge (merge), ExcelImport onDone (import), SigneDialog (Signé).
  assert.match(PAGE_SRC, /const onSaved = \(\) => refetch\(\)/)
  assert.match(PAGE_SRC, /onAnyMerge=\{\(\) => \{ refetch\(\); refreshDoublonsCount\(\) \}\}/)
  assert.match(PAGE_SRC, /onDone=\{refetch\}/)
})

test('LB7 : ListView onArchive/onRestore ne refetch plus (le store patche déjà is_archived), toastent en échec', () => {
  const archiveStart = LIST_SRC.indexOf('const onArchive = useCallback(')
  const archiveEnd = LIST_SRC.indexOf('}, [dispatch])', archiveStart)
  const archiveBody = LIST_SRC.slice(archiveStart, archiveEnd)
  assert.doesNotMatch(archiveBody, /onRefetch\?\.\(\)/)
  assert.match(archiveBody, /toastError\("L'archivage a échoué/)

  const restoreStart = LIST_SRC.indexOf('const onRestore = useCallback(')
  const restoreEnd = LIST_SRC.indexOf('}, [dispatch])', restoreStart)
  const restoreBody = LIST_SRC.slice(restoreStart, restoreEnd)
  assert.doesNotMatch(restoreBody, /onRefetch\?\.\(\)/)
  assert.match(restoreBody, /toastError\('La restauration a échoué/)
})

test('LB7 : ListView onDelete GARDE son onRefetch (corbeille → restaurerCorbeille n\'a pas de reducer de ré-insertion)', () => {
  const start = LIST_SRC.indexOf('const onDelete = useCallback(')
  assert.ok(start > 0)
  const block = LIST_SRC.slice(start, start + 900)
  assert.match(block, /onRefetch\?\.\(\)/)
})
