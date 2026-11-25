// QJR526 — la réouverture re-dérive des lignes le wattage, la structure, le
// hors-réseau et « Composition libre ».
// Run : node --test src/features/ventes/quote/reouverture.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { deriverReouverture, tailleAutoRemplirPompage } from './reouverture.js'

const L = (designation, quantite, produit = '1') =>
  ({ designation, quantite: String(quantite), produit: String(produit), typeLigne: 'produit' })

test('devis 637 : 10 × 550 W + structure alu (produit 77) + onduleur hors réseau', () => {
  assert.deepEqual(deriverReouverture([
    L('Panneau mono 550W', 10),
    L('Structure aluminium', 1, 77),
    L('Onduleur hors réseau 5kW', 1),
  ]), {
    panelW: '550', structure: 'aluminium', structureProduitId: '77',
    horsReseau: true, accessoiresOnly: false,
  })
})

test('wattage : celui de la ligne panneau DOMINANTE', () => {
  const d = deriverReouverture([
    L('Panneau 710W', 2), L('Panneau 550W', 12), L('Onduleur réseau 5kW', 1),
  ])
  assert.equal(d.panelW, '550')
  assert.equal(d.horsReseau, false)
})

test('structure acier + pas de wattage lisible → panelW null (défaut conservé)', () => {
  const d = deriverReouverture([
    L('Panneau solaire', 8), L('Structure acier galvanisé', 1, 5), L('Onduleur hybride 5kW', 1),
  ])
  assert.equal(d.panelW, null)
  assert.equal(d.structure, 'acier')
  assert.equal(d.structureProduitId, '5')
})

test('Composition libre : aucune paire panneau + onduleur', () => {
  assert.equal(deriverReouverture([L('Câble solaire 6mm', 50)]).accessoiresOnly, true)
  assert.equal(deriverReouverture([L('Panneau 550W', 4)]).accessoiresOnly, true)
  // sans ligne produit : jamais « libre » par défaut
  assert.equal(deriverReouverture([]).accessoiresOnly, false)
  assert.equal(deriverReouverture([
    { typeLigne: 'section', designation: 'Titre', quantite: '0' },
  ]).accessoiresOnly, false)
})

test('agricole : « libre » = aucune pompe', () => {
  assert.equal(deriverReouverture([L('Pompe immergée 5.5 CV', 1)], { mode: 'agricole' })
    .accessoiresOnly, false)
  assert.equal(deriverReouverture([L('Panneau 550W', 10)], { mode: 'agricole' })
    .accessoiresOnly, true)
})

test('T4-V2-007 — Auto-remplir agricole : le wattage est celui du panneau des LIGNES', () => {
  // Kit servi : 4 × « Panneau Canadien Solar 715W » ⇒ 2,86 kWc, jamais 4 × 710.
  const lignes = [
    L('Pompe immergée solaire 3 CV Monophasé', 1),
    L('Panneau Canadien Solar 715W', 4),
    L('Structure au sol', 4),
  ]
  assert.deepEqual(tailleAutoRemplirPompage({ nb_panneaux: 4, kwc: 2.86 }, lignes),
    { panneaux: 4, panel_watt: 715 })
  // Aucun wattage lisible : seule la taille est posée (le défaut reste).
  assert.deepEqual(tailleAutoRemplirPompage({ nb_panneaux: 4 }, [L('Pompe 3 CV', 1)]),
    { panneaux: 4 })
  assert.equal(tailleAutoRemplirPompage({ nb_panneaux: null }, lignes), null)
})

test('lignes serveur (type_ligne snake_case) acceptées', () => {
  const d = deriverReouverture([
    { designation: 'Panneau 545W', quantite: '6.00', produit: 3, type_ligne: 'produit' },
  ])
  assert.equal(d.panelW, '545')
})
