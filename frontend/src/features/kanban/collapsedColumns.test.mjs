// LB10 — Persistance PURE du repli de colonnes (localStorage). Aucun import
// React : un `window.localStorage` FACTICE minimal suffit (même principe que
// jsdom), donc réellement exécutable ici, contrairement aux hooks React de ce
// worktree/lane (pas de node_modules).
//   node --test src/features/kanban/collapsedColumns.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

function makeFakeStorage() {
  const store = new Map()
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(k, String(v)) },
    removeItem: (k) => { store.delete(k) },
    clear: () => { store.clear() },
  }
}

globalThis.window = { localStorage: makeFakeStorage() }

const {
  COLLAPSED_STORAGE_KEY,
  readCollapsedStages,
  writeCollapsedStages,
} = await import('./collapsedColumns.js')

test('LB10 : rien de stocké → aucun repli par défaut (tableau vide)', () => {
  window.localStorage.clear()
  assert.deepEqual(readCollapsedStages(), [])
})

test('LB10 : écrit puis relit le même ensemble de clés', () => {
  writeCollapsedStages(['COLD', 'FOLLOW_UP'])
  assert.deepEqual(readCollapsedStages(), ['COLD', 'FOLLOW_UP'])
})

test('LB10 : dédoublonne les clés en écriture', () => {
  writeCollapsedStages(['COLD', 'COLD', 'NEW'])
  assert.deepEqual(readCollapsedStages(), ['COLD', 'NEW'])
})

test('LB10 : tolérant aux clés inconnues (une étape retirée ne fait jamais planter la lecture)', () => {
  window.localStorage.setItem(
    COLLAPSED_STORAGE_KEY,
    JSON.stringify(['COLD', 'ETAPE_FANTOME_RETIREE']),
  )
  assert.deepEqual(readCollapsedStages(), ['COLD'])
})

test('LB10 : filtre aussi les clés inconnues EN ÉCRITURE (jamais persistées)', () => {
  writeCollapsedStages(['NEW', 'ETAPE_FANTOME'])
  assert.deepEqual(readCollapsedStages(), ['NEW'])
})

test('LB10 : JSON corrompu → tableau vide, jamais un throw', () => {
  window.localStorage.setItem(COLLAPSED_STORAGE_KEY, '{ceci n’est pas du JSON')
  assert.doesNotThrow(() => readCollapsedStages())
  assert.deepEqual(readCollapsedStages(), [])
})

test('LB10 : valeur stockée qui n’est PAS un tableau → tableau vide', () => {
  window.localStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify({ COLD: true }))
  assert.deepEqual(readCollapsedStages(), [])
})

test('LB10 : stockage absent (window supprimé) → lecture/écriture sans throw', () => {
  const saved = globalThis.window
  delete globalThis.window
  assert.doesNotThrow(() => {
    assert.deepEqual(readCollapsedStages(), [])
  })
  assert.doesNotThrow(() => writeCollapsedStages(['NEW']))
  globalThis.window = saved
})
