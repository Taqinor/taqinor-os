// SPL43 — les défauts d'écran du générateur, EXÉCUTÉS : part diurne par
// marché, ville de calcul servie, dernière TVA, format des nombres.
//
// Run : node --test src/features/ventes/quote/ecranDefauts.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  SAISON_LABELS, villeEffectiveLead, partDiurneParDefaut, lireLastTva, ecrireLastTva,
  FENETRE_REFERENCE_MS, fmtNum, dateValiditeParDefaut,
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

// T4-X1-016 — UNE règle de la validité par défaut d'un devis : la base + le réglage société
// (`quote_validity_days`), la même que le serveur dérive quand la date est vide
// (`utils/expiry.date_expiration` : création + jours). Création : la base est aujourd'hui ;
// une révision (V2) ouverte en édition : sa date de création.
test('validité par défaut : base + jours du réglage société, au format du champ date', () => {
  assert.equal(dateValiditeParDefaut(new Date(2026, 10, 25), 30), '2026-12-25')
  assert.equal(dateValiditeParDefaut(new Date(2026, 11, 20), 30), '2027-01-19')
  assert.equal(dateValiditeParDefaut(new Date(2026, 10, 25), 0), '')
  assert.equal(dateValiditeParDefaut(null, 30), '')
  assert.equal(dateValiditeParDefaut('pas une date', 30), '')
})
