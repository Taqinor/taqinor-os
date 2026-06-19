// Tests des helpers de stock multi-emplacements (N15).
// Run with: node --test src/features/stock/emplacements.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  quantiteEmplacement, totalVentile, validateTransfert, produitDansEmplacement,
} from './emplacements.js'

const breakdown = [
  { emplacement_id: 1, emplacement_nom: 'Dépôt principal', is_principal: true, quantite: 8 },
  { emplacement_id: 2, emplacement_nom: 'Camionnette', is_principal: false, quantite: 2 },
]

test('quantiteEmplacement : lit la quantité par id (souple sur le type)', () => {
  assert.equal(quantiteEmplacement(breakdown, 1), 8)
  assert.equal(quantiteEmplacement(breakdown, '2'), 2)
  assert.equal(quantiteEmplacement(breakdown, 999), 0)
  assert.equal(quantiteEmplacement(null, 1), 0)
})

test('totalVentile : la ventilation reconstitue le total', () => {
  assert.equal(totalVentile(breakdown), 10)
  assert.equal(totalVentile([]), 0)
})

test('validateTransfert : null quand tout est valide', () => {
  assert.equal(
    validateTransfert({ breakdown, source: 1, destination: 2, quantite: 5 }),
    null)
})

test('validateTransfert : source/destination requises et distinctes', () => {
  assert.match(
    validateTransfert({ breakdown, source: 1, destination: 1, quantite: 1 }),
    /différentes/)
  assert.match(
    validateTransfert({ breakdown, source: '', destination: 2, quantite: 1 }),
    /source et la destination/)
})

test('validateTransfert : quantité positive et entière', () => {
  assert.match(
    validateTransfert({ breakdown, source: 1, destination: 2, quantite: 0 }),
    /positive/)
  assert.match(
    validateTransfert({ breakdown, source: 1, destination: 2, quantite: 1.5 }),
    /entier/)
})

test('validateTransfert : refuse de dépasser le stock de la source', () => {
  assert.match(
    validateTransfert({ breakdown, source: 2, destination: 1, quantite: 5 }),
    /insuffisante/)
})

test('produitDansEmplacement : filtre catalogue par emplacement', () => {
  const p = { stock_par_emplacement: breakdown }
  assert.equal(produitDansEmplacement(p, ''), true)      // tous les emplacements
  assert.equal(produitDansEmplacement(p, 1), true)       // dépôt principal (8)
  assert.equal(produitDansEmplacement(p, '2'), true)     // camionnette (2)
  assert.equal(produitDansEmplacement(p, 999), false)    // emplacement vide
  // produit sans ventilation remontée → pas de stock dans un emplacement donné
  assert.equal(produitDansEmplacement({}, 1), false)
  assert.equal(produitDansEmplacement({}, ''), true)
})
