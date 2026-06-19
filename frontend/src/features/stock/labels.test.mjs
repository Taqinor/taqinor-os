// Tests des helpers étiquettes & scan (N20).
// Run with: node --test src/features/stock/labels.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeCode, isValidCode, resolveTarget, KNOWN_PREFIXES,
} from './labels.js'

test('normalizeCode : majuscule le préfixe, conserve l\'id, trim', () => {
  assert.equal(normalizeCode('  produit:42 '), 'PRODUIT:42')
  assert.equal(normalizeCode('Systeme: 7'), 'SYSTEME:7')
  assert.equal(normalizeCode(''), '')
  assert.equal(normalizeCode('garbage'), 'garbage')
  assert.equal(normalizeCode(null), '')
})

test('isValidCode : seuls les préfixes connus + id entier', () => {
  assert.equal(isValidCode('PRODUIT:1'), true)
  assert.equal(isValidCode(' produit:99 '), true)
  assert.equal(isValidCode('SYSTEME:3'), true)
  assert.equal(isValidCode('FACTURE:1'), false)
  assert.equal(isValidCode('PRODUIT:abc'), false)
  assert.equal(isValidCode('PRODUIT:'), false)
  assert.equal(isValidCode(''), false)
})

test('KNOWN_PREFIXES : aligné sur le backend', () => {
  assert.deepEqual(KNOWN_PREFIXES, ['PRODUIT', 'SYSTEME'])
})

test('resolveTarget : produit → /stock pré-rempli avec le SKU', () => {
  const t = resolveTarget({
    type: 'produit', id: 5, label: 'Panneau', sku: 'PAN550', route: '/stock',
  })
  assert.deepEqual(t, { route: '/stock', search: 'PAN550' })
})

test('resolveTarget : produit sans SKU retombe sur le nom', () => {
  const t = resolveTarget({
    type: 'produit', id: 5, label: 'Panneau', sku: '', route: '/stock',
  })
  assert.deepEqual(t, { route: '/stock', search: 'Panneau' })
})

test('resolveTarget : système → /chantiers avec la référence', () => {
  const t = resolveTarget({
    type: 'systeme', id: 9, label: 'CH-2026-001', route: '/chantiers',
  })
  assert.deepEqual(t, { route: '/chantiers', search: 'CH-2026-001' })
})

test('resolveTarget : null/sans route → null', () => {
  assert.equal(resolveTarget(null), null)
  assert.equal(resolveTarget({ type: 'produit' }), null)
})
