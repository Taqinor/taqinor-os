import test from 'node:test'
import assert from 'node:assert/strict'

import { buildUndoAction, isUndoWindowExpired, UNDO_WINDOW_MS } from './bulkEditUndo.js'

test('UNDO_WINDOW_MS = 10s', () => {
  assert.equal(UNDO_WINDOW_MS, 10000)
})

test('isUndoWindowExpired', () => {
  assert.equal(isUndoWindowExpired(9999), false)
  assert.equal(isUndoWindowExpired(10000), true)
  assert.equal(isUndoWindowExpired(15000), true)
})

test('buildUndoAction: onClick appelle onUndo avec les lignes "updated" sans conflit', () => {
  const result = { updated: [{ id: 1, before: 'a', after: 'b', updated_at: 't1' }], failed: [] }
  let called = null
  const action = buildUndoAction(result, {
    onUndo: (rows) => { called = rows },
    getCurrentUpdatedAt: () => 't1', // inchangé depuis le bulk-update
  })
  assert.equal(action.label, 'Annuler')
  action.onClick()
  assert.deepEqual(called, result.updated)
})

test('buildUndoAction: ligne modifiée entretemps (updated_at différent) → conflit, onUndo N\'EST PAS appelé pour elle', () => {
  const result = {
    updated: [
      { id: 1, before: 'a', after: 'b', updated_at: 't1' },
      { id: 2, before: 'x', after: 'y', updated_at: 't2' },
    ],
    failed: [],
  }
  let undone = null
  let conflicted = null
  const action = buildUndoAction(result, {
    onUndo: (rows) => { undone = rows },
    onConflict: (rows) => { conflicted = rows },
    // id=2 a changé d'updated_at depuis (quelqu'un d'autre l'a modifié) → conflit.
    getCurrentUpdatedAt: (id) => (id === 2 ? 't2-modified' : 't1'),
  })
  action.onClick()
  assert.deepEqual(undone.map((r) => r.id), [1])
  assert.deepEqual(conflicted.map((r) => r.id), [2])
})

test('buildUndoAction: sans getCurrentUpdatedAt, aucune vérification de conflit (repli permissif)', () => {
  const result = { updated: [{ id: 1, before: 'a', after: 'b' }], failed: [] }
  let undone = null
  const action = buildUndoAction(result, { onUndo: (rows) => { undone = rows } })
  action.onClick()
  assert.equal(undone.length, 1)
})

test('buildUndoAction: liste "updated" vide → onUndo jamais appelé', () => {
  let called = false
  const action = buildUndoAction({ updated: [], failed: [] }, { onUndo: () => { called = true } })
  action.onClick()
  assert.equal(called, false)
})
