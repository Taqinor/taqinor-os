// QJR570 (D-QJR5-4) — recomposer (Auto-remplir / Appliquer cette taille /
// Recalculer) FUSIONNE au lieu de remplacer : prix tapés et lignes ajoutées à
// la main conservés d'office ; seuls les conflits de quantité figée sont
// remontés (jamais reportés en silence).
// Run : node --test src/features/ventes/solar.recomposition.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { fusionnerRecomposition, lignesQuantiteFigee } from './solar.js'

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

test('lignesQuantiteFigee : seules les lignes produit verrouillées', () => {
  const figees = lignesQuantiteFigee([
    L(7, 'Socles', 24, 50, { quantiteManuelle: true }),
    L(8, 'Panneau', 10, 1200),
    { produit: '', designation: 'Note', typeLigne: 'note', quantiteManuelle: true },
  ])
  assert.deepEqual(figees.map(l => l.designation), ['Socles'])
})

test('lignes relues d’un devis enregistré + nouvelle composition : aucun doublon onduleur/batterie', async () => {
  const { lignesServeurVersEcran } = await import('./quote/lignesEcran.js')
  const serveur = [
    { id: 1, produit: 5, designation: 'Panneau 550W', quantite: '10', prix_unitaire: '1000', taux_tva: '20', ordre: 0, type_ligne: 'produit' },
    { id: 2, produit: 6, designation: 'Onduleur 5 kW', quantite: '1', prix_unitaire: '7500', taux_tva: '20', ordre: 1, type_ligne: 'produit' },
    { id: 3, produit: 7, designation: 'Batterie 5 kWh', quantite: '1', prix_unitaire: '16000', taux_tva: '20', ordre: 2, type_ligne: 'produit' },
  ]
  const relues = lignesServeurVersEcran(serveur, 20)
  const generees = [
    L(5, 'Panneau 550W', 12, 1200),
    L(60, 'Onduleur 8 kW', 1, 11000),
    L(70, 'Batterie 10 kWh', 1, 30000),
  ]
  const { lignes } = fusionnerRecomposition(relues, generees)
  assert.equal(lignes.length, 3)
  assert.deepEqual(lignes.map(l => l.produit), ['5', '60', '70'])
})
