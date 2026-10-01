// QJR576 — UNE conversion panneaux ↔ kWc (kwcPourPanneaux, inverse exact de
// panneauxPourKwc) et UN wattage par défaut (PANEL_W_DEFAUT) ; plus de « 710 »
// recopié dans autoQuote.js ni de mapping lead → scénario retapé.
// Run : node --test src/features/ventes/solar.kwcPanneaux.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { kwcPourPanneaux, panneauxPourKwc, PANEL_W_DEFAUT } from './solar.js'
import {
  BATTERIE_LEAD_VERS_SCENARIO, SCENARIO_SANS, SCENARIO_AVEC, SCENARIO_LES_DEUX,
} from './quote/sizingReducer.js'


test('aller-retour exact : panneauxPourKwc(kwcPourPanneaux(n, W), W) === n', () => {
  for (const W of [500, 550, 710]) {
    for (let n = 1; n <= 200; n++) {
      assert.equal(panneauxPourKwc(kwcPourPanneaux(n, W), W), n, `n=${n} W=${W}`)
    }
  }
})

test('kwcPourPanneaux = n × W / 1000, 0 sans compte ni wattage', () => {
  assert.equal(kwcPourPanneaux(10, 550), 5.5)
  assert.equal(kwcPourPanneaux(0, 550), 0)
  assert.equal(kwcPourPanneaux(10, 0), 0)
  assert.equal(PANEL_W_DEFAUT, 710)
  assert.equal(kwcPourPanneaux(10), 7.1)
})

test('mapping lead → scénario : une seule table, vocabulaire du reducer', () => {
  assert.deepEqual(BATTERIE_LEAD_VERS_SCENARIO, {
    sans: SCENARIO_SANS, avec: SCENARIO_AVEC, les_deux: SCENARIO_LES_DEUX,
  })
  assert.equal(BATTERIE_LEAD_VERS_SCENARIO.sans, 'Sans batterie')
  assert.equal(BATTERIE_LEAD_VERS_SCENARIO.avec, 'Avec batterie')
  assert.equal(BATTERIE_LEAD_VERS_SCENARIO.les_deux, 'Les deux (Sans + Avec)')
})
