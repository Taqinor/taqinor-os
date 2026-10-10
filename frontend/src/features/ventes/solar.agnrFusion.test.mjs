// AGNR20 — `fusionnerRecomposition` part de la ligne ANCIENNE appariée et
// n'écrase que ce que la composition POSSÈDE (produit, quantité non figée,
// variante, prix non tapé) : taux 0 % + base légale, désignation, remise,
// groupe villa, lot… survivent à « Auto-remplir » / « Recalculer ».
//
// Run : node --test src/features/ventes/solar.agnrFusion.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { fusionnerRecomposition, appliquerRecomposition } from './solar.js'
import { lignesServeurVersEcran } from './quote/lignesEcran.js'

const ANCIENNE = {
  produit: '5', designation: 'Pompe perso', quantite: '1', prix_unit_ttc: '3000',
  taux_tva: '0', tvaBaseLegale: 'Art. 92-I-6', remise: '5', groupeIndex: 2,
  groupeLabel: 'Villa 2', lot: 7, typeLigne: 'produit', role_devis: 'pompe', variante: 'sans',
}
const GENEREE = { produit: '5', designation: 'Pompe OSP', quantite: 2, prix_unit_ttc: 3600, taux_tva: 20 }

//: Les clés que la composition POSSÈDE (seules à pouvoir changer).
const POSSEDEES = new Set(['produit', 'quantite', 'variante', 'compose', 'prix_unit_ttc'])

test('AGNR20 — la ligne appariée garde taux 0 %, base légale, désignation, remise, groupe et lot', () => {
  const { lignes } = fusionnerRecomposition([ANCIENNE], [GENEREE])
  assert.equal(lignes.length, 1)
  const l = lignes[0]
  assert.equal(l.taux_tva, '0')
  assert.equal(l.tvaBaseLegale, 'Art. 92-I-6')
  assert.equal(l.designation, 'Pompe perso')
  assert.equal(l.remise, '5')
  assert.equal(l.groupeIndex, 2)
  assert.equal(l.groupeLabel, 'Villa 2')
  assert.equal(l.lot, 7)
  // Ce que la composition possède : quantité (non figée), variante, prix (non tapé).
  assert.equal(l.quantite, 2)
  assert.equal(l.variante, '')
  assert.equal(l.prix_unit_ttc, 3600)
  assert.equal(l.compose, true)
})

test('AGNR20 — propriété : toute clé d’une ligne relue du serveur hors des clés possédées survit', () => {
  // Une ligne telle que l'écran la relit d'un devis (toutes les clés réelles).
  const [relue] = lignesServeurVersEcran([{
    id: 1, produit: 5, designation: 'Pompe perso', quantite: '1', prix_unitaire: '3000.00',
    taux_tva: '0.00', base_legale_tva: 'Art. 92-I-6', remise: '5.00', ordre: 0,
    type_ligne: 'produit', optionnelle: false, variante: 'sans', groupe_index: 2,
    groupe_label: 'Villa 2', lot: 7, role_devis: 'pompe', prix_manuel: false, quantite_manuelle: false,
  }])
  const { lignes } = fusionnerRecomposition([relue], [GENEREE])
  for (const [cle, valeur] of Object.entries(relue)) {
    if (POSSEDEES.has(cle)) continue
    assert.deepEqual(lignes[0][cle], valeur, `clé ${cle} écrasée par la composition`)
  }
})

test('AGNR20 — prix tapé et quantité figée restent ceux du vendeur', () => {
  const { lignes, conflits } = fusionnerRecomposition(
    [{ ...ANCIENNE, prixManuel: true, quantiteManuelle: true }], [GENEREE])
  assert.equal(lignes[0].prix_unit_ttc, '3000')
  assert.equal(lignes[0].quantite, '1')
  assert.equal(conflits.length, 1)
})

test('AGNR20 — le mode « recalcule » (choix explicite) reste un remplacement', () => {
  const lignes = appliquerRecomposition([ANCIENNE], [GENEREE], 'recalcule')
  const l = lignes.lignes[0]
  assert.equal(l.designation, 'Pompe OSP')
})
