// SPL43 — la fabrique de lignes du générateur, EXÉCUTÉE (plus de regex sur
// la source) : clés `_key` séquentielles d'un compteur unique, champs
// préservés au rechargement, ligne vide et ligne de structure.
//
// Run : node --test src/features/ventes/quote/ligneFabrique.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { newKey, withKeys, emptyLine, structureLine } from './ligneFabrique.js'

test('les clés viennent d’UN compteur : séquentielles entre toutes les fabriques', () => {
  const a = newKey()
  const [l1, l2] = withKeys([{ produit: 1, designation: 'A', quantite: 1, prix_unit_ttc: 10 },
    { produit: 2, designation: 'B', quantite: 2, prix_unit_ttc: 20 }])
  const vide = emptyLine()
  const section = structureLine('section')
  assert.deepEqual([l1._key, l2._key, vide._key, section._key], [a + 1, a + 2, a + 3, a + 4])
})

test('withKeys : texte d’écran, verrous et rôle conservés, défauts honnêtes', () => {
  const [l] = withKeys([{
    produit: 101, designation: 'Panneau', quantite: 8, prix_unit_ttc: 1320, taux_tva: 10,
    prixManuel: true, quantiteManuelle: true, variante: 'sans', role_devis: 'panneau',
    remise: 5, lot: 3, compose: true, groupeIndex: 1, groupeLabel: 'Villa A',
  }])
  assert.equal(l.produit, '101')
  assert.equal(l.quantite, '8')
  assert.equal(l.prix_unit_ttc, '1320')
  assert.equal(l.taux_tva, '10')
  assert.equal(l.prixManuel, true)
  assert.equal(l.quantiteManuelle, true)
  assert.equal(l.variante, 'sans')
  assert.equal(l.role_devis, 'panneau')
  assert.equal(l.remise, '5')
  assert.equal(l.lot, 3)
  assert.equal(l.compose, true)
  assert.equal(l.groupeIndex, 1)
  const [d] = withKeys([{ designation: 'X', quantite: 1, prix_unit_ttc: 0 }])
  assert.deepEqual([d.produit, d.taux_tva, d.typeLigne, d.remise, d.variante, d.groupeIndex],
    ['', '20', 'produit', '0', '', null])
})

test('emptyLine : quantité 0, TVA suggérée (20 % sans stockage), aucun verrou', () => {
  const l = emptyLine()
  assert.equal(l.quantite, '0')
  assert.equal(l.taux_tva, '20')
  assert.equal(l._tvaSuggested, true)
  assert.equal(l.prixManuel, false)
  assert.equal(l.quantiteManuelle, false)
  assert.equal(l.typeLigne, 'produit')
})

test('structureLine : section / note sans produit ni prix', () => {
  const n = structureLine('note')
  assert.equal(n.typeLigne, 'note')
  assert.equal(n.produit, '')
  assert.equal(n.prix_unit_ttc, '0')
})
