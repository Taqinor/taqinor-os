// NTUX16 — Tests purs (node:test) du stockage localStorage des préférences
// de colonnes. `useColumnPrefs` (hook React) est vérifié séparément en RTL
// (DataTable.test.jsx) — ici, uniquement `readColumnPrefs`/`writeColumnPrefs`.
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readColumnPrefs, writeColumnPrefs } from './useColumnPrefs.js'

// localStorage minimal en mémoire (aucun DOM en node:test).
function makeMemoryStorage() {
  const store = new Map()
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  }
}

describe('NTUX16 — readColumnPrefs/writeColumnPrefs', () => {
  test('round-trip : écrit puis relit le même état de colonnes', () => {
    globalThis.localStorage = makeMemoryStorage()
    const state = { order: ['nom', 'ville'], hidden: { ville: true }, pinned: {}, widths: { nom: 220 } }
    writeColumnPrefs('stock.produits', state)
    assert.deepEqual(readColumnPrefs('stock.produits'), state)
  })

  test('écran distinct → clé distincte (aucune collision entre écrans)', () => {
    globalThis.localStorage = makeMemoryStorage()
    writeColumnPrefs('stock.produits', { order: ['a'], hidden: {}, pinned: {}, widths: {} })
    writeColumnPrefs('ventes.devis', { order: ['b'], hidden: {}, pinned: {}, widths: {} })
    assert.deepEqual(readColumnPrefs('stock.produits').order, ['a'])
    assert.deepEqual(readColumnPrefs('ventes.devis').order, ['b'])
  })

  test('rien de stocké → null (jamais une erreur)', () => {
    globalThis.localStorage = makeMemoryStorage()
    assert.equal(readColumnPrefs('stock.produits'), null)
  })

  test('JSON corrompu → null (jamais un plantage au montage)', () => {
    const storage = makeMemoryStorage()
    globalThis.localStorage = storage
    storage.setItem('taqinor.stock.produits.columnPrefs', '{not json')
    assert.equal(readColumnPrefs('stock.produits'), null)
  })

  test('forme inattendue (pas un état de colonnes) → null', () => {
    const storage = makeMemoryStorage()
    globalThis.localStorage = storage
    storage.setItem('taqinor.stock.produits.columnPrefs', JSON.stringify({ foo: 'bar' }))
    assert.equal(readColumnPrefs('stock.produits'), null)
  })

  test('localStorage indisponible → readColumnPrefs/writeColumnPrefs ne lèvent jamais', () => {
    const realLS = globalThis.localStorage
    Object.defineProperty(globalThis, 'localStorage', {
      get() { throw new Error('indisponible (mode privé)') },
      configurable: true,
    })
    assert.doesNotThrow(() => writeColumnPrefs('stock.produits', { order: [], hidden: {}, pinned: {}, widths: {} }))
    assert.equal(readColumnPrefs('stock.produits'), null)
    Object.defineProperty(globalThis, 'localStorage', { value: realLS, configurable: true, writable: true })
  })

  test('ecran vide/absent → no-op sûr', () => {
    globalThis.localStorage = makeMemoryStorage()
    assert.equal(readColumnPrefs(''), null)
    assert.equal(readColumnPrefs(undefined), null)
    assert.doesNotThrow(() => writeColumnPrefs('', { order: [] }))
  })
})
