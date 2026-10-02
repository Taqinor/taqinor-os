// QJR402 — L'écran du vendeur dit EXACTEMENT ce que dit le noyau :
// `optionTotalsTTC` applique la règle QF9 (miroir de `_panier_sert_huawei` /
// `retirer_accessoires_huawei`, `apps/ventes/utils/options.py:114-134`) et ne
// perd plus l'arrondi au dirham conditionnel-à-la-remise.
//
// AUCUN montant mesuré par la ronde 4 n'est recopié ici : chaque attente est
// DÉRIVÉE d'un mirror indépendant de la règle du noyau (`panierSertHuawei` /
// `totalAttenduPourPanier` ci-dessous), appliqué aux mêmes lignes que celles
// passées à `optionTotalsTTC`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  optionTotalsTTC, appartientAuPanierSans, appartientAuPanierAvec,
  isAnyInverter, isSmartMeter, isWifiDongle, totauxCanoniquesTtc,
} from './solar.js'
import { PAS_ARRONDI_DEVIS } from './remise.js'

// ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — un panier se chiffre par la chaîne
// canonique du noyau (HT persisté → TVA), jamais par Σ TTC saisis.
// ARRONDI-100 : le total par option que le backend facture est ramené au
// palier de 100 MAD inférieur ; le noyau de référence reçoit le même palier
// pour comparer la MÊME quantité arrondie.
const canon = (...rows) => totauxCanoniquesTtc(rows, 0, PAS_ARRONDI_DEVIS)

// ── Mirror indépendant de QF9 (le NOYAU, pas la production) ─────────────────
function estAccessoireHuawei(d) {
  return isSmartMeter(d) || isWifiDongle(d)
}
function panierSertHuawei(rows) {
  const onduleurs = rows.filter(l => isAnyInverter(l?.designation))
  if (onduleurs.length === 0) return false
  let huaweiVu = false
  for (const l of onduleurs) {
    if ((l?.designation || '').toLowerCase().includes('huawei')) huaweiVu = true
    else return false
  }
  return huaweiVu
}
function totalAttenduPourPanier(lignesDuPanier) {
  const rows = panierSertHuawei(lignesDuPanier)
    ? lignesDuPanier
    : lignesDuPanier.filter(l => !estAccessoireHuawei(l?.designation))
  return totauxCanoniquesTtc(rows, 0, PAS_ARRONDI_DEVIS)
}

// Devis résidentiel canonique « Les deux » : réseau Huawei ('sans'), hybride
// Deye ('avec'), Smart Meter + Wifi Dongle insérés par `autoFillLines` (QF8)
// — communs (`variante: ''`) puisque les deux compositions fusionnées voient
// chacune le réseau Huawei et posent donc la même quantité des deux côtés
// (mécanisme d'atteignabilité décrit par la tâche : `autoFillLines:2043-2047`
// raisonne sur le devis entier, jamais panier par panier).
const DEVIS_CANONIQUE = [
  { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000, variante: 'sans' },
  { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000, variante: 'avec' },
  { designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 17000, variante: 'avec' },
  { designation: 'Panneau Canadien Solar 710W', quantite: 10, prix_unit_ttc: 1400, variante: 'sans' },
  { designation: 'Panneau Canadien Solar 710W', quantite: 17, prix_unit_ttc: 1400, variante: 'avec' },
  { designation: 'Smart Meter', quantite: 1, prix_unit_ttc: 1800, variante: '' },
  { designation: 'Wifi Dongle', quantite: 1, prix_unit_ttc: 1200, variante: '' },
]

test('optionTotalsTTC : QF9 — chaque option rend le total que le noyau rend pour la même option', () => {
  const lignesSans = DEVIS_CANONIQUE.filter(appartientAuPanierSans)
  const lignesAvec = DEVIS_CANONIQUE.filter(appartientAuPanierAvec)
  const attenduSans = totalAttenduPourPanier(lignesSans)
  const attenduAvec = totalAttenduPourPanier(lignesAvec)

  const { totalSansBrut, totalAvecBrut } = optionTotalsTTC(DEVIS_CANONIQUE, 0)
  assert.equal(totalSansBrut, attenduSans)
  assert.equal(totalAvecBrut, attenduAvec)
  // Le panier « avec » (Deye, pas Huawei) ne compte NI le Smart Meter NI la
  // clé Wi-Fi : sans ce correctif il les comptait (28000+17000+17*1400+3000).
  const L = DEVIS_CANONIQUE
  assert.equal(totalAvecBrut, canon(L[1], L[2], L[4]))
  // Le panier « sans » (Huawei) les garde, lui, intégralement.
  assert.equal(totalSansBrut, canon(L[0], L[3], L[5], L[6]))
})

test('optionTotalsTTC : QF9 — panier « sans » à onduleur Huawei, inchangé (F14/QJR300 non régressés)', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000, variante: '' },
    { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000, variante: '' },
    { designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 17000, variante: '' },
    { designation: 'Panneau Canadien Solar 710W', quantite: 10, prix_unit_ttc: 1400, variante: 'sans' },
    { designation: 'Panneau Canadien Solar 710W', quantite: 17, prix_unit_ttc: 1400, variante: 'avec' },
    { designation: 'Transport', quantite: 1, prix_unit_ttc: 1000, variante: '' },
  ]
  const { totalSans, totalAvec } = optionTotalsTTC(lignes, 0)
  // Non-régression QJR300 (déjà verrouillée par solar.deuxOptimiseurs.test.mjs) :
  // aucune ligne Huawei-only ici, la répartition reste celle d'avant.
  assert.equal(totalSans, canon(lignes[0], lignes[3], lignes[5]))
  assert.equal(totalAvec, canon(lignes[1], lignes[2], lignes[4], lignes[5]))
})

// ── Arrondi au centime, jamais au dirham entier, jamais conditionnel ────────

test('optionTotalsTTC : l’arrondi au centime ne dépend plus de la présence d’une remise', () => {
  const lignes = [{ designation: 'Transport', quantite: 1, prix_unit_ttc: 1000.5 }]
  const sansRemise = optionTotalsTTC(lignes, 0)
  const avecRemise = optionTotalsTTC(lignes, 10)
  // Sans remise : déjà au centime aujourd'hui (comportement historique).
  // ARRONDI-100 : 1 000,5 → palier de 100 inférieur (le centime reste porté
  // par le noyau sans palier, vérifié juste dessous).
  assert.equal(sansRemise.totalSans, 1000)
  assert.equal(totauxCanoniquesTtc(lignes, 0), 1000.5)
  // Avec remise : AVANT ce correctif, `Math.round(1000.5 × 0.9)` rendait 900
  // (l'entier), perdant les 0,45 MAD qui restent dans la liste/le PDF/la
  // facture (au centime). ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER : la valeur
  // est celle de la chaîne canonique (HT 833,75 ; remise 83,38 ; HT net
  // 750,37 ; TVA 150,07) → 900,44, le chiffre facturé.
  // ARRONDI-100 : 900,44 → palier de 100 inférieur ; le noyau SANS palier
  // garde la chaîne au centime (900,44), preuve que rien n'est arrondi au
  // dirham avant le palier.
  assert.equal(avecRemise.totalSans, 900)
  assert.equal(totauxCanoniquesTtc(lignes, 10), 900.44)
})

// ARRONDI-100 : « inchangé » = même population de lignes et même chaîne ; le
// total est désormais au palier de 100 MAD (le noyau de référence aussi).
test('optionTotalsTTC : un devis mono-option (aucune remise) reste inchangé à l’octet', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000 },
    { designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unit_ttc: 1400 },
    { designation: 'Smart Meter', quantite: 1, prix_unit_ttc: 1800 },
  ]
  const { totalSans, totalSansBrut } = optionTotalsTTC(lignes, 0)
  assert.equal(totalSansBrut, canon(...lignes))
  assert.equal(totalSans, totalSansBrut)
})

// ── QJR300 — devis SANS alternative déclarée (aucune ligne `variante`) :
// QF9 ne s'applique pas, comportement historique strictement inchangé, même
// quand le devis porte réseau ET hybride ET un accessoire Huawei-only
// (l'artefact « deux onduleurs non déclarés » du noyau, PV86). ────────────

test('optionTotalsTTC : sans aucune ligne variantée, QF9 ne s’applique pas (comportement historique)', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000 },
    { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000 },
    { designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 17000 },
    { designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unit_ttc: 1400 },
    { designation: 'Smart Meter', quantite: 1, prix_unit_ttc: 1800 },
    { designation: 'Wifi Dongle', quantite: 1, prix_unit_ttc: 1200 },
  ]
  const { totalSansBrut, totalAvecBrut } = optionTotalsTTC(lignes, 0)
  // Aucune alternative déclarée : le panier « avec » (mots-clés seuls)
  // continue de compter Smart Meter + Wifi Dongle, exactement comme avant ce
  // correctif — QF9 (QJR300) ne joue que sur un vrai devis à deux options.
  assert.equal(totalSansBrut, canon(lignes[0], lignes[3], lignes[4], lignes[5]))
  assert.equal(totalAvecBrut, canon(lignes[1], lignes[2], lignes[3], lignes[4], lignes[5]))
})

// QJR567 — le total du rail suit la MÊME population que le noyau
// (`selectors.ligne_compte_dans_totaux`) : une ligne optionnelle (add-on non
// activé) et les sections/notes n'entrent jamais dans totalSans / totalAvec.
test('QJR567 — une ligne optionnelle ou de section/note ne compte pas dans les totaux', () => {
  const normale = { produit: '1', designation: 'Panneau 550W', quantite: '10', prix_unit_ttc: '1100', taux_tva: 10 }
  const seule = optionTotalsTTC([normale], 0)
  assert.equal(seule.totalSans, 11000)
  const avecOptionnelle = optionTotalsTTC([
    normale,
    { produit: '2', designation: 'Borne de recharge', quantite: '1', prix_unit_ttc: '1200', taux_tva: 20, optionnelle: true },
    { designation: 'Toiture est', quantite: '1', prix_unit_ttc: '500', typeLigne: 'section' },
    { designation: 'Pose en deux temps', quantite: '1', prix_unit_ttc: '300', typeLigne: 'note' },
  ], 0)
  assert.equal(avecOptionnelle.totalSans, seule.totalSans)
  assert.equal(avecOptionnelle.totalAvec, seule.totalAvec)
  assert.equal(avecOptionnelle.totalSansBrut, seule.totalSansBrut)
})
