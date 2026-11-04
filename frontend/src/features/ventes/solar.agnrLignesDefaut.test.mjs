// AGNR27 — la table par défaut du générateur (`defaultProductLines`) ne pointe
// jamais un produit à prix nul : « Structures acier » et les rôles `first(...)`
// prennent le premier produit PRIX CONNU du rôle, ou restent sans produit.
//
// Catalogue : extrait du catalogue démo (trié par nom, `ProduitViewSet.ordering
// = ['nom']`) + l'article seed C&I `CI-STRUCT-BAC` à prix vide, servi AVANT
// « Structures acier » dans l'ordre alphabétique.
//
// Run : node --test src/features/ventes/solar.agnrLignesDefaut.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { defaultProductLines } from './calc/lignesDefaut.js'

const P = (id, nom, prix_vente, extra = {}) => ({ id, nom, prix_vente: String(prix_vente), tva: '20.00', ...extra })
const CATALOGUE = [
  P(11, 'Accessoires de pose', 0),
  P(12, 'Accessoires solaires', 450),
  P(20, 'Installation', 0),
  P(21, 'Installation et mise en service', 2500),
  P(30, 'Smart Meter Huawei DTSU666', 0),
  P(31, 'Smart Meter Huawei DTSU666-H', 1200),
  P(40, 'Structure bac acier C&I', 0, { reference: 'CI-STRUCT-BAC', role_devis_effectif: 'structure' }),
  P(41, 'Structures acier', 375),
  P(42, 'Structures aluminium', 0),
  P(50, 'Transport', 600),
]

test('AGNR27 — la ligne acier pointe « Structures acier » (375), jamais l’article C&I à 0', () => {
  const lignes = defaultProductLines(CATALOGUE)
  const acier = lignes.find((l) => /acier/i.test(l.designation))
  assert.equal(String(acier.produit), '41')
})

test('AGNR27 — aucune ligne par défaut ne référence un produit sans prix', () => {
  const sansPrix = new Set(CATALOGUE.filter((p) => !(parseFloat(p.prix_vente) > 0)).map((p) => String(p.id)))
  for (const l of defaultProductLines(CATALOGUE)) {
    assert.equal(sansPrix.has(String(l.produit ?? '')), false, `ligne « ${l.designation} » → produit sans prix`)
  }
})

test('AGNR27 — un rôle sans aucun produit prix connu reste sans produit (placeholder nommé)', () => {
  const lignes = defaultProductLines(CATALOGUE)
  const alu = lignes.find((l) => /aluminium/i.test(l.designation))
  assert.equal(alu.produit || '', '')
})

// ADVS47 — TVA standard société sur un produit sans taux (table par défaut + retaux).
import { retauxerLignesSansTva } from './calc/lignesDefaut.js'

test('ADVS47 — produit sans taux : 14 % société à l’écran ; produit à 10 % inchangé ; sans réglage : 20', () => {
  const cat = [
    { id: 1, nom: 'Installation et mise en service', prix_vente: '2500', tva: null },
    { id: 2, nom: 'Transport', prix_vente: '600', tva: '10.00' },
  ]
  const inst = (std) => defaultProductLines(cat, undefined, std).find((l) => String(l.produit) === '1')
  assert.equal(inst(14).taux_tva, 14)
  assert.equal(inst(undefined).taux_tva, 20)
  const transport = defaultProductLines(cat, undefined, 14).find((l) => String(l.produit) === '2')
  assert.equal(transport.taux_tva, 10)
  assert.ok(defaultProductLines(cat, undefined, 14).every((l) => l.produit || l.taux_tva === 14))
})

test('ADVS47 — réglages société tardifs : ligne composée suit 14 %, saisie manuelle intacte', () => {
  const cat = [{ id: 1, nom: 'Installation', prix_vente: '2500', tva: null }]
  const l0 = defaultProductLines(cat).find((l) => String(l.produit) === '1')
  const lignes = [{ ...l0, compose: true }, { ...l0, compose: true, tvaManuelle: true }]
  const out = retauxerLignesSansTva(lignes, cat, 14)
  assert.equal(out[0].taux_tva, 14)
  assert.ok(Math.abs(out[0].prix_unit_ttc - 2500 * 1.14) < 0.01)
  assert.equal(out[1].taux_tva, 20)
  assert.equal(retauxerLignesSansTva(out, cat, 14), out)
})
