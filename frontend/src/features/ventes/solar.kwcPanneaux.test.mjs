// QJR576 — UNE conversion panneaux ↔ kWc (kwcPourPanneaux, inverse exact de
// panneauxPourKwc) et UN wattage par défaut (PANEL_W_DEFAUT) ; plus de « 710 »
// recopié dans autoQuote.js ni de mapping lead → scénario retapé.
// Run : node --test src/features/ventes/solar.kwcPanneaux.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { kwcPourPanneaux, panneauxPourKwc, PANEL_W_DEFAUT } from './solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const AQ = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')
const CODE_AQ = AQ.split(/\r?\n/).filter(l => !/^\s*(\/\/|\*)/.test(l)).join('\n')

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

test('autoQuote.js : plus aucun 710 en dur ni ternaire de scénario retapé', () => {
  assert.doesNotMatch(CODE_AQ, /710 \/ 1000/)
  assert.doesNotMatch(CODE_AQ, /\b710\b/)
  assert.doesNotMatch(CODE_AQ, /'Sans batterie'|'Avec batterie'|'Les deux \(Sans \+ Avec\)'/)
  assert.match(AQ, /BATTERIE_LEAD_VERS_SCENARIO/)
})
