// Forfaits au panneau : l'écran pose le prix que le serveur écrira.
// Nouveau fichier car : module neuf (`forfaitsPanneau.js`), aucun module de
// test existant ne le couvre.
// Run : node --test src/features/ventes/quote/forfaitsPanneau.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  prixForfaitHt, porteBaremeParPanneau, comptesPanneauxEcran, retarifierForfaitsEcran,
} from './forfaitsPanneau.js'
import { lignesEcranVersPayload } from './lignesEcran.js'

// Mêmes barèmes que `apps/ventes/tests/test_pvkit_composition.py::BAREMES_FORFAIT`
// (chaînes telles que DRF les sert : DecimalField 2 et 4 décimales).
const INST = { id: 1, nom: 'Installation', prix_vente: '4000', tva: 20, prix_fixe_ht: '2000.00', prix_par_panneau_ht: '250.0000' }
const ACC = { id: 2, nom: 'Accessoires', prix_vente: '2000', tva: 20, prix_fixe_ht: '0.00', prix_par_panneau_ht: '52.0833' }
const TAB = { id: 3, nom: 'Tableau De Protection AC/DC', prix_vente: '2000', tva: 20, prix_fixe_ht: '0.00', prix_par_panneau_ht: '203.1250' }
const PAN = { id: 10, nom: 'Panneau Jinko 550W', prix_vente: '1000', tva: 10, prix_fixe_ht: null, prix_par_panneau_ht: null }
const OND = { id: 11, nom: 'Onduleur réseau 5kW', prix_vente: '9000', tva: 20, prix_fixe_ht: null, prix_par_panneau_ht: null }
const PRODUITS = [INST, ACC, TAB, PAN, OND]

test('prixForfaitHt — parité avec test_pvkit_composition.py (prix_forfait_ht)', () => {
  // test_les_deux_ancrages_du_fondateur_sont_tenus
  assert.equal(prixForfaitHt(INST, 8), '4000.00')
  assert.equal(prixForfaitHt(INST, 16), '6000.00')
  // test_l_entre_deux_se_lisse_au_lieu_de_sauter
  assert.equal(prixForfaitHt(INST, 10), '4500.00')
  assert.equal(prixForfaitHt(ACC, 10), '520.83')
  assert.equal(prixForfaitHt(TAB, 10), '2031.25')
  assert.equal(prixForfaitHt(INST, 9), '4250.00')
  // test_accessoires_moitie_et_tableau_plus_30_pct
  assert.equal(prixForfaitHt(ACC, 8), '416.67')
  assert.equal(prixForfaitHt(ACC, 16), '833.33')
  assert.equal(prixForfaitHt(TAB, 8), '1625.00')
  assert.equal(prixForfaitHt(TAB, 16), '3250.00')
  // test_le_barreme_se_change_depuis_le_stock : 3 000 + 300 × 8
  assert.equal(prixForfaitHt({ prix_fixe_ht: '3000', prix_par_panneau_ht: '300' }, 8), '5400.00')
  // test_une_part_fixe_seule_suffit
  const plat = { prix_fixe_ht: '750', prix_par_panneau_ht: null }
  assert.equal(prixForfaitHt(plat, 8), '750.00')
  assert.equal(prixForfaitHt(plat, 16), '750.00')
  // test_sans_bareme_le_produit_garde_son_prix_de_vente : aucun barème ⇒ null
  assert.equal(prixForfaitHt({ prix_vente: '2000', prix_fixe_ht: null, prix_par_panneau_ht: null }, 8), null)
  assert.equal(prixForfaitHt(PAN, 8), null)
})

test('prixForfaitHt — bords : 0 panneau = part fixe, nombre tronqué, valeurs numériques', () => {
  assert.equal(prixForfaitHt(INST, 0), '2000.00')
  assert.equal(prixForfaitHt(INST, null), '2000.00')
  assert.equal(prixForfaitHt(INST, 10.9), '4500.00') // int(10.9) == 10 côté Python
  assert.equal(prixForfaitHt({ prix_fixe_ht: 3000, prix_par_panneau_ht: 150 }, 10), '4500.00')
  // 52,0833 × 12 = 624,9996 → 625,00 (ROUND_HALF_UP au centime, sans flottant)
  assert.equal(prixForfaitHt(ACC, 12), '625.00')
  assert.equal(prixForfaitHt({ prix_fixe_ht: null, prix_par_panneau_ht: '0.0050' }, 1), '0.01')
  assert.equal(porteBaremeParPanneau(null), false)
  assert.equal(porteBaremeParPanneau({ prix_fixe_ht: '0.00', prix_par_panneau_ht: null }), true)
  assert.equal(porteBaremeParPanneau({ prix_vente: '10' }), false)
})

const ligne = (p, quantite, extra = {}) => ({
  produit: String(p.id), designation: p.nom, quantite,
  prix_unit_ttc: Math.round(parseFloat(p.prix_vente) * (1 + p.tva / 100) * 100) / 100,
  taux_tva: p.tva, prixHtOrigine: (parseFloat(p.prix_vente)).toFixed(2), ...extra,
})

test('résidentiel 12 panneaux : installation 6 000 TTC (2 000 + 250 × 12, HT × 1,2) — plus 4 800', () => {
  const lines = [ligne(PAN, 12), ligne(OND, 1), ligne(INST, 1), ligne(ACC, 1), ligne(TAB, 1)]
  const out = retarifierForfaitsEcran(lines, PRODUITS)
  assert.equal(out[2].prix_unit_ttc, 6000)
  assert.equal(out[2].prixHtOrigine, '5000.00')
  assert.equal(out[3].prixHtOrigine, '625.00')
  assert.equal(out[4].prixHtOrigine, '2437.50')
  // Produits SANS barème : la même ligne, objet identique (byte-identique).
  assert.equal(out[0], lines[0])
  assert.equal(out[1], lines[1])
  // Ce que le serveur recevra : exactement le barème (aucune réécriture côté serveur).
  const payload = lignesEcranVersPayload(out)
  assert.deepEqual(payload.slice(2).map(l => l.prix_unitaire), ['5000.00', '625.00', '2437.50'])
})

test('le compte suit les lignes : 12 → 16 panneaux re-tarife, et un 2e passage ne change rien', () => {
  const a = retarifierForfaitsEcran([ligne(PAN, 12), ligne(INST, 1)], PRODUITS)
  const b = retarifierForfaitsEcran([{ ...a[0], quantite: '16' }, a[1]], PRODUITS)
  assert.equal(b[1].prixHtOrigine, '6000.00')
  assert.equal(b[1].prix_unit_ttc, 7200)
  assert.equal(retarifierForfaitsEcran(b, PRODUITS), b, 'même tableau quand rien ne change')
})

test('agricole : kit de 10 panneaux, installation prix_vente 0 + barème 3 000 + 150/panneau → 4 500 HT', () => {
  const inst0 = { id: 7, nom: 'Installation pompage', prix_vente: '0', tva: 20, prix_fixe_ht: '3000.00', prix_par_panneau_ht: '150.0000' }
  const out = retarifierForfaitsEcran([ligne(PAN, 10), ligne(inst0, 1)], [PAN, inst0])
  assert.equal(out[1].prixHtOrigine, '4500.00')
  assert.equal(out[1].prix_unit_ttc, 5400)
})

test('prix tapé (prixManuel) : jamais re-tarifé (D12)', () => {
  const lines = [ligne(PAN, 12), { ...ligne(INST, 1), prix_unit_ttc: '3000', prixManuel: true }]
  assert.equal(retarifierForfaitsEcran(lines, PRODUITS), lines)
})

test('panneau reconnu par le NOM du produit quand la désignation est réécrite', () => {
  const lines = [{ ...ligne(PAN, 9), designation: 'Modules posés' }, ligne(INST, 1)]
  assert.equal(comptesPanneauxEcran(lines, PRODUITS)[''], 9)
  assert.equal(retarifierForfaitsEcran(lines, PRODUITS)[1].prixHtOrigine, '4250.00')
})

test('lignes non envoyées (sans produit, quantité 0, section) : hors compte', () => {
  const lines = [
    { produit: '', designation: 'Panneaux', quantite: 8 },
    ligne(PAN, 0),
    { typeLigne: 'section', designation: 'Panneau', quantite: 5, produit: '10' },
    ligne(INST, 1),
  ]
  assert.deepEqual(comptesPanneauxEcran(lines, PRODUITS), { '': 0, sans: 0, avec: 0 })
  assert.equal(retarifierForfaitsEcran(lines, PRODUITS)[3].prixHtOrigine, '2000.00')
})

test('options : chaque forfait varianté suit SON option ; commun divergent ⇒ abstention (comme le serveur)', () => {
  const lines = [
    ligne(PAN, 8, { variante: 'sans' }),
    ligne(PAN, 12, { variante: 'avec' }),
    ligne(INST, 1, { variante: 'sans' }),
    ligne(INST, 1, { variante: 'avec' }),
    ligne(ACC, 1),
  ]
  assert.deepEqual(comptesPanneauxEcran(lines, PRODUITS), { '': null, sans: 8, avec: 12 })
  const out = retarifierForfaitsEcran(lines, PRODUITS)
  assert.equal(out[2].prixHtOrigine, '4000.00')
  assert.equal(out[3].prixHtOrigine, '5000.00')
  assert.equal(out[4], lines[4], 'forfait commun à deux options divergentes : prix inchangé')
  // Options non divergentes (commun + même compte) : le commun suit ce compte.
  const egal = [ligne(PAN, 6), ligne(PAN, 2, { variante: 'sans' }), ligne(PAN, 2, { variante: 'avec' }), ligne(ACC, 1)]
  assert.deepEqual(comptesPanneauxEcran(egal, PRODUITS), { '': 8, sans: 8, avec: 8 })
  assert.equal(retarifierForfaitsEcran(egal, PRODUITS)[3].prixHtOrigine, '416.67')
})

test('prix RELU du serveur (AGNR16) : gardé à la réouverture, re-tarifé quand le compte change', () => {
  const relu = { ...ligne(INST, 1), prix_unit_ttc: '4800', prixHtOrigine: undefined, prixRelu: true }
  const ouvert = retarifierForfaitsEcran([ligne(PAN, 8), relu], PRODUITS)
  assert.equal(ouvert[1].prix_unit_ttc, '4800', 'réouverture : prix relu inchangé')
  assert.deepEqual(ouvert[1].forfaitPanneaux, { produit: '1', n: 8 })
  assert.equal(retarifierForfaitsEcran(ouvert, PRODUITS), ouvert)
  const geste = retarifierForfaitsEcran([{ ...ouvert[0], quantite: 10 }, ouvert[1]], PRODUITS)
  assert.equal(geste[1].prix_unit_ttc, '5400')
  assert.equal(geste[1].prixHtOrigine, '4500.00')
})

test('catalogue absent ou vide : lignes rendues telles quelles', () => {
  const lines = [ligne(PAN, 8), ligne(INST, 1)]
  assert.equal(retarifierForfaitsEcran(lines, []), lines)
  assert.equal(retarifierForfaitsEcran(lines, undefined), lines)
})
