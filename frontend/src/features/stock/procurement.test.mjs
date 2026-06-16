// Tests des helpers d'approvisionnement fournisseur (N11-N13).
// Run with: node --test src/features/stock/procurement.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  bcfStatutLabel, totalAchat, quantiteRestante, estEntierementRecu,
  buildReceptionPayload, lignesEnPenurie, nbPenuries,
} from './procurement.js'

test('bcfStatutLabel : libellés FR connus + repli', () => {
  assert.equal(bcfStatutLabel('brouillon'), 'Brouillon')
  assert.equal(bcfStatutLabel('recu'), 'Reçu')
  assert.equal(bcfStatutLabel('inconnu'), 'inconnu')
})

test('totalAchat : somme qté × prix d\'achat (interne)', () => {
  const lignes = [
    { quantite: 2, prix_achat_unitaire: '100' },
    { quantite: 3, prix_achat_unitaire: '50.5' },
  ]
  assert.equal(totalAchat(lignes), 2 * 100 + 3 * 50.5)
  assert.equal(totalAchat([]), 0)
})

test('quantiteRestante : jamais négative', () => {
  assert.equal(quantiteRestante({ quantite: 10, quantite_recue: 4 }), 6)
  assert.equal(quantiteRestante({ quantite: 5, quantite_recue: 9 }), 0)
})

test('estEntierementRecu : toutes lignes soldées, au moins une', () => {
  assert.equal(estEntierementRecu([]), false)
  assert.equal(estEntierementRecu([{ quantite: 5, quantite_recue: 5 }]), true)
  assert.equal(estEntierementRecu([
    { quantite: 5, quantite_recue: 5 },
    { quantite: 3, quantite_recue: 1 },
  ]), false)
})

test('buildReceptionPayload : plafonne au reste, ignore <=0', () => {
  const lignes = [
    { id: 1, quantite: 10, quantite_recue: 4 }, // reste 6
    { id: 2, quantite: 5, quantite_recue: 5 },  // reste 0
  ]
  // Demander 100 sur la ligne 1 → plafonné à 6 ; 0/négatif/déjà soldé ignorés.
  assert.deepEqual(
    buildReceptionPayload(lignes, { 1: 100, 2: 3 }),
    [{ ligne: 1, quantite: 6 }],
  )
  assert.deepEqual(buildReceptionPayload(lignes, { 1: 0, 2: -2 }), [])
  assert.deepEqual(buildReceptionPayload(lignes, { 1: 2 }), [
    { ligne: 1, quantite: 2 },
  ])
})

test('penuries : filtre manque > 0', () => {
  const items = [
    { sku: 'A', manque: 7 },
    { sku: 'B', manque: 0 },
    { sku: 'C', manque: 2 },
  ]
  assert.deepEqual(lignesEnPenurie(items).map((i) => i.sku), ['A', 'C'])
  assert.equal(nbPenuries(items), 2)
  assert.equal(nbPenuries([]), 0)
})
