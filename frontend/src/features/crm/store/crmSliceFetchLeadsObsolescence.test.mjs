// LB7 — garde d'obsolescence sur fetchLeads (bug recon2-03 #10) : un
// `fulfilled` dont le requestId ne correspond plus au DERNIER fetchLeads
// dispatché est ignoré, même motif que `leadUpdateSeq`/`isStaleResourceUpdate`
// déjà en place pour `updateLead`. Verified against SOURCE — `@reduxjs/toolkit`
// n'est pas installé dans ce worktree/lane (pas de node_modules), donc la
// slice ne peut pas être importée/exécutée directement ici ; la logique
// PARTAGÉE (isStaleResourceUpdate) est déjà exercée en pratique par
// `leadUpdateSeq`/`clientUpdateSeq` (même fonction, réutilisée telle quelle).
//   node --test src/features/crm/store/crmSliceFetchLeadsObsolescence.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'crmSlice.js'), 'utf8')

test('LB7 : fetchLeadsRequestId initialisé dans le state (miroir clientUpdateSeq/leadUpdateSeq)', () => {
  assert.match(SRC, /fetchLeadsRequestId: null,/)
})

test('LB7 : fetchLeads.pending trace le requestId de la dernière requête dispatchée', () => {
  const start = SRC.indexOf(".addCase(fetchLeads.pending,")
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 200)
  assert.match(block, /state\.fetchLeadsRequestId = action\.meta\.requestId/)
})

test('LB7 : fetchLeads.fulfilled ignore un payload OBSOLÈTE (requestId périmé)', () => {
  const start = SRC.indexOf('.addCase(fetchLeads.fulfilled,')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 500)
  assert.match(block, /if \(action\.meta\.requestId !== state\.fetchLeadsRequestId\) return/)
  // La garde précède TOUJOURS l'écriture — sinon elle ne protège rien.
  const guardIdx = block.indexOf('if (action.meta.requestId !== state.fetchLeadsRequestId) return')
  const writeIdx = block.indexOf('state.leads = action.payload.results ?? action.payload')
  assert.ok(guardIdx > 0 && writeIdx > guardIdx, 'la garde doit précéder l\'écriture de state.leads')
})

test('LB7 : même motif que isStaleResourceUpdate (leadUpdateSeq) — cohérence du style de garde', () => {
  assert.match(SRC, /function isStaleResourceUpdate\(seqMap, id, requestId\)/)
  assert.match(SRC, /if \(isStaleResourceUpdate\(state\.leadUpdateSeq, action\.payload\.id, action\.meta\.requestId\)\) return/)
})
