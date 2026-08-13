// NTMOB31 — check-out/check-in d'outillage par scan (logique pure).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { trouverOutil, statutApresScan, normaliserCode } from './scanOutil.js'

const PARC = [
  { id: 3, nom: 'Perceuse', asset_tag: 'OUT-014', numero_serie: 'SN-9', statut: 'disponible' },
  { id: 4, nom: 'Échelle', asset_tag: 'OUT-020', statut: 'en_intervention' },
  { id: 5, nom: 'Multimètre', asset_tag: 'OUT-030', statut: 'en_reparation' },
]

test('NTMOB31: résout l\'étiquette, le n° de série et le préfixe OUTIL:', () => {
  assert.equal(trouverOutil(PARC, 'OUT-014').id, 3)
  assert.equal(trouverOutil(PARC, 'out-014').id, 3)
  assert.equal(trouverOutil(PARC, 'OUTIL:OUT-020').id, 4)
  assert.equal(trouverOutil(PARC, 'SN-9').id, 3)
  assert.equal(normaliserCode(' OUTIL:Abc '), 'abc')
})

test('NTMOB31: un code inconnu ne devine JAMAIS un outil approchant', () => {
  assert.equal(trouverOutil(PARC, 'OUT-999'), null)
  assert.equal(trouverOutil(PARC, ''), null)
})

test('NTMOB31: le scan bascule disponible ↔ en intervention', () => {
  assert.equal(statutApresScan(PARC[0]), 'en_intervention')
  assert.equal(statutApresScan(PARC[1]), 'disponible')
})

test('NTMOB31: un outil en réparation ou perdu n\'est jamais basculé par un scan', () => {
  assert.equal(statutApresScan(PARC[2]), null)
  assert.equal(statutApresScan({ statut: 'perdu' }), null)
  assert.equal(statutApresScan(null), null)
})
