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

import {
  defaultProductLines, lignesParDefautDuMarche, signatureGabarit, tableIntacte,
} from './calc/lignesDefaut.js'
import { estArticlePompage } from './calc/classification.js'

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

// T4-U3-006 — le marché « Agricole (pompage) » part de SES lignes : jamais
// d'onduleur ni de batterie (CLAUDE.md « Pompage compositions contain NO
// inverter and NO battery »), ni de forfait au panneau tarifé à 0.
test('T4-U3-006 — modèle agricole : pompe, variateur, panneaux… sans onduleur ni batterie', () => {
  const lignes = lignesParDefautDuMarche(CATALOGUE, 'agricole')
  const noms = lignes.map((l) => l.designation)
  for (const attendu of ['Pompe', 'Variateur', 'Afficheur du variateur', 'Panneaux', 'Structure au sol']) {
    assert.ok(noms.includes(attendu), attendu)
  }
  for (const l of lignes) {
    assert.doesNotMatch(l.designation, /onduleur|batterie|smart meter|wifi|dongle/i, l.designation)
    assert.equal(l.produit, '', `${l.designation} : aucun produit imposé (auto-remplir ou choix)`)
  }
  assert.deepEqual(
    lignesParDefautDuMarche(CATALOGUE, 'residentiel').map((l) => l.designation),
    defaultProductLines(CATALOGUE).map((l) => l.designation))
})

test('T4-U3-006 — changer de marché remplace une table INTACTE, jamais une table éditée', () => {
  const avec = (ls) => ls.map((l, i) => ({ ...l, _key: `k${i}`, compose: true }))
  const residentiel = avec(lignesParDefautDuMarche(CATALOGUE, 'residentiel'))
  const signature = signatureGabarit(residentiel)
  assert.equal(tableIntacte(residentiel, signature), true)
  const editee = residentiel.map((l, i) => (i === 0 ? { ...l, quantite: 3, quantiteManuelle: true } : l))
  assert.equal(tableIntacte(editee, signature), false)
  assert.equal(tableIntacte([...residentiel, { designation: 'Ajout', produit: '7', quantite: 1 }], signature), false)
  assert.equal(tableIntacte(residentiel, null), false)
})

// D-ACAL-130 — un article au rôle POMPAGE déclaré (hors câble DC partagé) ne
// remplit jamais la table résidentielle / C&I ; le mode agricole est intact.
test('D-ACAL-130 — structure de pompage chiffrée jamais structure résidentielle', () => {
  const pompage = P(60, 'Structure acier au sol pompage', 450, { role_pompage: 'structure_sol' })
  const sansAcierPrice = CATALOGUE.map((p) => (p.nom === 'Structures acier' ? { ...p, prix_vente: '0' } : p))
  const acier = (ls) => ls.find((l) => l.designation === 'Structures acier' || l.produit === '60')
  // Sans la garde, « … acier … » chiffré serait la structure acier par défaut.
  assert.equal(acier(defaultProductLines([...sansAcierPrice, pompage])).produit, '')
  // Une structure acier ordinaire n'est pas touchée.
  assert.equal(acier(defaultProductLines([...CATALOGUE, pompage])).produit, '41')
  // Le rôle partagé « cable_dc » n'est pas un article de pompage.
  assert.equal(estArticlePompage({ role_pompage: 'cable_dc' }), false)
  assert.equal(estArticlePompage({ role_pompage: 'structure_sol' }), true)
  assert.equal(estArticlePompage({ role_pompage: '' }), false)
  assert.equal(estArticlePompage({}), false)
  // Mode agricole : la même table, avec ou sans l'article de pompage.
  assert.deepEqual(lignesParDefautDuMarche([...CATALOGUE, pompage], 'agricole'),
    lignesParDefautDuMarche(CATALOGUE, 'agricole'))
})
