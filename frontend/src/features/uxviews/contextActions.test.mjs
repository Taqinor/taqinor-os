import test from 'node:test'
import assert from 'node:assert/strict'

import { contextActionsForRoute, nextStageFor } from './contextActions.js'

function sp(query) {
  return new URLSearchParams(query)
}

test('NTUX9 — route sans correspondance : aucune action', () => {
  const actions = contextActionsForRoute({ pathname: '/', searchParams: sp('') }, {
    downloadDevisProposal: () => {}, changeLeadStage: () => {},
  })
  assert.deepEqual(actions, [])
})

test('NTUX9 — /crm/leads sans id ouvert : aucune action (« Nouveau lead » reste global, pas ici)', () => {
  const actions = contextActionsForRoute(
    { pathname: '/crm/leads', searchParams: sp('') },
    { changeLeadStage: () => {} },
  )
  assert.deepEqual(actions, [])
})

test('NTUX9 — /crm/leads?lead=<id> : « Changer le stage » exécute avec le bon id', () => {
  let called = null
  const actions = contextActionsForRoute(
    { pathname: '/crm/leads', searchParams: sp('lead=42') },
    { changeLeadStage: (id) => { called = id } },
  )
  assert.equal(actions.length, 1)
  const stageAction = actions.find((a) => a.id === 'ctx-lead-stage')
  assert.ok(stageAction, 'action de changement de stage attendue')
  assert.equal(stageAction.label, 'Changer le stage du lead sélectionné')
  stageAction.run()
  assert.equal(called, '42')
})

test('NTUX9 — sans helper `changeLeadStage`, aucune action stage n’apparaît (jamais une action cassée)', () => {
  const actions = contextActionsForRoute(
    { pathname: '/crm/leads', searchParams: sp('lead=42') },
    {},
  )
  assert.ok(!actions.some((a) => a.id === 'ctx-lead-stage'))
})

test('NTUX9 — /ventes/devis sans id ouvert : aucune action (« Créer un devis » reste global, pas ici)', () => {
  const actions = contextActionsForRoute(
    { pathname: '/ventes/devis', searchParams: sp('') },
    { downloadDevisProposal: () => {} },
  )
  assert.deepEqual(actions, [])
})

test('NTUX9 — critère d’acceptation : /ventes/devis?devis=<id> propose « Générer le PDF » et l’exécute SANS navigation', () => {
  let downloadedId = null
  const actions = contextActionsForRoute(
    { pathname: '/ventes/devis', searchParams: sp('devis=7') },
    { downloadDevisProposal: (id) => { downloadedId = id } },
  )
  assert.equal(actions.length, 1)
  const pdfAction = actions[0]
  assert.equal(pdfAction.id, 'ctx-devis-pdf')
  assert.equal(pdfAction.label, 'Générer le PDF du devis ouvert')
  pdfAction.run()
  assert.equal(downloadedId, '7')
})

test('nextStageFor — avance à l’étape suivante, jamais vers/depuis COLD, null en fin de funnel', () => {
  const stages = ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD']
  assert.equal(nextStageFor('NEW', stages), 'CONTACTED')
  assert.equal(nextStageFor('FOLLOW_UP', stages), 'SIGNED')
  assert.equal(nextStageFor('SIGNED', stages), null)
  assert.equal(nextStageFor('COLD', stages), null)
  assert.equal(nextStageFor('INCONNU', stages), null)
})
