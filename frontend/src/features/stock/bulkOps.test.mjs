// Tests des helpers d'édition groupée + édition en ligne du catalogue.
// Run with: node --test src/features/stock/bulkOps.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { previewNewPrix, validateInline, INLINE_FIELDS } from './bulkOps.js'

test('previewNewPrix : variation en pourcentage', () => {
  assert.equal(previewNewPrix('100', 'percent', 10), 110)
  assert.equal(previewNewPrix('100', 'percent', -10), 90)
  assert.equal(previewNewPrix('1272.73', 'percent', 0), 1272.73)
})

test('previewNewPrix : variation en montant fixe', () => {
  assert.equal(previewNewPrix('100', 'fixed', 50), 150)
  assert.equal(previewNewPrix('100', 'fixed', -25), 75)
})

test('previewNewPrix : ne descend jamais sous 0', () => {
  assert.equal(previewNewPrix('100', 'fixed', -500), 0)
  assert.equal(previewNewPrix('100', 'percent', -200), 0)
})

test('previewNewPrix : entrées invalides → null', () => {
  assert.equal(previewNewPrix('abc', 'percent', 10), null)
  assert.equal(previewNewPrix('100', 'autre', 10), null)
  assert.equal(previewNewPrix('100', 'percent', 'x'), null)
})

test('INLINE_FIELDS : prix_achat jamais éditable en ligne', () => {
  assert.ok(!INLINE_FIELDS.includes('prix_achat'))
  assert.deepEqual(INLINE_FIELDS, ['prix_vente', 'quantite_stock', 'categorie_id'])
})

test('validateInline : prix de vente', () => {
  assert.deepEqual(validateInline('prix_vente', '1234.5'), { ok: true, value: 1234.5 })
  assert.equal(validateInline('prix_vente', '-1').ok, false)
  assert.equal(validateInline('prix_vente', 'abc').ok, false)
})

test('validateInline : quantité entière positive', () => {
  assert.deepEqual(validateInline('quantite_stock', '12'), { ok: true, value: 12 })
  assert.equal(validateInline('quantite_stock', '1.5').ok, false)
  assert.equal(validateInline('quantite_stock', '-3').ok, false)
})

test('validateInline : catégorie (id ou vide)', () => {
  assert.deepEqual(validateInline('categorie_id', '5'), { ok: true, value: 5 })
  assert.deepEqual(validateInline('categorie_id', ''), { ok: true, value: null })
  assert.equal(validateInline('categorie_id', '0').ok, false)
})

test('validateInline : champ risqué refusé', () => {
  assert.equal(validateInline('prix_achat', '10').ok, false)
})
