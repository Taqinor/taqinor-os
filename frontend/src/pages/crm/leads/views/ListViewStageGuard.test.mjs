// LB4 — le select d'étape de la liste (InlineEdit) doit griser les mêmes
// transitions interdites que le drag kanban (isStageMoveAllowed, miroir
// serveur _bulk_stage_allowed) — bug recon2-03 #8 : le chemin clavier/select
// n'avait aucun garde de recul. Verified against SOURCE (no node_modules in
// this worktree/lane) — la logique pure (funnelRank/isStageMoveAllowed) est
// couverte exhaustivement par features/crm/stages.test.mjs.
//   node --test src/pages/crm/leads/views/ListViewStageGuard.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ListView.jsx'), 'utf8')
const INLINE_EDIT_SRC = readFileSync(
  join(HERE, '..', '..', '..', '..', 'components', 'InlineEdit.jsx'), 'utf8')

test('LB4 : ListView importe isStageMoveAllowed de stages.js (jamais un second garde recodé)', () => {
  const start = SRC.indexOf("from '../../../../features/crm/stages'")
  assert.ok(start > 0, 'import stages.js introuvable')
  const importBlock = SRC.slice(Math.max(0, start - 300), start)
  assert.match(importBlock, /isStageMoveAllowed/)
})

test('LB4 : stageOptionsFor grise chaque option NON courante et NON permise par isStageMoveAllowed', () => {
  const start = SRC.indexOf('const stageOptionsFor = ')
  assert.ok(start > 0, 'stageOptionsFor introuvable')
  const body = SRC.slice(start, start + 400)
  assert.match(body, /disabled: s !== currentStage && !isStageMoveAllowed\(currentStage, s\)/)
})

test('LB4 : la cellule Stade calcule les options PAR LIGNE (lead.stage courant), pas une liste plate partagée', () => {
  const start = SRC.indexOf('data-label="Stade"')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 400)
  assert.match(block, /options=\{stageOptionsFor\(lead\.stage\)\}/)
})

test('LB4 : InlineEdit propage `disabled` par option au <option> natif (rétro-compatible : undefined pour les autres appelants)', () => {
  assert.match(INLINE_EDIT_SRC, /<option key=\{String\(o\.value\)\} value=\{o\.value \?\? ''\} disabled=\{o\.disabled\}>\{o\.label\}<\/option>/)
})
