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
  PRODUCTIBLE_NET_FACTOR, SYSTEM_LOSS_TOTAL,
} from './solar.js'

// ── Fixture MIROIR (identique côté Python) ───────────────────────────────────
// 10 kWc à Casablanca : productible stocké 1651 (PVGIS, déjà net de 14 %)
// ramené aux 20 % de pertes TOTALES du fondateur → 1651 × 0,9302 = 1 535,81,
// soit 15 358 kWh/an pour 10 kWc. Batterie 10 kWh ; conso réelle 15 000 kWh/an ;
// barème ONEE.
const PROD = 15358
const BATTERY = 10
const CONSO = 15000

test('taux avec batterie DÉRIVÉ : 60 % + capacité × 1 cycle/jour', () => {
  // À la main : 10 kWh × 365 j = 3 650 kWh/an décalés ;
  // 3 650 / 15 358 = 0,237661154... → 0,60 + 0,237661... = 0,837661154...
  const ratio = autoconsoAvecRatio(PROD, BATTERY)
  assert.equal(Math.abs(ratio - 0.8376611538) < 1e-9, true,
    `ratio dérivé attendu ≈ 0.8376611538, obtenu ${ratio}`)
  // Formule fermée (même expression que pricing.autoconso_avec_ratio)
  assert.equal(ratio, AUTOCONSO_SANS + (BATTERY * DAYS_PER_YEAR) / PROD)
  // En kWh : 9 214,8 (60 %) + 3 650 (batterie) = 12 864,8 → 12 865 kWh.
  assert.equal(Math.round(ratio * PROD), 12865)
})

test('plafond production : la batterie ne décale que l\'énergie qui existe', () => {
  // 30 kWh × 365 = 10 950 kWh > 40 % de 15 358 (6 143) → taux plafonné à 1.
  assert.equal(autoconsoAvecRatio(PROD, 30), 1)
})

test('plafond consommation : jamais plus que ce que le client consomme', () => {
  // conso 9 000 kWh/an sur 15 358 produits → 9 000/15 358 = 0,586014...
  const ratio = autoconsoAvecRatio(PROD, BATTERY, { consoAnnuelleKwh: 9000 })
  assert.equal(ratio, 9000 / PROD)
  assert.equal(ratio < 0.8376611538, true)
})

test('capacité inconnue : repli documenté sur l\'ancien forfait 85 %', () => {
  assert.equal(autoconsoAvecRatio(PROD, 0), AUTOCONSO_AVEC)
  assert.equal(autoconsoAvecRatio(PROD, null), AUTOCONSO_AVEC)
  // production inconnue → repli aussi (aucun chiffre inventé)
  assert.equal(autoconsoAvecRatio(0, BATTERY), AUTOCONSO_AVEC)
})

// ── VERROU DE DÉRIVE JS ↔ Python ─────────────────────────────────────────────
// Valeurs dérivées À LA MAIN du barème ONEE SÉLECTIF (progressif ≤ 150 : 0,9010
// puis 1,0732 ; sélectif au-delà — TOUTE la conso au tarif de sa tranche :
// 151-210 = 1,0732 · 211-310 = 1,1676 · 311-510 = 1,3817 · > 510 = 1,5958) — le
// jumeau Python (test_battery_autoconso.py, test_miroir_js_meme_fixture_memes_
// chiffres) attend EXACTEMENT les mêmes.
//
//  facture sans solaire  : 15 000/12 = 1 250 kWh/mois → > 510
//      1 250 × 1,5958 = 1 994,75 MAD/mois × 12 = 23 937 MAD/an
//  option SANS (60 %)    : autoconsommé 9 214,8 → résiduel 5 785,2
//      → 482,1 kWh/mois → bande 311-510 : 482,1 × 1,3817 = 666,11757
//      × 12 = 7 993,41 → 7 993
//      ⇒ économie 23 937 − 7 993 = 15 944 MAD/an
//  option AVEC (83,8 %)  : autoconsommé 12 864,8 → résiduel 2 135,2
//      → 177,9333 kWh/mois → bande 151-210 : 177,9333 × 1,0732 = 190,95805
//      × 12 = 2 291,50 → 2 291
//      ⇒ économie 23 937 − 2 291 = 21 646 MAD/an
//  (la batterie fait franchir DEUX marches vers le bas : 1,3817 → 1,0732 sur la
//   totalité du résiduel — c'est là que le modèle sélectif change tout.)
test('MIROIR Python — mêmes entrées, mêmes factures et mêmes économies', () => {
  const sans = twoBillsSavings(PROD, CONSO, AUTOCONSO_SANS, 'onee')
  const avec = twoBillsSavings(PROD, CONSO, autoconsoAvecRatio(PROD, BATTERY), 'onee')
  assert.equal(sans.factureSans, 23937)
  assert.equal(sans.factureAvec, 7993)
  assert.equal(sans.economie, 15944)
  assert.equal(avec.autoconsoKwh, 12865)
  assert.equal(avec.factureAvec, 2291)
  assert.equal(avec.economie, 21646)
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
  // 10 kWc × 1651 × 0,9302325581 = 15 358,14 → 15 358 kWh/an (mêmes 20 % de
  // pertes totales que le PDF : test_battery_autoconso.py attend le même 15 358)
  assert.equal(Math.round(roi.production_annuelle_kwh), PROD)
  assert.equal(roi.autoconso_sans, AUTOCONSO_SANS)
  // Le taux est dérivé sur la production ARRONDIE (15 358), exactement comme
  // le PDF : à l'écran comme sur le document, 0,60 + 3 650/15 358.
  assert.equal(Math.abs(roi.autoconso_avec - 0.8376611538) < 1e-9, true)
  assert.equal(roi.autoconso_avec, autoconsoAvecRatio(PROD, BATTERY))
  assert.equal(roi.eco_annuelle_sans, 15944)
  assert.equal(roi.eco_annuelle_avec, 21646)
  assert.notEqual(roi.autoconso_avec, AUTOCONSO_AVEC)
})

// ── Pertes système : 20 % AU TOTAL (ordre fondateur 18/08) ───────────────────
test('20 % de pertes TOTALES : le productible stocké (net 14 %) est ramené au net 20 %', () => {
  // (1 − 0,20)/(1 − 0,14) = 0,80/0,86 = 0,9302325581395349 — on n'applique que
  // le COMPLÉMENT, sinon les 14 % déjà dans le productible PVGIS compteraient
  // deux fois (l'ancien 0,86 faisait 26 % cumulés).
  assert.equal(SYSTEM_LOSS_TOTAL, 0.20)
  assert.equal(PRODUCTIBLE_NET_FACTOR, 0.8 / 0.86)
  assert.equal(Math.abs(PRODUCTIBLE_NET_FACTOR - 0.9302325581395349) < 1e-15, true)
  // 10 kWc Casablanca : 16 510 kWh bruts (net 14 %) → 15 358 kWh (net 20 %).
  const roi = computeROI({
    kwp: 10, productible: 1651, factures: Array(12).fill(1500),
    dayUsagePct: 60, totalSans: 100000, totalAvec: 140000, batteryKwh: 0,
  })
  assert.equal(Math.round(roi.production_annuelle_kwh), 15358)
  assert.equal(Math.round(16510 * PRODUCTIBLE_NET_FACTOR), 15358)
})

test('computeROI (estimation) : la batterie apporte des kWh, plus un forfait MAD', () => {
  const PRICE = 1.75
  const roi = computeROI({
    kwp: 10, productible: 1651, factures: Array(12).fill(1500),
    dayUsagePct: 60, totalSans: 100000, totalAvec: 140000, batteryKwh: BATTERY,
  })
  assert.equal(roi.savings_model, 'estimation')
  // Production EXACTE (non arrondie) telle que computeROI la calcule.
  const PROD_EXACT = 10 * 1651 * PRODUCTIBLE_NET_FACTOR
  const GHI_SUM = GHI.reduce((s, v) => s + v, 0)
  let shiftAttendu = 0
  for (let i = 0; i < 12; i++) {
    const prod = PROD_EXACT * (GHI[i] / GHI_SUM)
    const shift = Math.min(BATTERY * DAYS_IN_MONTH[i], prod * 0.4) // 100 % − 60 %
    shiftAttendu += shift
    // Chaque mois : écart avec/sans = kWh décalés × tarif.
    assert.equal(
      Math.abs(roi.eco_avec_monthly[i] - roi.eco_sans_monthly[i] - shift * PRICE) < 1e-6,
      true, `mois ${i + 1} : apport batterie ≠ kWh décalés × tarif`)
  }
  // Avec les 20 % de pertes totales, DÉCEMBRE devient plafonné : production
  // 15 358 × 74,61/1 570,28 = 729,7 kWh, surplus 40 % = 291,9 kWh alors que la
  // batterie pourrait décaler 10 × 31 = 310 kWh. L'apport annuel n'est donc
  // plus 3 650 kWh mais 3 650 − 18,1 = 3 631,9 → 3 632 kWh (honnête : on ne
  // stocke pas une énergie qui n'existe pas en hiver).
  assert.equal(Math.round(shiftAttendu), 3632)
  assert.equal(roi.battery_shift_kwh, 3632)
  assert.equal(roi.battery_shift_kwh < BATTERY * DAYS_PER_YEAR, true)
})

test('petite installation, grosse batterie : l\'apport est plafonné par la production', () => {
  // 3 kWc → 3 × 1651 × 0,9302 = 4 607 kWh/an (net 20 %). Avec 20 kWh de
  // batterie : 20 × 365 = 7 300 kWh « décalables » — impossible, il n'existe
  // que 40 % × 4 607 = 1 843 kWh de surplus. Le modèle ne dépasse JAMAIS la
  // production.
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
