// AGNR25 — le chemin « estimation » de `computeROI` (sans conso) calcule
// l'apport batterie sur l'ANNÉE par `autoconsoAvecRatio`, comme
// `calculate_savings_roi` : production arrondie × taux × tarif.
//
// Valeurs serveur figées (sonde V_VA p6 de l'audit C-AGNR-017) : 5 kWc,
// production nette 7 679 kWh, part diurne 60 %, tarif 1,75, batteries
// 2,5 / 5 / 7,5 / 10 kWh ⇒ 9 660 / 11 257 / 12 854 / 13 438 MAD/an « avec ».
// La production 7 679 kWh est reproduite à l'écran par le productible
// 1 651 kWh/kWc (× PRODUCTIBLE_NET_FACTOR × 5 kWc).
//
// Run : node --test src/features/ventes/solar.agnrBatterieEstimation.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { computeROI } from './solar.js'

const base = {
  kwp: 5, factures: Array(12).fill(800), dayUsagePct: 60, totalSans: 50000, totalAvec: 90000,
  kwhPrice: 1.75, productible: 1651,
}

for (const [batteryKwh, attendu] of [[2.5, 9660], [5, 11257], [7.5, 12854], [10, 13438]]) {
  test(`AGNR25 — batterie ${batteryKwh} kWh ⇒ ${attendu} MAD/an « avec batterie »`, () => {
    const r = computeROI({ ...base, batteryKwh })
    assert.equal(r.savings_model, 'estimation')
    assert.equal(Math.round(r.production_annuelle_kwh), 7679)
    assert.equal(Math.round(r.eco_annuelle_avec), attendu)
    // Σ de la série mensuelle « avec » = l'annuel.
    const somme = r.monthly_detail.reduce((s, m) => s + m.eco_avec, 0)
    assert.ok(Math.abs(somme - r.eco_annuelle_avec) < 0.01)
  })
}
