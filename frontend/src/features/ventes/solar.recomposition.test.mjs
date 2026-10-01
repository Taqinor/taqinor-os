// QJR570 (D-QJR5-4) — recomposer (Auto-remplir / Appliquer cette taille /
// Recalculer) FUSIONNE au lieu de remplacer : prix tapés et lignes ajoutées à
// la main conservés d'office ; seuls les conflits de quantité figée sont
// remontés (jamais reportés en silence).
// Run : node --test src/features/ventes/solar.recomposition.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { fusionnerRecomposition } from './solar.js'
import { lignesServeurVersEcran } from './quote/lignesEcran.js'

const L = (produit, designation, quantite, prix, extra = {}) => ({
  produit: String(produit), designation, quantite: String(quantite),
  prix_unit_ttc: String(prix), taux_tva: '20', typeLigne: 'produit', ...extra,
})

test('prix tapé reporté, produit ajouté et section gardés à leur place, nouvelle ligne générée prise', () => {
  const anciennes = [
    L(5, 'Panneau 550W', 10, 999, { prixManuel: true, compose: true }),
    { produit: '', designation: 'Toiture est', quantite: '0', prix_unit_ttc: '0', typeLigne: 'section' },
    L(9, 'Borne de recharge', 1, 6000),
  ]
  const generees = [
    L(5, 'Panneau 550W', 12, 1200, { variante: '' }),
    L(6, 'Onduleur réseau 5 kW', 1, 9000),
  ]
  const { lignes, conflits } = fusionnerRecomposition(anciennes, generees)
  assert.deepEqual(conflits, [])
  assert.deepEqual(lignes.map(l => [l.produit || l.designation, l.quantite, l.prix_unit_ttc]), [
    ['5', '12', '999'],
    ['Toiture est', '0', '0'],
    ['9', '1', '6000'],
    ['6', '1', '9000'],
  ])
  assert.equal(lignes[0].prixManuel, true)
  assert.equal(lignes[1].typeLigne, 'section')
})

test('quantiteManuelle 24 contre 20 → conflit NOMMÉ, quantité figée gardée', () => {
  const anciennes = [L(7, 'Socles', 24, 50, { quantiteManuelle: true })]
  const generees = [L(7, 'Socles', 20, 55)]
  const { lignes, conflits } = fusionnerRecomposition(anciennes, generees)
  assert.deepEqual(conflits, [{ designation: 'Socles', figee: '24', recalculee: '20' }])
  assert.equal(lignes[0].quantite, '24')
  assert.equal(lignes[0].quantiteManuelle, true)
  // Le prix n'était PAS tapé : celui de la composition est pris.
  assert.equal(lignes[0].prix_unit_ttc, '55')
})

test('quantité figée identique → aucun conflit, verrou conservé', () => {
  const { lignes, conflits } = fusionnerRecomposition(
    [L(7, 'Socles', 20, 50, { quantiteManuelle: true })], [L(7, 'Socles', 20, 50)])
  assert.deepEqual(conflits, [])
  assert.equal(lignes[0].quantiteManuelle, true)
})

test('une ligne issue de la composition PRÉCÉDENTE et absente de la nouvelle est retirée', () => {
  const anciennes = [
    L(5, 'Panneau 550W', 10, 1200, { compose: true }),
    L(13, 'Batterie 5 kWh', 1, 20000, { compose: true }),
    L(14, 'Câble spécial', 2, 300, { compose: true, prixManuel: true }),
  ]
  const { lignes } = fusionnerRecomposition(anciennes, [L(5, 'Panneau 550W', 10, 1200)])
  // La batterie composée hier disparaît ; la ligne au prix tapé reste.
  assert.deepEqual(lignes.map(l => l.produit), ['5', '14'])
})

test('placeholders et lignes produit à quantité nulle non reprises ne survivent pas', () => {
  const anciennes = [
    { produit: '', designation: 'Onduleur réseau', quantite: '1', prix_unit_ttc: '0', typeLigne: 'produit' },
    L(20, 'Structures aluminium', 0, 400),
  ]
  const { lignes } = fusionnerRecomposition(anciennes, [L(5, 'Panneau 550W', 10, 1200)])
  assert.deepEqual(lignes.map(l => l.produit), ['5'])
})

test('optionnelle ajoutée à la main conservée', () => {
  const anciennes = [L(30, 'Borne', 1, 5000, { optionnelle: true, compose: true })]
  const { lignes } = fusionnerRecomposition(anciennes, [L(5, 'Panneau', 10, 1200)])
  assert.deepEqual(lignes.map(l => [l.produit, !!l.optionnelle]), [['5', false], ['30', true]])
})

test('la variante vient de la ligne générée ; chaque ligne générée porte le marqueur de composition', () => {
  const { lignes } = fusionnerRecomposition(
    [L(5, 'Panneau', 10, 1200, { variante: 'sans' })], [L(5, 'Panneau', 12, 1200, { variante: 'avec' })])
  assert.equal(lignes[0].variante, 'avec')
  assert.equal(lignes[0].compose, true)
})

test('ERR-QJR570 — « prendre N (recalculé) » : la quantité recalculée remplace la figée, verrou levé', () => {
  const anciennes = [
    L(7, 'Socles', 24, 50, { quantiteManuelle: true }),
    L(8, 'Rails', 6, 80, { quantiteManuelle: true }),
  ]
  const generees = [L(7, 'Socles', 20, 55), L(8, 'Rails', 6, 80)]
  const { lignes, conflits } = fusionnerRecomposition(anciennes, generees, { prendreRecalcule: true })
  // Le conflit reste NOMMÉ (le vendeur a choisi en le voyant)…
  assert.deepEqual(conflits, [{ designation: 'Socles', figee: '24', recalculee: '20' }])
  // …mais c'est la quantité recalculée qui est prise, verrou levé.
  assert.deepEqual(lignes.map(l => [l.produit, l.quantite, !!l.quantiteManuelle]),
    [['7', '20', false], ['8', '6', true]])
})

// ERR-QJR570-EDITION-DOUBLONS-RECOMPOSITION — régression client : en Édition
// complète les lignes RELUES du serveur n'avaient aucun marqueur `compose`
// → `_ancienneLigneAGarder` les prenait pour des ajouts manuels et la
// recomposition gardait l'ancien onduleur + l'ancienne batterie À CÔTÉ des
// nouveaux (5 lignes au lieu de 3, TTC gonflé, enregistrable/envoyable).
test('ERR-QJR570 — lignes relues sans marqueur + nouvelle composition → aucun onduleur/batterie en double', () => {
  const serveur = [
    { id: 1, ordre: 0, produit: 5, designation: 'Panneau 550W', quantite: '10.00',
      prix_unitaire: '1000.00', taux_tva: '20.00', type_ligne: 'produit' },
    { id: 2, ordre: 1, produit: 13, designation: 'Onduleur hybride Deye 5kW', quantite: '1.00',
      prix_unitaire: '10000.00', taux_tva: '20.00', type_ligne: 'produit' },
    { id: 3, ordre: 2, produit: 15, designation: 'Batterie Dyness 5 kWh', quantite: '1.00',
      prix_unitaire: '15000.00', taux_tva: '20.00', type_ligne: 'produit' },
  ]
  const relues = lignesServeurVersEcran(serveur, '20.00')
  const generees = [
    L(5, 'Panneau 550W', 12, 1200),
    L(23, 'Onduleur hybride Deye 6kW', 1, 14000),
    L(25, 'Batterie Dyness 10 kWh', 1, 30000),
  ]
  const { lignes, conflits } = fusionnerRecomposition(relues, generees)
  assert.deepEqual(conflits, [])
  assert.equal(lignes.length, 3, `attendu 3 lignes, obtenu ${lignes.length} : `
    + lignes.map(l => l.designation).join(' | '))
  assert.deepEqual(lignes.map(l => l.produit), ['5', '23', '25'])
  assert.equal(lignes.filter(l => /onduleur/i.test(l.designation)).length, 1)
  assert.equal(lignes.filter(l => /batterie/i.test(l.designation)).length, 1)
})

test('ERR-QJR570 — relue avec saisie humaine (prix / quantité figés, optionnelle) : gardée, jamais composée', () => {
  const serveur = [
    { id: 1, ordre: 0, produit: 9, designation: 'Borne', quantite: '1.00',
      prix_unitaire: '5000.00', taux_tva: '20.00', type_ligne: 'produit', prix_manuel: true },
    { id: 2, ordre: 1, produit: 7, designation: 'Socles', quantite: '24.00',
      prix_unitaire: '50.00', taux_tva: '20.00', type_ligne: 'produit', quantite_manuelle: true },
    { id: 3, ordre: 2, produit: 30, designation: 'Option', quantite: '1.00',
      prix_unitaire: '100.00', taux_tva: '20.00', type_ligne: 'produit', optionnelle: true },
  ]
  const relues = lignesServeurVersEcran(serveur, '20.00')
  assert.deepEqual(relues.map(l => l.compose), [false, false, false])
  const { lignes } = fusionnerRecomposition(relues, [L(5, 'Panneau 550W', 12, 1200)])
  assert.deepEqual(lignes.map(l => l.produit), ['5', '9', '7', '30'])
})

// ERR-QJR570 (D-QJR5-4) — la PROVENANCE persistée (`ligne_composee`) fait foi
// à la réouverture : un produit ajouté À LA MAIN, enregistré puis rouvert,
// n'a ni prix tapé ni quantité figée — sans marqueur persistant il était pris
// pour une ligne composée et REMPLACÉ au recalcul suivant.
const ondulRelu = (ligneComposee) => ({
  id: 2, ordre: 1, produit: 13, designation: 'Onduleur hybride Deye 5kW', quantite: '1.00',
  prix_unitaire: '10000.00', taux_tva: '20.00', type_ligne: 'produit',
  ...(ligneComposee === undefined ? {} : { ligne_composee: ligneComposee }),
})
const panneauRelu = {
  id: 1, ordre: 0, produit: 5, designation: 'Panneau 550W', quantite: '10.00',
  prix_unitaire: '1000.00', taux_tva: '20.00', type_ligne: 'produit', ligne_composee: true,
}
const recomposition = [
  L(5, 'Panneau 550W', 12, 1200),
  L(23, 'Onduleur hybride Deye 6kW', 1, 14000),
]

test('ERR-QJR570 provenance — ligne_composee:false (ajout manuel relu) : GARDÉE par une recomposition qui change d’onduleur', () => {
  const relues = lignesServeurVersEcran([panneauRelu, ondulRelu(false)], '20.00')
  assert.deepEqual(relues.map(l => l.compose), [true, false])
  const { lignes, conflits } = fusionnerRecomposition(relues, recomposition)
  assert.deepEqual(conflits, [])
  assert.deepEqual(lignes.map(l => l.produit), ['5', '13', '23'])
})

test('ERR-QJR570 provenance — ligne_composee:true : REMPLACÉE par la recomposition', () => {
  const relues = lignesServeurVersEcran([panneauRelu, ondulRelu(true)], '20.00')
  assert.deepEqual(relues.map(l => l.compose), [true, true])
  const { lignes } = fusionnerRecomposition(relues, recomposition)
  assert.deepEqual(lignes.map(l => l.produit), ['5', '23'])
})

test('ERR-QJR570 provenance — null / absente : règle de repli b7f7cbee2 inchangée', () => {
  for (const valeur of [null, undefined]) {
    const relues = lignesServeurVersEcran([panneauRelu, ondulRelu(valeur)], '20.00')
    assert.equal(relues[1].compose, true)
    const { lignes } = fusionnerRecomposition(relues, recomposition)
    assert.deepEqual(lignes.map(l => l.produit), ['5', '23'])
  }
  // Repli : une saisie humaine (prix tapé) garde la ligne, provenance inconnue.
  const [l] = lignesServeurVersEcran([{ ...ondulRelu(null), prix_manuel: true }], '20.00')
  assert.equal(l.compose, false)
})
