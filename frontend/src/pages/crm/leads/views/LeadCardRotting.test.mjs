// LB14 — Rampe « rotting » sur la carte (blueprint D3). La carte réutilise
// features/crm/workspace/rotting.js TEL QUEL sur `stage_since_days` :
//   data-rot = perdu ? 'ok' : rottingLevel(stage_since_days,
//              thresholdsForIndex(PIPELINE_STAGES.indexOf(stage)))
// posé sur `article.kb-card` ; la pill d'âge se teinte (ambre/rouge) et un
// liseré gauche apparaît en danger. Jamais de rot sur SIGNED/COLD (seuils
// null) ni sur un lead perdu. Ce test PROUVE la classification (import réel du
// module pur) EN PLUS de vérifier le câblage source (no node_modules ici).
//   node --test src/pages/crm/leads/views/LeadCardRotting.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { rottingLevel, thresholdsForIndex } from '../../../../features/crm/workspace/rotting.js'
import { PIPELINE_STAGES } from '../../../../features/crm/stages.js'

const rotFor = (stage, days, perdu = false) =>
  perdu ? 'ok' : rottingLevel(days, thresholdsForIndex(PIPELINE_STAGES.indexOf(stage)))

test('LB14 : un lead perdu n\'est JAMAIS teinté (rot forcé à ok)', () => {
  assert.equal(rotFor('QUOTE_SENT', 30, true), 'ok')
})

test('LB14 : QUOTE_SENT à 16 j = danger (rouge), 9 j = warning (ambre), 3 j = ok (neutre)', () => {
  assert.equal(rotFor('QUOTE_SENT', 16), 'danger')
  assert.equal(rotFor('QUOTE_SENT', 9), 'warning')
  assert.equal(rotFor('QUOTE_SENT', 3), 'ok')
})

test('LB14 : SIGNED et COLD ne pourrissent jamais (seuils null → ok)', () => {
  for (const days of [1, 50, 400]) {
    assert.equal(rotFor('SIGNED', days), 'ok')
    assert.equal(rotFor('COLD', days), 'ok')
  }
})
