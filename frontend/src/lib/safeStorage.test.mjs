// VX170 — safeStorage : jamais de throw qui remonte à l'appelant, éviction de
// l'entrée la plus ancienne (sous le même préfixe) quand `setItem` lève un
// quota plein (Safari privé = quota ~0, ou quota réellement saturé).
// Exécuté en CI : node --test src/lib/safeStorage.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { safeGet, safeSet, safeRemove } from './safeStorage.js'

// localStorage factice minimal (Map en mémoire) — CAUTION : jamais un mock du
// VRAI localStorage (il n'y en a pas ici, plain Node), un objet complet avec
// la même surface (getItem/setItem/removeItem/key/length).
function fakeStorage({ quotaAfter = Infinity } = {}) {
  const store = new Map()
  let writes = 0
  return {
    get length() { return store.size },
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => {
      writes += 1
      if (writes > quotaAfter) {
        const err = new Error('quota exceeded')
        err.name = 'QuotaExceededError'
        throw err
      }
      store.set(k, v)
    },
    removeItem: (k) => { store.delete(k) },
    key: (i) => Array.from(store.keys())[i] ?? null,
    _store: store,
  }
}

test('safeGet: renvoie null (jamais de throw) sur une clé absente ou du JSON invalide', () => {
  const storage = fakeStorage()
  storage.setItem('bad', '{not json')
  global.window = { localStorage: storage }

  assert.equal(safeGet('missing'), null)
  assert.equal(safeGet('bad'), null)
})

test('safeSet/safeGet: round-trip normal', () => {
  global.window = { localStorage: fakeStorage() }

  const ok = safeSet('k', { hello: 'world' })
  assert.equal(ok, true)
  assert.deepEqual(safeGet('k'), { hello: 'world' })
})

test('safeRemove: jamais de throw même si localStorage est indisponible', () => {
  global.window = undefined
  assert.doesNotThrow(() => safeRemove('anything'))
  assert.equal(safeGet('anything'), null)
})

test('safeSet: quota plein -> évince la clé la plus ANCIENNE (savedAt) sous le préfixe puis retente', () => {
  const storage = fakeStorage()
  global.window = { localStorage: storage }

  // Deux brouillons déjà présents sous le même préfixe, le premier plus ancien.
  safeSet('taqinor:draft:a', { savedAt: '2026-01-01T00:00:00.000Z', data: 'old' })
  safeSet('taqinor:draft:b', { savedAt: '2026-06-01T00:00:00.000Z', data: 'recent' })
  assert.equal(storage.length, 2)

  // La PROCHAINE écriture (la 3ᵉ) lève un quota plein — safeSet doit évincer
  // « a » (le plus ancien) puis retenter avec succès.
  const realSetItem = storage.setItem
  let calls = 0
  storage.setItem = (k, v) => {
    calls += 1
    if (calls === 1) {
      const err = new Error('quota exceeded')
      err.name = 'QuotaExceededError'
      throw err
    }
    realSetItem(k, v)
  }

  const ok = safeSet('taqinor:draft:c', { savedAt: '2026-07-01T00:00:00.000Z', data: 'new' }, { prefix: 'taqinor:draft:' })

  assert.equal(ok, true, 'safeSet ne doit jamais crasher — succès après éviction')
  assert.equal(safeGet('taqinor:draft:a'), null, 'le plus ancien a été évincé')
  assert.deepEqual(safeGet('taqinor:draft:b'), { savedAt: '2026-06-01T00:00:00.000Z', data: 'recent' })
  assert.deepEqual(safeGet('taqinor:draft:c'), { savedAt: '2026-07-01T00:00:00.000Z', data: 'new' })
})

test('safeSet: quota plein SANS candidat à éviction -> renvoie false, ne crash jamais', () => {
  const storage = fakeStorage({ quotaAfter: 0 })
  global.window = { localStorage: storage }

  const ok = safeSet('solo-key', { data: 'x' })
  assert.equal(ok, false)
})
