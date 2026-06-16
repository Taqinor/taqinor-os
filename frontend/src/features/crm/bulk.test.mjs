import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  toggleId, toggleAll, allVisibleSelected, pruneSelection, bulkResultMessage,
} from './bulk.js'

test('toggleId ajoute puis retire', () => {
  let s = new Set()
  s = toggleId(s, 1)
  assert.ok(s.has(1))
  s = toggleId(s, 1)
  assert.ok(!s.has(1))
})

test('toggleAll coche tous les visibles puis vide', () => {
  const visible = [1, 2, 3]
  let s = toggleAll(new Set(), visible)
  assert.deepEqual([...s].sort(), [1, 2, 3])
  // tous cochés → un nouveau toggle vide
  s = toggleAll(s, visible)
  assert.equal(s.size, 0)
})

test('allVisibleSelected ne vaut que si tous cochés', () => {
  assert.ok(allVisibleSelected(new Set([1, 2]), [1, 2]))
  assert.ok(!allVisibleSelected(new Set([1]), [1, 2]))
  assert.ok(!allVisibleSelected(new Set(), []))
})

test('pruneSelection retire les ids disparus', () => {
  const s = pruneSelection(new Set([1, 2, 3]), [2, 3])
  assert.deepEqual([...s].sort(), [2, 3])
})

test('bulkResultMessage résume et détaille les ignorés', () => {
  const msg = bulkResultMessage({
    updated: 2, unchanged: 1,
    skipped: [{ nom: 'A', reason: 'lead Perdu' }],
  })
  assert.match(msg, /2 mis à jour/)
  assert.match(msg, /1 inchangé/)
  assert.match(msg, /1 ignoré/)
  assert.match(msg, /A \(lead Perdu\)/)
})

test('bulkResultMessage gère le cas vide', () => {
  assert.equal(bulkResultMessage({ updated: 0, unchanged: 0, skipped: [] }),
    'Aucune modification')
})
