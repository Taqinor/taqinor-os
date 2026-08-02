// LB4 — le select d'étape de la liste (InlineEdit) doit traiter un recul
// EXACTEMENT comme le drag kanban — bug recon2-03 #8 : le chemin
// clavier/select n'avait aucun garde de sens.
// ORDRE FONDATEUR 2026-08-01 — la réponse commune a changé de forme : d'un
// « impossible » silencieux (option grisée) à une CONFIRMATION qui nomme le
// lead et les deux étapes, puis un enregistrement portant le marqueur. Ce qui
// n'a PAS changé : les trois surfaces composent les mêmes prédicats de
// stages.js, aucune ne redérive un rang de funnel localement.
// Verified against SOURCE (no node_modules in this worktree/lane) — la logique
// pure (funnelRank/isStageMoveAllowed/isStageMoveBackward) est couverte
// exhaustivement par features/crm/stages.test.mjs.
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

test('LB4 : ListView importe son prédicat de sens de stages.js (jamais un second garde recodé)', () => {
  const start = SRC.indexOf("from '../../../../features/crm/stages'")
  assert.ok(start > 0, 'import stages.js introuvable')
  const importBlock = SRC.slice(Math.max(0, start - 300), start)
  assert.match(importBlock, /isStageMoveBackward/)
  // L'invariant du bug #8 : le SENS d'un mouvement ne se redérive jamais ici.
  // (`PIPELINE_STAGES.indexOf` reste légitime dans le comparateur de TRI de la
  // colonne Stade — c'est un ordre d'affichage, pas un rang de funnel.)
  const decision = SRC.slice(SRC.indexOf('const stageOptionsFor = '))
  assert.doesNotMatch(
    decision.slice(0, decision.indexOf('const PRIORITE_OPTIONS')),
    /funnelRank|PIPELINE_STAGES\.indexOf|stageRank/,
  )
})

test("ordre fondateur 2026-08-01 : stageOptionsFor ne grise plus que l'étape COURANTE", () => {
  // Reculer est devenu légitime (sous confirmation) : griser les options
  // arrière disait « impossible » là où la bonne réponse est une question.
  // Seule reste grisée l'option qui ne veut rien dire — l'étape courante.
  const start = SRC.indexOf('const stageOptionsFor = ')
  assert.ok(start > 0, 'stageOptionsFor introuvable')
  const body = SRC.slice(start, start + 400)
  assert.match(body, /disabled: s === currentStage/)
  assert.doesNotMatch(body, /isStageMoveAllowed/)
})

test('ordre fondateur 2026-08-01 : la cellule Stade CONFIRME un recul, puis enregistre avec le marqueur', () => {
  const start = SRC.indexOf('data-label="Stade"')
  assert.ok(start > 0)
  const block = SRC.slice(start, SRC.indexOf('data-label="Score"', start))
  // La question vient de la source PARTAGÉE (une seule formulation pour le
  // board et la liste), jamais d'un window.confirm ni d'un texte local.
  assert.match(SRC, /import \{ useConfirmerRecul \} from '\.\.\/\.\.\/\.\.\/\.\.\/features\/crm\/confirmRecul'/)
  assert.doesNotMatch(block, /window\.confirm/)
  assert.match(block, /const enArriere = isStageMoveBackward\(lead\.stage, v\)/)
  assert.match(block, /if \(enArriere && !\(await confirmerRecul\(lead, v\)\)\) return/)
  // Confirmé → MÊME chemin d'enregistrement, avec le marqueur que le serveur
  // exige (sans lui, apps/crm/serializers.py refuse toujours le recul).
  assert.match(block, /onInlineSave\(lead, 'stage', v, \{ confirmeRecul: enArriere \}\)/)
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
