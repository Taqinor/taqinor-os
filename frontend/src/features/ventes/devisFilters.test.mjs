// Tests de la logique pure de la liste des devis (T7a/T10).
// Run: node --test src/features/ventes/devisFilters.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { filterDevisByExpiry, versionLabel, canRevise } from './devisFilters.js'

const D = (id, extra = {}) => ({ id, ...extra })
const SAMPLE = [
  D(1, { est_expire: true }),
  D(2, { est_expire: false }),
  D(3, { est_expire: true }),
]

test('filterDevisByExpiry — all retourne tout', () => {
  assert.equal(filterDevisByExpiry(SAMPLE, 'all').length, 3)
})

test('filterDevisByExpiry — expire ne garde que les expirés', () => {
  const out = filterDevisByExpiry(SAMPLE, 'expire')
  assert.deepEqual(out.map(d => d.id), [1, 3])
})

test('filterDevisByExpiry — valide ne garde que les non-expirés', () => {
  const out = filterDevisByExpiry(SAMPLE, 'valide')
  assert.deepEqual(out.map(d => d.id), [2])
})

test('versionLabel — v1 sans badge, v2+ avec badge', () => {
  assert.equal(versionLabel({ version: 1 }), null)
  assert.equal(versionLabel({}), null)
  assert.equal(versionLabel({ version: 2 }), 'v2')
  assert.equal(versionLabel({ version: 5 }), 'v5')
})

test('canRevise — faux si déjà remplacé', () => {
  assert.equal(canRevise({ version: 1 }), true)
  assert.equal(canRevise({ remplace_par: { id: 9 } }), false)
})
