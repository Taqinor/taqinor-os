// ERR-QAH-DIFF-POMPAGE-TENSION-NOM-2200W — `tensionOf` lit la tension d'un nom
// avec la MÊME règle stricte que `calepinage.services.pompage.tension_produit`
// (nombre isolé 220/380 suivi de « V »). Run :
//   node --test src/features/ventes/solar.tensionNom.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { tensionOf } from './solar.js'

test('une puissance en watts ou un nombre collé ne sont pas une tension', () => {
  assert.equal(tensionOf({ nom: 'Variateur VEICHI SVF3 2.2kW 2200W', tension_v: null }), null)
  assert.equal(tensionOf({ nom: 'Pompe 1220V' }), null)
  assert.equal(tensionOf({ nom: 'Pompe 3800W' }), null)
})

test('tension explicite lue, champ tension_v prioritaire', () => {
  for (const [nom, attendu] of [['VARIATEUR VEICHI SI22 2.2KW 220V', 220],
    ['Pompe 380 V', 380], ['Pompe 220Vac', 220], ['Moteur 380 volts', 380],
    ['Pompe 220V/380V', 220]]) {
    assert.equal(tensionOf({ nom }), attendu, nom)
  }
  assert.equal(tensionOf({ nom: 'X 220V', tension_v: 380 }), 380)
})
