import test from 'node:test'
import assert from 'node:assert/strict'
import {
  runOptimistic, optimisticListUpdate, optimisticListRemove,
} from './optimistic.js'

test('runOptimistic: applique l’état optimiste puis confirme (succès)', async () => {
  const seen = []
  const res = await runOptimistic({
    current: 1,
    optimistic: 2,
    apply: (v) => seen.push(v),
    commit: async () => 'OK',
  })
  assert.deepEqual(seen, [2])            // appliqué une seule fois (optimiste)
  assert.deepEqual(res, { ok: true, data: 'OK' })
})

test('runOptimistic: rollback à l’état précédent en cas d’échec', async () => {
  const seen = []
  const err = new Error('boom')
  let onErrorArgs = null
  const res = await runOptimistic({
    current: 'avant',
    optimistic: 'après',
    apply: (v) => seen.push(v),
    commit: async () => { throw err },
    onError: (e, prev) => { onErrorArgs = [e, prev] },
  })
  // optimiste puis restauration
  assert.deepEqual(seen, ['après', 'avant'])
  assert.equal(res.ok, false)
  assert.equal(res.error, err)
  assert.deepEqual(onErrorArgs, [err, 'avant']) // onError reçoit l'erreur + l'ancien état
})

test('runOptimistic: rollback custom utilisé à la place d’apply', async () => {
  const applied = []
  const rolledBack = []
  await runOptimistic({
    current: { n: 0 },
    optimistic: { n: 9 },
    apply: (v) => applied.push(v),
    commit: async () => { throw new Error('x') },
    rollback: (prev) => rolledBack.push(prev),
  })
  assert.deepEqual(applied, [{ n: 9 }])      // apply seulement pour l'optimiste
  assert.deepEqual(rolledBack, [{ n: 0 }])   // rollback custom pour la restauration
})

test('runOptimistic: optimistic peut être une fonction de l’état courant', async () => {
  const seen = []
  await runOptimistic({
    current: 5,
    optimistic: (cur) => cur + 10,
    apply: (v) => seen.push(v),
    commit: async () => true,
  })
  assert.deepEqual(seen, [15])
})

test('runOptimistic: ne rejette jamais même si onError lance', async () => {
  const res = await runOptimistic({
    current: 0,
    optimistic: 1,
    apply: () => {},
    commit: async () => { throw new Error('net') },
    onError: () => { throw new Error('toast cassé') },
  })
  assert.equal(res.ok, false)
})

test('runOptimistic: valide les arguments requis (rejet)', async () => {
  await assert.rejects(runOptimistic({ apply: undefined, commit: () => {} }), /apply/)
  await assert.rejects(runOptimistic({ apply: () => {}, commit: undefined }), /commit/)
})

test('optimisticListUpdate: remplace par clé, laisse le reste intact', () => {
  const rows = [{ id: 1, n: 'a' }, { id: 2, n: 'b' }]
  const out = optimisticListUpdate(rows, { id: 2, n: 'B' })
  assert.deepEqual(out, [{ id: 1, n: 'a' }, { id: 2, n: 'B' }])
  // entrée non mutée
  assert.equal(rows[1].n, 'b')
})

test('optimisticListUpdate: clé personnalisée', () => {
  const rows = [{ ref: 'x', v: 1 }, { ref: 'y', v: 2 }]
  const out = optimisticListUpdate(rows, { ref: 'x', v: 99 }, 'ref')
  assert.deepEqual(out, [{ ref: 'x', v: 99 }, { ref: 'y', v: 2 }])
})

test('optimisticListRemove: retire par id (et par clé custom)', () => {
  assert.deepEqual(optimisticListRemove([{ id: 1 }, { id: 2 }], 1), [{ id: 2 }])
  assert.deepEqual(
    optimisticListRemove([{ k: 'a' }, { k: 'b' }], 'b', 'k'),
    [{ k: 'a' }],
  )
})

test('helpers de liste: tolèrent une entrée non-tableau', () => {
  assert.equal(optimisticListUpdate(null, { id: 1 }), null)
  assert.equal(optimisticListRemove(undefined, 1), undefined)
})
