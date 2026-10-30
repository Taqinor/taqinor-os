// SPL210 — tests de calc/totaux.js déplacés tel quel de solar.test.mjs (move
// only : aucune assertion modifiée).
//
// Run : node --test src/features/ventes/calc/totaux.test.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  optionTotalsTTC, prixParKwc, discountForTarget, computeBuyCost, multiPropertyPreviewTTC,
  totauxCanoniquesTtc,
} from './totaux.js'
import { PAS_ARRONDI_DEVIS } from '../remise.js'

test('remise saisie librement (ex. 12.5 %) : appliquée exactement', () => {
  const lines = [{ designation: 'Transport', quantite: '1', prix_unit_ttc: '1000' }]
  const { totalSans } = optionTotalsTTC(lines, '12.5')
  // ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — chaîne canonique du noyau : HT
  // persisté 833,33 ; remise 104,17 ; HT net 729,16 ; TVA 145,83 → 874,99
  // (le chiffre facturé ; l'ancien « 1000 × 0,875 = 875 » ne l'était pas).
  // ARRONDI-100 : 874,99 → palier de 100 inférieur.
  assert.equal(totalSans, 800)
})

test('prix/kWc + prix cible appliqué via remise transparente', () => {
  assert.equal(prixParKwc(99400, 9.94), 10000)
  // cible 9 000 MAD/kWc sur un brut de 99 400 → remise ≈ 9.96 %
  const pct = discountForTarget(9000, 9.94, 99400)
  assert.ok(Math.abs(pct - (1 - 9000 * 9.94 / 99400) * 100) < 0.01)
  // le total remisé atteint la cible (à l'arrondi près)
  const totalApres = 99400 * (1 - pct / 100)
  assert.ok(Math.abs(totalApres - 9000 * 9.94) < 1)
})

test('marge : affichée seulement quand des prix d\'achat existent', () => {
  const produits = [
    { id: 1, nom: 'Panneau X', prix_vente: '1166.67', prix_achat: '0' },
    { id: 2, nom: 'Onduleur Y', prix_vente: '16666.67', prix_achat: '0' },
  ]
  const lines = [
    { produit: '1', designation: 'Panneau X', quantite: '10', prix_unit_ttc: '1400' },
    { produit: '2', designation: 'Onduleur Y', quantite: '1', prix_unit_ttc: '20000' },
  ]
  // aucun prix d'achat → null (rien à afficher)
  assert.equal(computeBuyCost(lines, produits), null)
  // un prix d'achat renseigné → coût TTC de cette ligne
  produits[0].prix_achat = '1000'
  assert.equal(computeBuyCost(lines, produits), Math.round(10 * 1000 * 1.2))
})

// QJR567 — le coût d'achat (marge du générateur) suit la MÊME population que
// les totaux : ni ligne optionnelle (add-on non activé), ni section/note.
test('QJR567 computeBuyCost ignore une ligne optionnelle et les sections/notes', () => {
  const produits = [
    { id: 1, nom: 'Panneau X', prix_vente: '1000', prix_achat: '800' },
    { id: 3, nom: 'Borne de recharge', prix_vente: '5000', prix_achat: '4000' },
  ]
  const normale = { produit: '1', designation: 'Panneau X', quantite: '10', prix_unit_ttc: '1100' }
  const lines = [
    normale,
    { produit: '3', designation: 'Borne de recharge', quantite: '1', prix_unit_ttc: '6000', optionnelle: true },
    { produit: '1', designation: 'Section toiture', quantite: '1', prix_unit_ttc: '0', typeLigne: 'section' },
    { produit: '1', designation: 'Note', quantite: '1', prix_unit_ttc: '0', typeLigne: 'note' },
  ]
  assert.equal(computeBuyCost(lines, produits), computeBuyCost([normale], produits))
})

// ── QJ31 — Multi-propriétés : aperçu écran (TTC) mode ×N et mode villas ──────
const L = (designation, qty, ttc, extra = {}) => ({
  designation, quantite: String(qty), prix_unit_ttc: String(ttc), ...extra,
})

test('QJ31 — sans mode multi (pas de N, pas de groupe) : preview = null (mono-système inchangé)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)]
  assert.equal(multiPropertyPreviewTTC(lines, {}), null)
  assert.equal(multiPropertyPreviewTTC(lines, { nombreProprietes: '1' }), null)
})

test('QJ31 mode A — ×N multiplie le total TTC (unitaire × N)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)] // 34000 TTC
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '3', discountPct: '0' })
  assert.equal(r.mode, 'multiplicateur')
  assert.equal(r.nombreProprietes, 3)
  // Chaîne canonique (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER) : 34 000,04, que
  // l'ARRONDI-100 ramène au palier de 100 MAD inférieur (noyau : même palier).
  assert.equal(r.totalUnitaireSans, totauxCanoniquesTtc(lines, 0, PAS_ARRONDI_DEVIS))
  assert.equal(r.totalUnitaireSans, 34000)
  // ERR-QAC-MULTIVILLA-TOTAL-XN — ×N au CENTIME (miroir backend) : unitaire × 3.
  // ARRONDI-100 : 102 000,12 → palier de 100 inférieur (unitaire arrondi AVANT le ×N).
  assert.equal(r.totalMultiSans, 102000)
})

test('QJ31 mode A — ×N applique aussi la remise (unitaire remisé × N)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)] // 34000 brut
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '2', discountPct: '10' })
  // Chaîne canonique (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER) : 30 600,04, que
  // l'ARRONDI-100 ramène au palier de 100 MAD inférieur (noyau : même palier).
  assert.equal(r.totalUnitaireSans, totauxCanoniquesTtc(lines, 10, PAS_ARRONDI_DEVIS))
  assert.equal(r.totalUnitaireSans, 30600)
  // ERR-QAC-MULTIVILLA-TOTAL-XN — ×N au CENTIME : unitaire × 2.
  // ARRONDI-100 : 61 200,08 → palier de 100 inférieur (unitaire arrondi AVANT le ×N).
  assert.equal(r.totalMultiSans, 61200)
})

test('QJ31 mode B — groupes villas : sous-total par villa + total général', () => {
  const lines = [
    L('Installation commune', 1, 6000, { groupeIndex: 0, groupeLabel: 'Équipement commun' }),
    L('Onduleur réseau', 1, 20000, { groupeIndex: 1, groupeLabel: 'Villa A' }),
    L('Panneaux', 10, 1400, { groupeIndex: 1, groupeLabel: 'Villa A' }), // 14000
    L('Onduleur réseau', 1, 11000, { groupeIndex: 2, groupeLabel: 'Villa B' }),
    L('Panneaux', 8, 1400, { groupeIndex: 2, groupeLabel: 'Villa B' }), // 11200
  ]
  const r = multiPropertyPreviewTTC(lines, {})
  assert.equal(r.mode, 'villas')
  assert.deepEqual(r.groupes.map(g => g.label), ['Équipement commun', 'Villa A', 'Villa B'])
  // ATOT24 — chaque villa = chaîne canonique de SES lignes (HT persisté au
  // centime → TVA → TTC, comme `multi_villa_totaux`) ; total général = chaîne
  // canonique de toutes les lignes au palier ARRONDI-100.
  assert.equal(r.groupes[0].totalTtc, 6000)
  assert.equal(r.groupes[1].totalTtc, totauxCanoniquesTtc(lines.slice(1, 3), 0, 0)) // ≈ 20000 + 14000
  assert.equal(r.groupes[2].totalTtc, totauxCanoniquesTtc(lines.slice(3), 0, 0)) // ≈ 11000 + 11200
  assert.equal(r.grandTotalTtc, totauxCanoniquesTtc(lines, 0, PAS_ARRONDI_DEVIS))
  assert.equal(r.grandTotalTtc, 62200)
})

test('QJ31 mode B — libellé par défaut quand groupeLabel vide (Villa N / Équipement commun)', () => {
  const lines = [
    L('X', 1, 1000, { groupeIndex: 0, groupeLabel: '' }),
    L('Y', 1, 2000, { groupeIndex: 1, groupeLabel: '' }),
  ]
  const r = multiPropertyPreviewTTC(lines, {})
  assert.equal(r.groupes[0].label, 'Équipement commun')
  assert.equal(r.groupes[1].label, 'Villa 1')
})

test('QJ31 — le multiplicateur (>1) prime sur les groupes si les deux sont présents', () => {
  // À l'écran les deux modes sont exclusifs ; par sécurité, N>1 gagne.
  const lines = [L('X', 1, 1000, { groupeIndex: 1, groupeLabel: 'Villa 1' })]
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '4' })
  assert.equal(r.mode, 'multiplicateur')
})

// QJR529 — la remise PAR LIGNE stockée (LigneDevis.remise) compte dans le
// même calcul que les totaux canoniques, comme `total_ht` = q × pu × (1 − remise/100)
// côté serveur : sinon l'écran ≠ le PDF.
test('QJR529 — totauxCanoniquesTtc applique la remise de ligne', () => {
  assert.equal(totauxCanoniquesTtc(
    [{ quantite: '1', prix_unit_ttc: '1200', taux_tva: 20, remise: '10' }], 0), 1080)
  // Remise absente / nulle : strictement inchangé.
  assert.equal(totauxCanoniquesTtc(
    [{ quantite: '1', prix_unit_ttc: '1200', taux_tva: 20 }], 0), 1200)
  // Taux mixtes + remise globale : la remise de ligne s'applique AVANT.
  // HT : 2 × 1000 × 0,5 = 1000 (10 %) + 1000 (20 %) → brut 2000, remise
  // globale 10 % → 1800 ; TVA 900 × 10 % + 900 × 20 % = 270 → 2070.
  assert.equal(totauxCanoniquesTtc([
    { quantite: '2', prix_unit_ttc: '1100', taux_tva: 10, remise: '50' },
    { quantite: '1', prix_unit_ttc: '1200', taux_tva: 20 },
  ], 10), 2070)
})

test('ERR-QJR576 — SCENARIOS_ALTERNATIVE est la liste unique de quote/scenarios.js (SCENARIOS_VALIDES)', async () => {
  const { SCENARIOS_ALTERNATIVE } = await import('./totaux.js')
  const { SCENARIOS_VALIDES } = await import('../quote/sizingReducer.js')
  assert.equal(SCENARIOS_ALTERNATIVE, SCENARIOS_VALIDES)
  assert.deepEqual([...SCENARIOS_ALTERNATIVE].sort(),
    ['Avec batterie', 'Les deux (Sans + Avec)', 'Sans batterie'])
})
