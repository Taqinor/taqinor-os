// QJR643 — le calculateur d'écran n'embarque plus de code mort : le hook
// `useComposition` (aucun appelant) et sa moitié pure sont partis, comme les
// exports de `solar.js` / `agronomy.js` qui ne servaient qu'à leurs tests ;
// les en-têtes « IMPORTÉ PAR PERSONNE » de modules réellement importés sont
// corrigés.
// Exécuté en CI : node --test src/features/ventes/quote/codeMortParcours.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import * as solar from '../solar.js'
import * as agronomy from '../agronomy.js'

const ICI = dirname(fileURLToPath(import.meta.url))

test('le hook useComposition et sa moitié pure n’existent plus', () => {
  assert.equal(existsSync(join(ICI, 'hooks', 'useComposition.js')), false)
  assert.equal(existsSync(join(ICI, 'hooks', 'useCompositionPur.js')), false)
})

test('solar.js n’exporte plus les fonctions sans appelant', () => {
  for (const nom of ['metreCableDc', 'APPROX_UTILITIES', 'onduleurComplet',
    'designationMatchesProduct', 'buildEtudeParamsChoice']) {
    assert.equal(nom in solar, false, `solar.${nom} est encore exporté`)
  }
  // Les survivants restent (aucun dégât collatéral).
  assert.equal(typeof solar.metreCableDcParPaires, 'function')
  assert.equal(typeof solar.onduleurSpecsManquantes, 'function')
})

test('agronomy.js n’exporte plus les fonctions sans appelant', () => {
  for (const nom of ['requiredFlow', 'hectaresIrrigable',
    'annualWaterFromMonthly', 'datePalmCitedPerTree']) {
    assert.equal(nom in agronomy, false, `agronomy.${nom} est encore exporté`)
  }
  assert.equal(typeof agronomy.waterDemandFromFarm, 'function')
})

test('aucun module du calculateur ne se dit « IMPORTÉ PAR PERSONNE »', () => {
  for (const rel of ['sizingReducer.js', 'hooks/useSizingMoteur.js',
    'hooks/useSizingMoteurPur.js']) {
    const source = readFileSync(join(ICI, rel), 'utf-8')
    assert.equal(source.includes('IMPORTÉ PAR PERSONNE')
      || source.includes('IMPORTÉ PAR\n// PERSONNE'), false, rel)
  }
})
