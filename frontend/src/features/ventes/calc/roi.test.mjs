// SPL210 — tests de calc/roi.js déplacés tel quel de solar.test.mjs (move
// only : aucune assertion modifiée).
//
// Run : node --test src/features/ventes/calc/roi.test.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  computeROI, computeCashflowPayback, TARIFF_ESCALATION, BATTERY_ROUNDTRIP, INVERTER_REPLACE_YEAR,
} from './roi.js'

test('factures saisies librement : utilisées telles quelles dans la simulation', () => {
  const typed = [517, 433.5, 601, 380, 360, 502, 707, 681, 580, 480, 430, 480]
  const roi = computeROI({
    kwp: 5, factures: typed, dayUsagePct: 60,
    totalSans: 50000, totalAvec: 80000, batteryKwh: 5,
  })
  // Aucune retouche : le graphique reçoit exactement les montants saisis
  assert.deepEqual(roi.monthly_detail.map(d => d.facture), typed)
})

// ── QX39 — cashflow 25 ans honnête (miroir backend pricing.py) ──────────────
test('QX39 — computeCashflowPayback : croisement du cumul à zéro (parité backend)', () => {
  const cf = computeCashflowPayback(50000, 10000)
  assert.equal(cf.cumulative.length, 25)
  assert.ok(cf.paybackYears > 0 && cf.paybackYears < 25)
  assert.ok(cf.cumulative[0] < 0)                 // année 1 encore négatif
  assert.ok(cf.cumulative[cf.cumulative.length - 1] > 0) // rentabilisé à 25 ans
  assert.ok(cf.netGain > 0)
})

test('QX39 — projection à TARIF CONSTANT (miroir pricing.py TARIFF_ESCALATION=0)', () => {
  // ALIGNEMENT 18/08 — l'écran supposait +2 %/an alors que le PDF et la page
  // proposition écrivent « projection à tarif constant » : le modèle doit FAIRE
  // ce qu'il dit. Seule la dégradation panneau (0,5 %/an) érode les économies.
  assert.equal(TARIFF_ESCALATION, 0)
  const cf = computeCashflowPayback(50000, 10000)
  // Année 1 : cumul = −50 000 + 10 000 = −40 000 (aucune indexation).
  assert.equal(cf.cumulative[0], -40000)
  // Année 2 : économie × (1 − 0,005) = 9 950 → cumul −30 050.
  assert.equal(cf.cumulative[1], -30050)
})

test('QX39 — computeCashflowPayback : dégénéré → payback null', () => {
  assert.equal(computeCashflowPayback(0, 10000).paybackYears, null)
  assert.equal(computeCashflowPayback(50000, 0).paybackYears, null)
})

test('ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — drapeau jamaisRembourse (même règle que pricing)', () => {
  const jamais = computeCashflowPayback(269065, 3000)
  assert.equal(jamais.jamaisRembourse, true)
  assert.ok(jamais.cumulative[jamais.cumulative.length - 1] < 0)
  assert.equal(computeCashflowPayback(50000, 10000).jamaisRembourse, false)
  assert.equal(computeCashflowPayback(0, 10000).jamaisRembourse, false)
})

test('QX39 — batterie (rendement aller-retour) allonge le payback', () => {
  const no = computeCashflowPayback(50000, 10000)
  const bat = computeCashflowPayback(50000, 10000, { battery: true })
  assert.ok(bat.paybackYears >= no.paybackYears)
})

// ── Z5 (ORDRE FONDATEUR, 20/08/2026) — le rendement aller-retour batterie ne
// frappe QUE la part de l'économie qui transite RÉELLEMENT par elle, jamais
// 100 % (miroir pricing.py compute_cashflow_payback, batt_factor). ──────────
test('Z5 — batteryShare borne la perte aller-retour à la part réellement stockée', () => {
  // Investissement 50 000, économie année 1 = 10 000 MAD, moitié de
  // l'économie transite par la batterie (batteryShare = 0,5).
  //   batt_factor = 1 − (1 − 0,90) × 0,5 = 1 − 0,05 = 0,95
  //   Année 1 (dégradation/escalade = ×1 encore) :
  //     yearSaving = 10 000 × 0,95 = 9 500 → cumul = −50 000 + 9 500 = −40 500
  const half = computeCashflowPayback(50000, 10000, { battery: true, batteryShare: 0.5 })
  assert.equal(half.cumulative[0], -40500)

  // batteryShare = 0 : RIEN ne transite par la batterie (tout est autoconsommé
  // au fil du soleil) → aucune perte → IDENTIQUE au cashflow sans batterie.
  const zero = computeCashflowPayback(50000, 10000, { battery: true, batteryShare: 0 })
  const none = computeCashflowPayback(50000, 10000)
  assert.deepEqual(zero.cumulative, none.cumulative)

  // batteryShare = 1 (toute l'économie transite) et batteryShare = null/absent
  // (repli historique, appelant direct sans décomposition) sont IDENTIQUES au
  // forfait plein 0,90 sur 100 % — comportement inchangé pour ces appelants.
  const full = computeCashflowPayback(50000, 10000, { battery: true, batteryShare: 1 })
  const legacy = computeCashflowPayback(50000, 10000, { battery: true })
  assert.deepEqual(full.cumulative, legacy.cumulative)
  assert.equal(legacy.cumulative[0], -50000 + 10000 * BATTERY_ROUNDTRIP) // −41 000

  // AVANT Z5, batteryShare était ignoré : la part diurne directe (qui ne
  // traverse jamais la batterie) payait quand même 10 % de perte — une double
  // peine qui allongeait le payback « avec batterie ». Le payback à
  // batteryShare=0,5 doit désormais se situer STRICTEMENT ENTRE les deux bornes.
  assert.ok(half.paybackYears >= zero.paybackYears)
  assert.ok(half.paybackYears <= legacy.paybackYears)
})

// ── Q1 (ORDRE FONDATEUR, 20/08/2026) — la provision de remplacement onduleur
// (année 12) vaut le PRIX RÉEL de la ligne onduleur du devis, jamais un
// pourcentage forfaitaire de l'investissement (miroir pricing.py
// compute_cashflow_payback + builder.py _cout_onduleur). ─────────────────────
test('Q1 — computeCashflowPayback : la provision = prix RÉEL, jamais 8 % de l\'investissement', () => {
  const investment = 80000
  const economieAnnee1 = 12000
  const withoutProvision = computeCashflowPayback(investment, economieAnnee1)
  // Prix réel d'une ligne onduleur — délibérément DIFFÉRENT de l'ancien
  // forfait 8 % (0,08 × 80 000 = 6 400) pour prouver qu'il n'est plus utilisé.
  const realInverterPrice = 15300
  assert.notEqual(realInverterPrice, Math.round(investment * 0.08))
  const withProvision = computeCashflowPayback(investment, economieAnnee1, {
    inverterReplaceCost: realInverterPrice,
  })
  // Avant l'année de remplacement (12) : STRICTEMENT AUCUNE différence.
  for (let i = 0; i < INVERTER_REPLACE_YEAR - 1; i++) {
    assert.equal(withProvision.cumulative[i], withoutProvision.cumulative[i],
      `année ${i + 1} : la provision ne doit rien changer avant l'année ${INVERTER_REPLACE_YEAR}`)
  }
  // À l'année 12 (indice 11) et pour tout le reste de la projection : le cumul
  // « avec provision » est en retrait EXACTEMENT du prix réel de l'onduleur —
  // jamais un pourcentage (round(a) − round(a − k) = k pour k entier : la
  // preuve tient quelle que soit la valeur exacte du cumul non arrondi).
  for (let i = INVERTER_REPLACE_YEAR - 1; i < 25; i++) {
    assert.equal(
      withoutProvision.cumulative[i] - withProvision.cumulative[i],
      realInverterPrice,
      `année ${i + 1} : écart ≠ prix réel de l'onduleur`)
  }
  // Aucune ligne onduleur identifiable (inverterReplaceCost null/absent) :
  // AUCUNE provision — jamais un repli sur un pourcentage.
  const omitted = computeCashflowPayback(investment, economieAnnee1, { inverterReplaceCost: null })
  assert.deepEqual(omitted.cumulative, withoutProvision.cumulative)
})

// ── M9 (audit du 19/08/2026) — l'option « avec batterie » ne porte le
// rendement aller-retour QUE lorsqu'une VRAIE batterie est chiffrée sur le
// devis (dérivé de batteryKwhFromLines(lignes) > 0), jamais codé en dur. ─────
test('M9 — la présence de batterie vient des VRAIES lignes, jamais codée en dur', () => {
  const base = {
    kwp: 8, factures: Array(12).fill(1200), dayUsagePct: 60,
    totalSans: 90000, totalAvec: 90000, kwhPrice: 1.20,
  }
  // batteryKwh=0 (aucune vraie batterie) : le cashflow « avec » doit être
  // STRUCTURELLEMENT IDENTIQUE à un cashflow sans aucune perte de batterie —
  // avant M9, `battery: true` était codé en dur pour l'option 2 et infligeait
  // quand même 10 % de perte à un devis qui ne porte aucune batterie.
  const roiNoBattery = computeROI({ ...base, batteryKwh: 0 })
  const refNoBattery = computeCashflowPayback(base.totalAvec, roiNoBattery.eco_annuelle_avec)
  assert.deepEqual(roiNoBattery.cashflow_avec, refNoBattery.cumulative)
  assert.equal(roiNoBattery.payback_avec, refNoBattery.paybackYears)

  // Avec une VRAIE capacité (10 kWh) sur les mêmes entrées par ailleurs : la
  // perte aller-retour DOIT désormais s'appliquer — le cashflow diverge du
  // cashflow « sans aucune perte » calculé sur la MÊME économie avec batterie.
  const roiWithBattery = computeROI({ ...base, batteryKwh: 10 })
  const refWithBatteryNoLoss = computeCashflowPayback(
    base.totalAvec, roiWithBattery.eco_annuelle_avec)
  assert.notDeepEqual(roiWithBattery.cashflow_avec, refWithBatteryNoLoss.cumulative)
})

// ── QF5 — computeROI bascule sur le modèle « deux factures » (parité écran/PDF) ─
test('QF5 — computeROI : sans consommation réelle, comportement HISTORIQUE inchangé (estimation)', () => {
  const roi = computeROI({
    kwp: 5, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 80000, totalAvec: 100000, batteryKwh: 0,
  })
  assert.equal(roi.savings_model, 'estimation')
  assert.equal(roi.facture_sans, null)
})
