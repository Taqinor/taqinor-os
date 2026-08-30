// NTMOB2 — logique pure de l'arbitrage de conflit de synchronisation.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CLES_CHOIX, choixValide, peutEnvoyer, lirePayload, versions, resumer,
} from './conflitsSynchro.js'

test('NTMOB2: exactement trois arbitrages, aucun autre', () => {
  assert.deepEqual(CLES_CHOIX, ['mienne', 'serveur', 'fusion'])
  assert.equal(choixValide('mienne'), true)
  assert.equal(choixValide('ecraser-tout'), false)
  assert.equal(choixValide(''), false)
})

test('NTMOB2: une fusion sans corps recomposé n’est pas envoyable', () => {
  assert.equal(peutEnvoyer('fusion', null), false)
  assert.equal(peutEnvoyer('fusion', {}), false)
  assert.equal(peutEnvoyer('fusion', { tag: 'chaud' }), true)
  // Les deux autres arbitrages n'ont jamais besoin d'un corps.
  assert.equal(peutEnvoyer('mienne', null), true)
  assert.equal(peutEnvoyer('serveur', null), true)
  assert.equal(peutEnvoyer('inconnu', { a: 1 }), false)
})

test('NTMOB2: un corps illisible ne devine RIEN', () => {
  assert.equal(lirePayload('{pas du json'), null)
  assert.equal(lirePayload('[1,2]'), null)
  assert.equal(lirePayload('"texte"'), null)
  assert.deepEqual(lirePayload('{"tag":"chaud"}'), { tag: 'chaud' })
})

test('NTMOB2: les deux versions viennent du serveur, jamais d’un défaut', () => {
  const vide = versions({ conflit: {} })
  assert.equal(vide.champ, null)
  assert.equal(vide.mienne, null)
  assert.equal(vide.serveur, null)

  const plein = versions({
    conflit: {
      champ: 'date_modification',
      base: '2026-08-31T10:00:00+00:00',
      serveur: '2026-08-31T11:30:00+00:00',
    },
  })
  assert.equal(plein.champ, 'date_modification')
  assert.equal(plein.mienne, '2026-08-31T10:00:00+00:00')
  assert.equal(plein.serveur, '2026-08-31T11:30:00+00:00')
})

test('NTMOB2: le résumé reprend le message du serveur tel quel', () => {
  const ligne = resumer({
    id: 12,
    op_type: 'crm.lead.tag',
    module: 'crm',
    module_libelle: 'CRM',
    client_op_id: 'abcdef',
    erreur: 'Conflit de synchronisation : …',
    conflit: { champ: 'date_modification', base: 'A', serveur: 'B' },
  })
  assert.equal(ligne.id, 12)
  assert.equal(ligne.module, 'CRM')
  assert.equal(ligne.opType, 'crm.lead.tag')
  assert.equal(ligne.mienne, 'A')
  assert.equal(ligne.serveur, 'B')
  assert.equal(ligne.message, 'Conflit de synchronisation : …')
  assert.equal(resumer(null), null)
})
