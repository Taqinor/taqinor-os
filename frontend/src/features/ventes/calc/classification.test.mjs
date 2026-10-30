// SPL210 — tests de calc/classification.js déplacés tel quel de solar.test.mjs (move
// only : aucune assertion modifiée).
//
// Run : node --test src/features/ventes/calc/classification.test.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isPompe } from './classification.js'

test('QX20 — isPompe classe une pompe, pas un panneau/onduleur', () => {
  assert.equal(isPompe('Pompe immergée OSP 30/8'), true)
  assert.equal(isPompe('Pompe de surface'), true)
  assert.equal(isPompe('Panneau Canadien Solar 710W'), false)
  assert.equal(isPompe('Onduleur réseau Huawei 10kW'), false)
  assert.equal(isPompe(''), false)
})
