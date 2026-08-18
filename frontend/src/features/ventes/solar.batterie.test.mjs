// ORDRE FONDATEUR (18/08) — modèle d'économies « avec batterie » ADDITIF.
//
//   sans batterie : autoconsommé = 60 % × production
//   avec batterie : autoconsommé = 60 % × production + capacité_kWh × 1 cycle/jour
//   plafonds      : jamais plus que la production ; jamais plus que la
//                   consommation réelle quand elle est connue.
//
// Le forfait « 85 % avec batterie » ne survit QUE comme repli documenté
// (capacité inconnue). Ce fichier est le VERROU DE DÉRIVE avec son jumeau
// Python backend/django_core/apps/ventes/tests/test_battery_autoconso.py :
// mêmes entrées, mêmes valeurs attendues, DÉRIVÉES À LA MAIN des deux côtés.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  autoconsoAvecRatio, twoBillsSavings, computeROI, batteryKwhFromLines,
  AUTOCONSO_SANS, AUTOCONSO_AVEC, DAYS_PER_YEAR, DAYS_IN_MONTH, GHI,
} from './solar.js'

// ── Fixture MIROIR (identique côté Python) ───────────────────────────────────
// 10 kWc, productible PVGIS 1651 → 16 510 kWh/an ; batterie 10 kWh ;
// consommation réelle 15 000 kWh/an ; barème ONEE.
const PROD = 16510
const BATTERY = 10
const CONSO = 15000

test('taux avec batterie DÉRIVÉ : 60 % + capacité × 1 cycle/jour', () => {
  // À la main : 10 kWh × 365 j = 3 650 kWh/an décalés ;
  // 3 650 / 16 510 = 0,221078134... → 0,60 + 0,221078... = 0,821078134...
  const ratio = autoconsoAvecRatio(PROD, BATTERY)
  assert.equal(Math.abs(ratio - 0.8210781344639613) < 1e-12, true,
    `ratio dérivé attendu 0.8210781344639613, obtenu ${ratio}`)
  // Formule fermée (même expression que pricing.autoconso_avec_ratio)
  assert.equal(ratio, AUTOCONSO_SANS + (BATTERY * DAYS_PER_YEAR) / PROD)
  // En kWh : 9 906 (60 %) + 3 650 (batterie) = 13 556 kWh autoconsommés.
  assert.equal(Math.round(ratio * PROD), 13556)
})

test('plafond production : la batterie ne décale que l\'énergie qui existe', () => {
  // 30 kWh × 365 = 10 950 kWh > 40 % de 16 510 (6 604) → taux plafonné à 1.
  assert.equal(autoconsoAvecRatio(PROD, 30), 1)
})

test('plafond consommation : jamais plus que ce que le client consomme', () => {
  // conso 9 000 kWh/an sur 16 510 produits → 9 000/16 510 = 0,545124...
  const ratio = autoconsoAvecRatio(PROD, BATTERY, { consoAnnuelleKwh: 9000 })
  assert.equal(ratio, 9000 / PROD)
  assert.equal(ratio < 0.8210781344639613, true)
})

test('capacité inconnue : repli documenté sur l\'ancien forfait 85 %', () => {
  assert.equal(autoconsoAvecRatio(PROD, 0), AUTOCONSO_AVEC)
  assert.equal(autoconsoAvecRatio(PROD, null), AUTOCONSO_AVEC)
  // production inconnue → repli aussi (aucun chiffre inventé)
  assert.equal(autoconsoAvecRatio(0, BATTERY), AUTOCONSO_AVEC)
})

// ── VERROU DE DÉRIVE JS ↔ Python ─────────────────────────────────────────────
// Valeurs dérivées À LA MAIN du barème ONEE [[100, 0.9010], [250, 1.0258],
// [400, 1.2515], [null, 1.4017]] — le jumeau Python (test_battery_autoconso.py,
// test_miroir_js_meme_fixture_memes_chiffres) attend EXACTEMENT les mêmes.
//
//  facture sans solaire  : 15 000/12 = 1 250 kWh/mois
//      100 × 0,9010 = 90,10 | 150 × 1,0258 = 153,87 | 150 × 1,2515 = 187,725
//      850 × 1,4017 = 1 191,445 → 1 623,14 MAD/mois × 12 = 19 477,68 → 19 478
//  option SANS (60 %)    : autoconsommé 9 906 → résiduel 5 094 → 424,5 kWh/mois
//      90,10 + 153,87 + 187,725 + 24,5 × 1,4017 (34,34165) = 466,03665
//      × 12 = 5 592,44 → 5 592  ⇒ économie 19 478 − 5 592 = 13 886 MAD/an
//  option AVEC (82,1 %)  : autoconsommé 13 556 → résiduel 1 444 → 120,333 kWh/mois
//      90,10 + 20,3333 × 1,0258 (20,857933) = 110,957933 × 12 = 1 331,50 → 1 331
//      ⇒ économie 19 478 − 1 331 = 18 147 MAD/an
test('MIROIR Python — mêmes entrées, mêmes factures et mêmes économies', () => {
  const sans = twoBillsSavings(PROD, CONSO, AUTOCONSO_SANS, 'onee')
  const avec = twoBillsSavings(PROD, CONSO, autoconsoAvecRatio(PROD, BATTERY), 'onee')
  assert.equal(sans.factureSans, 19478)
  assert.equal(sans.factureAvec, 5592)
  assert.equal(sans.economie, 13886)
  assert.equal(avec.autoconsoKwh, 13556)
  assert.equal(avec.factureAvec, 1331)
  assert.equal(avec.economie, 18147)
  // La batterie ajoute une économie RÉELLE, jamais négative.
  assert.equal(avec.economie > sans.economie, true)
})

// ── computeROI : les deux chemins portent le modèle du fondateur ─────────────
test('computeROI (modèle « deux factures ») : taux avec batterie dérivé, pas 85 %', () => {
  const roi = computeROI({
    kwp: 10, productible: 1651, factures: Array(12).fill(1500),
    dayUsagePct: 60, totalSans: 100000, totalAvec: 140000,
    batteryKwh: BATTERY, consoAnnuelleKwh: CONSO, utility: 'onee',
  })
  assert.equal(roi.savings_model, 'factures')
  assert.equal(Math.round(roi.production_annuelle_kwh), PROD)
  assert.equal(roi.autoconso_sans, AUTOCONSO_SANS)
  assert.equal(Math.abs(roi.autoconso_avec - 0.8210781344639613) < 1e-12, true)
  assert.equal(roi.eco_annuelle_sans, 13886)
  assert.equal(roi.eco_annuelle_avec, 18147)
  assert.notEqual(roi.autoconso_avec, AUTOCONSO_AVEC)
})

test('computeROI (estimation) : la batterie apporte des kWh, plus un forfait MAD', () => {
  const PRICE = 1.75
  const roi = computeROI({
    kwp: 10, productible: 1651, factures: Array(12).fill(1500),
    dayUsagePct: 60, totalSans: 100000, totalAvec: 140000, batteryKwh: BATTERY,
  })
  assert.equal(roi.savings_model, 'estimation')
  const GHI_SUM = GHI.reduce((s, v) => s + v, 0)
  let shiftAttendu = 0
  for (let i = 0; i < 12; i++) {
    const prod = PROD * (GHI[i] / GHI_SUM)
    const shift = Math.min(BATTERY * DAYS_IN_MONTH[i], prod * 0.4) // 100 % − 60 %
    shiftAttendu += shift
    // Chaque mois : écart avec/sans = kWh décalés × tarif.
    assert.equal(
      Math.abs(roi.eco_avec_monthly[i] - roi.eco_sans_monthly[i] - shift * PRICE) < 1e-6,
      true, `mois ${i + 1} : apport batterie ≠ kWh décalés × tarif`)
  }
  // Aucun mois plafonné pour 10 kWc / 10 kWh à 60 % de part diurne :
  // l'apport annuel vaut exactement 10 kWh × 365 j.
  assert.equal(Math.round(shiftAttendu), BATTERY * DAYS_PER_YEAR)
  assert.equal(roi.battery_shift_kwh, BATTERY * DAYS_PER_YEAR)
})

test('petite installation, grosse batterie : l\'apport est plafonné par la production', () => {
  // 3 kWc (4 953 kWh/an) avec 20 kWh de batterie : 20 × 365 = 7 300 kWh
  // « décalables » — impossible, il n'existe que 40 % × 4 953 = 1 981 kWh de
  // surplus. Le modèle ne peut donc JAMAIS dépasser la production.
  const roi = computeROI({
    kwp: 3, productible: 1651, factures: Array(12).fill(500),
    dayUsagePct: 60, totalSans: 40000, totalAvec: 60000, batteryKwh: 20,
  })
  assert.equal(roi.autoconso_avec <= 1, true)
  assert.equal(Math.abs(roi.autoconso_avec - 1) < 1e-9, true)
  assert.equal(roi.battery_shift_kwh, Math.round(roi.production_annuelle_kwh * 0.4))
})

test('capacité lue sur les VRAIES lignes batterie du devis', () => {
  const lignes = [
    { designation: 'Batterie Dyness 5 kWh', quantite: '2', prix_unit_ttc: '17000' },
    { designation: 'Panneau 710W', quantite: '14', prix_unit_ttc: '1400' },
  ]
  assert.equal(batteryKwhFromLines(lignes), 10)
  // …et ce sont ces 10 kWh qui pilotent le taux (pas un forfait).
  assert.equal(autoconsoAvecRatio(PROD, batteryKwhFromLines(lignes)),
    autoconsoAvecRatio(PROD, 10))
})
