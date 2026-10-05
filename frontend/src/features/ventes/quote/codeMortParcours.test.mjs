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

// AGR131 — le jumeau JS du besoin en eau (`agronomy.js`) est SUPPRIMÉ :
// l'écran lit `besoin` dans l'aperçu serveur (AGR127/AGR129).
test('agronomy.js n’existe plus et plus rien ne l’importe', () => {
  assert.equal(existsSync(join(ICI, '..', 'agronomy.js')), false)
  const generateur = readFileSync(
    join(ICI, '..', '..', '..', 'pages', 'ventes', 'DevisGenerator.jsx'), 'utf-8')
  assert.equal(generateur.includes('waterDemandFromFarm'), false)
  assert.equal(/from '[^']*agronomy'/.test(generateur), false)
})

test('aucun module du calculateur ne se dit « IMPORTÉ PAR PERSONNE »', () => {
  for (const rel of ['sizingReducer.js', 'hooks/useSizingMoteur.js',
    'hooks/useSizingMoteurPur.js']) {
    const source = readFileSync(join(ICI, rel), 'utf-8')
    assert.equal(source.includes('IMPORTÉ PAR PERSONNE')
      || source.includes('IMPORTÉ PAR\n// PERSONNE'), false, rel)
  }
})
