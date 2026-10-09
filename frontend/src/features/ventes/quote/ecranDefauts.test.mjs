// SPL43 — les défauts d'écran du générateur, EXÉCUTÉS : part diurne par
// marché, ville de calcul servie, dernière TVA, format des nombres.
//
// Run : node --test src/features/ventes/quote/ecranDefauts.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  SAISON_LABELS, villeEffectiveLead, partDiurneParDefaut, lireLastTva, ecrireLastTva,
  FENETRE_REFERENCE_MS, fmtNum,
} from './ecranDefauts.js'
import { DAY_USAGE_DEFAULTS, TVA_STANDARD_DEFAUT } from '../solar.js'

test('part diurne : le défaut du marché (simulateur), résidentiel en repli', () => {
  assert.equal(partDiurneParDefaut('residentiel'), DAY_USAGE_DEFAULTS['Résidentielle'])
  assert.equal(partDiurneParDefaut('agricole'), DAY_USAGE_DEFAULTS.Agricole)
  assert.equal(partDiurneParDefaut('industriel'), DAY_USAGE_DEFAULTS['Résidentielle'])
})

test('ville de calcul : ville_effective servie d’abord, jamais null', () => {
  assert.equal(villeEffectiveLead({ ville: 'Rabat', ville_effective: 'Salé' }), 'Salé')
  assert.equal(villeEffectiveLead({ ville: 'Rabat' }), 'Rabat')
  assert.equal(villeEffectiveLead(null), '')
})

test('dernière TVA : sans stockage, le taux standard ; l’écriture ne lève jamais', () => {
  assert.equal(lireLastTva(), String(TVA_STANDARD_DEFAUT))
  assert.doesNotThrow(() => ecrireLastTva('10'))
})

test('constantes et format', () => {
  assert.deepEqual(SAISON_LABELS, { hiver: 'Hiver', mi_saison: 'Mi-saison', ete: 'Été' })
  assert.equal(FENETRE_REFERENCE_MS, 1500)
  assert.equal(fmtNum(null), 'N/A')
  assert.equal(fmtNum(undefined), 'N/A')
  assert.notEqual(fmtNum(1234), 'N/A')
})
