// ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — le chemin RÉEL qui atteignait le repli
// `computeROI` sans productible (GHI × 0,8 ≈ 1 256 kWh/kWc) était le balayage
// `optimalKwcByPayback` de l'écran et du devis automatique : ils passent
// désormais le productible de la ville, comme l'aperçu (`roi`) et le PDF
// (`pricing.calculate_savings_roi` : 1 651 × 0,93 ≈ 1 536 kWh/kWc).
// Le câblage des deux balayages est EXÉCUTÉ (QJR239, aucune lecture de
// source) par `autoQuote.balayageCI.test.jsx` et
// `pages/ventes/DevisGeneratorBalayageProductible.test.jsx`.
// Run : node --test src/features/ventes/solar.balayageProductible.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { computeROI, productibleForCity } from './solar.js'

test('avec le productible de la ville, la production est celle du PDF (kWc 22,56 → 34 648 kWh)', () => {
  const roi = computeROI({
    kwp: 22.56, factures: Array(12).fill(2000), dayUsagePct: 60,
    totalSans: 200000, totalAvec: 260000, batteryKwh: 0,
    productible: productibleForCity('', null),
  })
  // calculate_savings_roi(22.56, …)['prod_kwh'] = 34 648 (Python, arrondi à l'entier).
  assert.ok(Math.abs(roi.production_annuelle_kwh - 34648) <= 0.5, String(roi.production_annuelle_kwh))
})
