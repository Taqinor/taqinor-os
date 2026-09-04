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
  isAnyInverter, isSmartMeter, isWifiDongle,
} from './solar.js'

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
  return rows.reduce(
    (s, l) => s + (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0), 0)
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
  assert.equal(totalAvecBrut, 28000 + 17000 + 17 * 1400)
  // Le panier « sans » (Huawei) les garde, lui, intégralement.
  assert.equal(totalSansBrut, 20000 + 10 * 1400 + 1800 + 1200)
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
  assert.equal(totalSans, 20000 + 10 * 1400 + 1000)
  assert.equal(totalAvec, 28000 + 17000 + 17 * 1400 + 1000)
})

// ── Arrondi au centime, jamais au dirham entier, jamais conditionnel ────────

test('optionTotalsTTC : l’arrondi au centime ne dépend plus de la présence d’une remise', () => {
  const lignes = [{ designation: 'Transport', quantite: 1, prix_unit_ttc: 1000.5 }]
  const sansRemise = optionTotalsTTC(lignes, 0)
  const avecRemise = optionTotalsTTC(lignes, 10)
  // Sans remise : déjà au centime aujourd'hui (comportement historique).
  assert.equal(sansRemise.totalSans, 1000.5)
  // Avec remise : AVANT ce correctif, `Math.round(1000.5 × 0.9)` rendait 900
  // (l'entier), perdant les 0,45 MAD qui restent dans la liste/le PDF/la
  // facture (au centime). Le correctif garde ces 0,45 MAD : 900,45.
  assert.equal(avecRemise.totalSans, 900.45)
})

test('optionTotalsTTC : un devis mono-option (aucune remise) reste inchangé à l’octet', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000 },
    { designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unit_ttc: 1400 },
    { designation: 'Smart Meter', quantite: 1, prix_unit_ttc: 1800 },
  ]
  const { totalSans, totalSansBrut } = optionTotalsTTC(lignes, 0)
  assert.equal(totalSansBrut, 20000 + 14 * 1400 + 1800)
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
  assert.equal(totalSansBrut, 20000 + 14 * 1400 + 1800 + 1200)
  assert.equal(totalAvecBrut, 28000 + 17000 + 14 * 1400 + 1800 + 1200)
})
