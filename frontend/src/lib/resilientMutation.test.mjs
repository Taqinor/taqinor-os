import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resilientMutation, describeFailures } from './resilientMutation.js'

/* VX117 — allSettled + rapport nominatif : jamais un Promise.all qui perd
   les succès déjà acquis au premier échec. */

test('resilientMutation: 1 échec sur 3 → 2 succès nominatifs, allOk=false', async () => {
  const lignes = [{ id: 1, nom: 'A' }, { id: 2, nom: 'B' }, { id: 3, nom: 'C' }]
  const { succeeded, failed, allOk } = await resilientMutation(lignes, (l) => {
    if (l.id === 2) return Promise.reject(new Error('boom'))
    return Promise.resolve({ ...l, saved: true })
  })
  assert.equal(allOk, false)
  assert.equal(succeeded.length, 2)
  assert.equal(failed.length, 1)
  assert.equal(failed[0].item.nom, 'B')
  assert.equal(describeFailures(failed, (i) => i.nom), 'B')
})

test('resilientMutation: tout réussit → allOk=true, failed vide', async () => {
  const items = [1, 2, 3]
  const { succeeded, failed, allOk } = await resilientMutation(items, (n) => Promise.resolve(n * 2))
  assert.equal(allOk, true)
  assert.equal(failed.length, 0)
  assert.deepEqual(succeeded.map((s) => s.value), [2, 4, 6])
})

test('resilientMutation: liste vide → allOk=true (rien à réessayer)', async () => {
  const { succeeded, failed, allOk } = await resilientMutation([], () => Promise.resolve())
  assert.equal(allOk, true)
  assert.equal(succeeded.length, 0)
  assert.equal(failed.length, 0)
})

test('resilientMutation: retry ne renvoie que les items en échec', async () => {
  const items = [{ id: 1 }, { id: 2 }, { id: 3 }]
  const attempts = []
  const failing = new Set([2])
  const first = await resilientMutation(items, (it) => {
    attempts.push(it.id)
    if (failing.has(it.id)) return Promise.reject(new Error('nope'))
    return Promise.resolve(it)
  })
  assert.equal(first.failed.length, 1)
  // Le composant appelant ne relance QUE first.failed.map(f => f.item).
  failing.delete(2)
  const retryItems = first.failed.map((f) => f.item)
  const second = await resilientMutation(retryItems, (it) => {
    attempts.push(it.id)
    return Promise.resolve(it)
  })
  assert.equal(second.allOk, true)
  assert.deepEqual(attempts, [1, 2, 3, 2]) // la relance ne retente QUE l'id 2
})
