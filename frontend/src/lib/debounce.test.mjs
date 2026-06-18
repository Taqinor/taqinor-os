import test from 'node:test'
import assert from 'node:assert/strict'
import { setTimeout as delay } from 'node:timers/promises'
import { debounce } from './debounce.js'

/* O66 — Tests de l'anti-rebond (timing + appel trailing). */

test('debounce: ne déclenche qu une fois après la pause (trailing)', async () => {
  const calls = []
  const d = debounce((v) => calls.push(v), 30)
  d('a')
  d('b')
  d('c')
  // Avant l'échéance : aucun appel.
  assert.deepEqual(calls, [])
  await delay(60)
  // Un seul appel, avec les derniers arguments.
  assert.deepEqual(calls, ['c'])
})

test('debounce: chaque appel reporte l échéance', async () => {
  const calls = []
  const d = debounce((v) => calls.push(v), 40)
  d('x')
  await delay(25) // < 40ms → pas encore déclenché
  assert.deepEqual(calls, [])
  d('y') // reporte l'échéance de 40ms supplémentaires
  await delay(25) // 25ms après le 2e appel → toujours rien
  assert.deepEqual(calls, [])
  await delay(40) // assez pour franchir l'échéance
  assert.deepEqual(calls, ['y'])
})

test('debounce: appels espacés déclenchent à chaque fois', async () => {
  const calls = []
  const d = debounce((v) => calls.push(v), 20)
  d('1')
  await delay(50)
  d('2')
  await delay(50)
  assert.deepEqual(calls, ['1', '2'])
})

test('debounce: cancel() annule l appel en attente', async () => {
  const calls = []
  const d = debounce((v) => calls.push(v), 30)
  d('a')
  d.cancel()
  await delay(60)
  assert.deepEqual(calls, [])
})

test('debounce: transmet tous les arguments', async () => {
  const seen = []
  const d = debounce((a, b, c) => seen.push([a, b, c]), 15)
  d(1, 2, 3)
  await delay(40)
  assert.deepEqual(seen, [[1, 2, 3]])
})
