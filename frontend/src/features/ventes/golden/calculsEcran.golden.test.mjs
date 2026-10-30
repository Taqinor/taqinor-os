// SPL190 — GARDE du golden des calculs écran de solar.js (aucun déplacement).
//
// Recalcule chaque entrée de `calculs_ecran_expected.json` avec les fonctions
// de solar.js et exige l'égalité EXACTE avec l'attendu commis (même patron que
// solar.calculs.corpus.test.mjs). Le JSON est produit UNE fois, sur le code
// d'avant les déplacements, par `frontend/scripts/calculs_golden.mjs` ; il
// n'est JAMAIS régénéré pour faire passer un déplacement (PACT10) : un rouge
// ici est un bug du déplacement.
//
// Les imports ci-dessous sont écrits SYMBOLE PAR SYMBOLE : chaque tâche de
// déplacement de solar.js (SPL195, SPL197-SPL202, SPL207) ne change que SA
// ligne d'import, vers le nouveau module.
//
// Run : node --test src/features/ventes/golden/calculsEcran.golden.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { defaultProductLines } from '../calc/autoFill.js'
import { structureRoleForName } from '../calc/autoFill.js'
import { structureChoisie } from '../calc/autoFill.js'
import { orderLinesByRolePreference } from '../calc/autoFill.js'
import { deriveRoleOrderFromLines } from '../calc/autoFill.js'
import { appliquerRecomposition } from '../calc/recomposition.js'
import { fusionnerRecomposition } from '../calc/recomposition.js'
import { fusionnerVariantes } from '../calc/recomposition.js'
import { lignesManuellesEnConflitPossible } from '../calc/recomposition.js'
import { multiPropertyPreviewTTC } from '../calc/totaux.js'
import { avecBatterieAvailability } from '../calc/totaux.js'
import { computeBuyCost } from '../calc/totaux.js'
import { prixParKwc } from '../calc/totaux.js'
import { discountForTarget } from '../calc/totaux.js'
import {
  calculer, chargerCatalogues, EXPECTED_PATH, SEED,
} from '../../../../scripts/calculs_golden.mjs'

const FONCTIONS = {
  defaultProductLines, structureRoleForName, structureChoisie,
  orderLinesByRolePreference, deriveRoleOrderFromLines, appliquerRecomposition,
  fusionnerRecomposition, fusionnerVariantes, lignesManuellesEnConflitPossible,
  multiPropertyPreviewTTC, avecBatterieAvailability, computeBuyCost, prixParKwc,
  discountForTarget,
}

const ATTENDU = JSON.parse(readFileSync(EXPECTED_PATH, 'utf8'))
const CATALOGUES = chargerCatalogues()

test('le golden est entier : graine figée, toutes les fonctions couvertes', () => {
  assert.equal(ATTENDU.seed, SEED)
  assert.equal(ATTENDU.count, ATTENDU.entries.length)
  // ADEV69 — 489 − 176 entrées `autoFillLines` (fonction supprimée) = 313.
  assert.ok(ATTENDU.entries.length >= 313, `golden régressé : ${ATTENDU.entries.length}`)
  assert.ok(!ATTENDU.entries.some((e) => e.axe === 'autoFillLines'), 'axe autoFillLines retiré (ADEV69)')
  const axes = new Set(ATTENDU.entries.map((e) => e.axe))
  for (const nom of Object.keys(FONCTIONS)) assert.ok(axes.has(nom), `fonction non couverte : ${nom}`)
  const catalogues = CATALOGUES.seed94.length + CATALOGUES.realPage1.length
  assert.equal(catalogues, 94 + 50, 'les deux catalogues commis ont changé')
})

for (const entree of ATTENDU.entries) {
  test(`recalcul ${entree.id} (${entree.axe}) == golden commis`, () => {
    const recalc = calculer(entree, FONCTIONS, CATALOGUES)
    assert.deepEqual(JSON.parse(JSON.stringify(recalc)), entree.attendu)
  })
}
