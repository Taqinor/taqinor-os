// ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — le chemin RÉEL qui atteignait le repli
// `computeROI` sans productible (GHI × 0,8 ≈ 1 256 kWh/kWc) était le balayage
// `optimalKwcByPayback` de l'écran et du devis automatique : ils passent
// désormais le productible de la ville, comme l'aperçu (`roi`) et le PDF
// (`pricing.calculate_savings_roi` : 1 651 × 0,93 ≈ 1 536 kWh/kWc).
// Run : node --test src/features/ventes/solar.balayageProductible.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { computeROI, productibleForCity } from './solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))

test('avec le productible de la ville, la production est celle du PDF (kWc 22,56 → 34 648 kWh)', () => {
  const roi = computeROI({
    kwp: 22.56, factures: Array(12).fill(2000), dayUsagePct: 60,
    totalSans: 200000, totalAvec: 260000, batteryKwh: 0,
    productible: productibleForCity('', null),
  })
  // calculate_savings_roi(22.56, …)['prod_kwh'] = 34 648 (Python, arrondi à l'entier).
  assert.ok(Math.abs(roi.production_annuelle_kwh - 34648) <= 0.5, String(roi.production_annuelle_kwh))
})

test("les deux balayages passent le productible de la ville à optimalKwcByPayback", () => {
  const auto = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')
  const debut = auto.indexOf('const opt = optimalKwcByPayback({')
  assert.ok(debut > 0)
  const appel = auto.slice(debut, auto.indexOf('})', debut))
  assert.match(appel, /productible: productibleForCity\(lead\.ville \|\| '', quoteLogic\?\.productible\)/)

  const gen = readFileSync(join(HERE, '../../pages/ventes/DevisGenerator.jsx'), 'utf8')
  const d2 = gen.indexOf('const opt = optimalKwcByPayback({')
  assert.ok(d2 > 0)
  const appel2 = gen.slice(d2, gen.indexOf('})', d2))
  assert.match(appel2, /productible: productibleBalayage,/)
  assert.match(gen, /const productibleBalayage = productibleForCity\(\s*selectedLead\?\.ville \|\| '', quoteLogic\.productible\)/)
})
