// QJR86 — tests de la primitive de la valeur signée. `node --test` uniquement
// (aucun node_modules requis : le module sous test n'importe rien).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  moteur, saisie, apercu, absent, estFait, unwrap, PUCE_APERCU,
} from './valeur.js'

test('les trois constructeurs signent la valeur avec leur source', () => {
  assert.deepEqual({ ...moteur(12) }, { valeur: 12, source: 'moteur' })
  assert.deepEqual({ ...saisie('14') }, { valeur: '14', source: 'saisie' })
  assert.deepEqual({ ...apercu(8.5) }, { valeur: 8.5, source: 'apercu' })
})

test('absent porte le motif FR et une valeur nulle', () => {
  const v = absent('Ville manquante : le moteur ne peut pas chiffrer.')
  assert.equal(v.valeur, null)
  assert.equal(v.source, null)
  assert.equal(v.motif, 'Ville manquante : le moteur ne peut pas chiffrer.')
})

test('absent REFUSE un motif vide (un vide sans explication est interdit)', () => {
  assert.throws(() => absent(''), TypeError)
  assert.throws(() => absent('   '), TypeError)
  assert.throws(() => absent(null), TypeError)
  assert.throws(() => absent(), TypeError)
})

test('une valeur signée est gelée (personne ne change sa source après coup)', () => {
  const v = moteur(12)
  assert.equal(Object.isFrozen(v), true)
  assert.throws(() => { 'use strict'; v.source = 'saisie' }, TypeError)
})

test('re-signer une valeur déjà signée est refusé', () => {
  assert.throws(() => moteur(saisie(12)), TypeError)
  assert.throws(() => apercu(absent('rien')), TypeError)
})

test('estFait distingue un chiffre exploitable d’un trou', () => {
  assert.equal(estFait(moteur(12)), true)
  assert.equal(estFait(saisie(0)), true)          // 0 EST un chiffre
  assert.equal(estFait(apercu('')), true)         // chaîne vide = valeur posée
  assert.equal(estFait(absent('motif')), false)
  assert.equal(estFait(moteur(null)), false)
  assert.equal(estFait(moteur(undefined)), false)
  assert.equal(estFait(moteur(NaN)), false)
  assert.equal(estFait(12), false)                // nombre nu : jamais « fait »
  assert.equal(estFait(null), false)
})

test('unwrap est le SEUL déballeur : il refuse un nombre NU', () => {
  assert.throws(() => unwrap(12), TypeError)
  assert.throws(() => unwrap('12'), TypeError)
  assert.throws(() => unwrap(null), TypeError)
  assert.throws(() => unwrap({ valeur: 12 }), TypeError)          // pas de source
  assert.throws(() => unwrap({ valeur: 12, source: 'pdf' }), TypeError) // source inconnue
})

test('unwrap : moteur et saisie sortent NUS, sans puce ni motif', () => {
  assert.deepEqual({ ...unwrap(moteur(12)) },
    { valeur: 12, source: 'moteur', puce: null, motif: null })
  assert.deepEqual({ ...unwrap(saisie('14')) },
    { valeur: '14', source: 'saisie', puce: null, motif: null })
})

test('unwrap : un aperçu sort TOUJOURS avec la puce « estimation d’exemple »', () => {
  const r = unwrap(apercu(8.5))
  assert.equal(r.valeur, 8.5)
  assert.equal(r.source, 'apercu')
  assert.equal(r.puce, PUCE_APERCU)
  assert.equal(PUCE_APERCU, "estimation d'exemple")
})

test('unwrap : un absent rend le motif FR VERBATIM du serveur, jamais un chiffre', () => {
  const motif = 'Catalogue incomplet : aucun onduleur hybride en stock pour ce kWc.'
  const r = unwrap(absent(motif))
  assert.equal(r.valeur, null)
  assert.equal(r.source, null)
  assert.equal(r.motif, motif)   // VERBATIM — jamais reformulé
  assert.equal(r.puce, null)
})
