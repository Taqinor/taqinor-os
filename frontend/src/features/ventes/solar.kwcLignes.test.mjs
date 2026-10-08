// QJR568 — le kWc réellement FACTURÉ par les lignes (celui que le PDF dérive,
// builder.py) alimente prix/kWc, prix cible et études C&I ; le champ « nb
// panneaux » reste la CIBLE du dimensionnement.
// Run : node --test src/features/ventes/solar.kwcLignes.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { kwcFactureDesLignes } from './solar.js'

const panneau = (q, extra = {}) => ({ designation: 'Panneau Longi 550W', quantite: String(q), produit: '1', ...extra })
const onduleur = { designation: 'Onduleur réseau 50 kW', quantite: '1', produit: '2' }

test('120 × 550 W → 66 kWc, quel que soit le champ « nb panneaux » (repli ignoré)', () => {
  assert.equal(kwcFactureDesLignes([panneau(120), onduleur], 550, 55), 66)
  assert.equal(kwcFactureDesLignes([panneau(120), onduleur], '550', 0), 66)
})

test('sans ligne panneau → repli sur la cible kwp', () => {
  assert.equal(kwcFactureDesLignes([onduleur], 550, 55), 55)
  assert.equal(kwcFactureDesLignes([], 550, 12.5), 12.5)
  assert.equal(kwcFactureDesLignes(null, 550, 7), 7)
})

test('branche SANS seulement : une ligne panneau variante « avec » ne compte pas', () => {
  const lignes = [panneau(10), panneau(4, { variante: 'avec' }), onduleur]
  // AGNR18 — le watt LU de la ligne (550 W) prime sur panelW (500) : 5,5 kWc.
  assert.equal(kwcFactureDesLignes(lignes, 500, 99), 5.5)
})

test('wattage illisible → repli (jamais un kWc à 0 inventé)', () => {
  // AGNR18 — illisible = ni désignation ni produit ne portent de watt.
  const sansWatt = panneau(10, { designation: 'Panneau Longi' })
  assert.equal(kwcFactureDesLignes([sansWatt], 0, 3.3), 3.3)
  assert.equal(kwcFactureDesLignes([sansWatt], 500, 3.3), 5)
})
