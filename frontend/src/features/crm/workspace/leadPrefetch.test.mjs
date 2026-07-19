import test from 'node:test'
import assert from 'node:assert/strict'

const {
  getPrefetched, setPrefetched, clearPrefetched, resetPrefetchCache, schedulePrefetch,
} = await import('./leadPrefetch.js')

test('getPrefetched: absent → null', () => {
  resetPrefetchCache()
  assert.equal(getPrefetched(1), null)
  assert.equal(getPrefetched(null), null)
})

test('setPrefetched/getPrefetched: pose puis relit la même donnée', () => {
  resetPrefetchCache()
  setPrefetched(7, { id: 7, nom: 'Ali' })
  assert.deepEqual(getPrefetched(7), { id: 7, nom: 'Ali' })
})

test('setPrefetched: id/donnée invalide → no-op', () => {
  resetPrefetchCache()
  setPrefetched(null, { id: 1 })
  setPrefetched(1, null)
  assert.equal(getPrefetched(1), null)
})

test('TTL 60s : une entrée expirée est purgée et redevient absente', (t) => {
  resetPrefetchCache()
  t.mock.timers.enable({ apis: ['Date'] })
  setPrefetched(3, { id: 3 })
  assert.deepEqual(getPrefetched(3), { id: 3 })
  t.mock.timers.tick(59_000)
  assert.deepEqual(getPrefetched(3), { id: 3 }) // toujours frais à 59s
  t.mock.timers.tick(2_000) // 61s au total → expiré
  assert.equal(getPrefetched(3), null)
})

test('clearPrefetched: retire une entrée explicitement', () => {
  resetPrefetchCache()
  setPrefetched(9, { id: 9 })
  clearPrefetched(9)
  assert.equal(getPrefetched(9), null)
})

test('schedulePrefetch: sans id valide → aucun fetch (pas de fetch sans file)', () => {
  resetPrefetchCache()
  const fetchFn = () => Promise.resolve({})
  const cancel = schedulePrefetch([], fetchFn)
  assert.equal(typeof cancel, 'function')
  const cancel2 = schedulePrefetch([null, undefined], fetchFn)
  assert.equal(typeof cancel2, 'function')
})

test('schedulePrefetch: appelle fetchFn(id) après le délai (repli setTimeout) pour chaque id manquant', async () => {
  resetPrefetchCache()
  const calls = []
  const fetchFn = (id) => { calls.push(id); return Promise.resolve({ id }) }
  schedulePrefetch([1, 2], fetchFn, { delay: 5 })
  assert.deepEqual(calls, []) // rien avant le délai
  await new Promise((r) => setTimeout(r, 20))
  assert.deepEqual(calls.sort(), [1, 2])
  // les données pré-chargées sont maintenant en cache
  assert.deepEqual(getPrefetched(1), { id: 1 })
  assert.deepEqual(getPrefetched(2), { id: 2 })
})

test('schedulePrefetch: un id déjà en cache frais est sauté (aucun re-fetch)', async () => {
  resetPrefetchCache()
  setPrefetched(5, { id: 5, cached: true })
  const calls = []
  const fetchFn = (id) => { calls.push(id); return Promise.resolve({ id }) }
  schedulePrefetch([5], fetchFn, { delay: 5 })
  await new Promise((r) => setTimeout(r, 20))
  assert.deepEqual(calls, [])
  assert.deepEqual(getPrefetched(5), { id: 5, cached: true })
})

test('schedulePrefetch: la fonction d\'annulation empêche le fetch s\'il n\'a pas encore eu lieu', async () => {
  resetPrefetchCache()
  const calls = []
  const fetchFn = (id) => { calls.push(id); return Promise.resolve({ id }) }
  const cancel = schedulePrefetch([1], fetchFn, { delay: 20 })
  cancel()
  await new Promise((r) => setTimeout(r, 40))
  assert.deepEqual(calls, [])
})

test('schedulePrefetch: un échec de fetch reste silencieux (jamais de rejet non attrapé)', async () => {
  resetPrefetchCache()
  const fetchFn = () => Promise.reject(new Error('réseau'))
  schedulePrefetch([1], fetchFn, { delay: 5 })
  await new Promise((r) => setTimeout(r, 20))
  assert.equal(getPrefetched(1), null)
})
