// LW16 — Tests du classifieur de pourrissement PUR (blueprint D3). Exécutés en
// CI : node --test src/features/crm/workspace/rotting.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { rottingLevel, thresholdsForIndex, STAGE_ROTTING_THRESHOLDS } from './rotting.js'

// Rappel de l'ordre PIPELINE_STAGES (stages.js) : NEW(0) CONTACTED(1)
// QUOTE_SENT(2) FOLLOW_UP(3) SIGNED(4) COLD(5).

test('CONTACTED (index 1) à 8 j → warning (seuils 7/14)', () => {
  assert.equal(rottingLevel(8, thresholdsForIndex(1)), 'warning')
})

test('CONTACTED (index 1) à 15 j → danger', () => {
  assert.equal(rottingLevel(15, thresholdsForIndex(1)), 'danger')
})

test('NEW (index 0) : 2 j ok, 3 j warning, 6 j danger', () => {
  assert.equal(rottingLevel(2, thresholdsForIndex(0)), 'ok')
  assert.equal(rottingLevel(3, thresholdsForIndex(0)), 'warning')
  assert.equal(rottingLevel(6, thresholdsForIndex(0)), 'danger')
})

test('QUOTE_SENT (index 2) partage les seuils de CONTACTED', () => {
  assert.deepEqual(thresholdsForIndex(2), thresholdsForIndex(1))
  assert.equal(rottingLevel(10, thresholdsForIndex(2)), 'warning')
})

test('FOLLOW_UP (index 3) : 14 j ok, 15 j warning, 31 j danger', () => {
  assert.equal(rottingLevel(14, thresholdsForIndex(3)), 'ok')
  assert.equal(rottingLevel(15, thresholdsForIndex(3)), 'warning')
  assert.equal(rottingLevel(31, thresholdsForIndex(3)), 'danger')
})

test('SIGNED (4) et COLD (5) ne pourrissent jamais', () => {
  assert.equal(thresholdsForIndex(4), null)
  assert.equal(thresholdsForIndex(5), null)
  assert.equal(rottingLevel(999, thresholdsForIndex(4)), 'ok')
  assert.equal(rottingLevel(999, thresholdsForIndex(5)), 'ok')
})

test('jours absents/invalides ou étape inconnue → ok (aucune alerte fantôme)', () => {
  assert.equal(rottingLevel(null, thresholdsForIndex(1)), 'ok')
  assert.equal(rottingLevel(undefined, thresholdsForIndex(1)), 'ok')
  assert.equal(rottingLevel('abc', thresholdsForIndex(1)), 'ok')
  assert.equal(rottingLevel(50, thresholdsForIndex(-1)), 'ok')
})

test('la table couvre exactement les 6 étapes du pipeline', () => {
  assert.equal(STAGE_ROTTING_THRESHOLDS.length, 6)
})
