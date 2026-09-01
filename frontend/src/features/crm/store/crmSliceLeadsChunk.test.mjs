// PERF-CRM (2026-09-01, mesuré à 930 leads en prod) — flux PROGRESSIF de
// fetchLeads : la 1re page s'affiche dès son arrivée (leadsChunkReceived),
// page_size=200 (plafond StandardPagination) et concurrency 3 (2 vCPU prod).
// Verified against SOURCE — `@reduxjs/toolkit` n'est pas installé dans ce
// worktree/lane (pas de node_modules), même motif que
// crmSliceFetchLeadsObsolescence.test.mjs.
//   node --test src/features/crm/store/crmSliceLeadsChunk.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'crmSlice.js'), 'utf8')

test('PERF-CRM : fetchLeads demande page_size=200 avec concurrency 3 (plus jamais 19×50 en rafale de 20)', () => {
  const start = SRC.indexOf("createCancellableThunk('crm/fetchLeads'")
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 900)
  assert.match(block, /page_size: 200/)
  assert.match(block, /concurrency: 3/)
})

test('PERF-CRM : chaque page dispatche leadsChunkReceived avec le requestId (flux progressif)', () => {
  const start = SRC.indexOf("createCancellableThunk('crm/fetchLeads'")
  const block = SRC.slice(start, start + 900)
  assert.match(block, /onPage:/)
  assert.match(block, /leadsChunkReceived\(\{/)
  assert.match(block, /requestId: thunkAPI\.requestId/)
})

test('PERF-CRM : le réducteur de page garde la MÊME garde anti-obsolescence LB7 que fulfilled', () => {
  const start = SRC.indexOf('.addCase(leadsChunkReceived,')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 700)
  const guardIdx = block.indexOf('if (requestId !== state.fetchLeadsRequestId) return')
  assert.ok(guardIdx > 0, 'garde requestId absente du réducteur de page')
  // La garde précède la première écriture d'état.
  const writeIdx = block.indexOf('state.leads = results')
  assert.ok(writeIdx > guardIdx, 'la garde doit précéder l’écriture de state.leads')
})

test('PERF-CRM : 1re page = remplace et lève le squelette ; suivantes = ajout DÉDUPLIQUÉ par id', () => {
  const start = SRC.indexOf('.addCase(leadsChunkReceived,')
  const block = SRC.slice(start, start + 700)
  assert.match(block, /if \(first\) \{/)
  assert.match(block, /state\.leadsLoading = false/)
  assert.match(block, /new Set\(state\.leads\.map\(\(l\) => l\.id\)\)/)
})
