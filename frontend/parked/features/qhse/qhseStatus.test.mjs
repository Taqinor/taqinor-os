// UX29–UX33 — Tests PURS de la logique QHSE. node --test, sans rendu DOM.
//   Exécuté en CI : node --test src/features/qhse/qhseStatus.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  computeTfTg, peutCloturerNotation, isoNiveauLabel, num,
} from './qhseStatus.js'

test('computeTfTg — formules TF/TG standard', () => {
  // 3 accidents, 12 jours perdus, 500 000 heures travaillées.
  const { tf, tg } = computeTfTg({ accidents: 3, joursPerdus: 12, heures: 500000 })
  assert.equal(tf, 6) // 3 × 1 000 000 / 500 000
  assert.equal(tg, 0.02) // 12 × 1 000 / 500 000 = 0,024 → 0,02
})

test('computeTfTg — null (jamais NaN) si heures ≤ 0 ou absentes', () => {
  assert.deepEqual(computeTfTg({ accidents: 5, heures: 0 }), { tf: null, tg: null })
  assert.deepEqual(computeTfTg({}), { tf: null, tg: null })
})

test('computeTfTg — accepte des chaînes numériques (Decimal API)', () => {
  const { tf } = computeTfTg({ accidents: '2', joursPerdus: '0', heures: '1000000' })
  assert.equal(tf, 2)
})

test('peutCloturerNotation — respecte le flag serveur', () => {
  assert.equal(peutCloturerNotation({ peut_cloturer: true }), true)
  assert.equal(peutCloturerNotation({ peut_cloturer: false }), false)
})

test('peutCloturerNotation — déduit du verdict + seuil sans flag', () => {
  assert.equal(peutCloturerNotation({ verdict: 'passe', score: 80, seuil_passage: 70 }), true)
  assert.equal(peutCloturerNotation({ verdict: 'echec', score: 60, seuil_passage: 70 }), false)
  assert.equal(peutCloturerNotation({ verdict: 'passe', score: 50, seuil_passage: 70 }), false)
})

test('peutCloturerNotation — false pour une notation vide/incomplète', () => {
  assert.equal(peutCloturerNotation(null), false)
  assert.equal(peutCloturerNotation({}), false)
})

test('isoNiveauLabel — traduit les niveaux ISO', () => {
  assert.equal(isoNiveauLabel('avance'), 'Avancé')
  assert.equal(isoNiveauLabel('intermediaire'), 'Intermédiaire')
  assert.equal(isoNiveauLabel('initial'), 'Initial')
})

test('num — coercition propre', () => {
  assert.equal(num('12.5'), 12.5)
  assert.equal(num(''), null)
  assert.equal(num('abc'), null)
  assert.equal(num(0), 0)
})
