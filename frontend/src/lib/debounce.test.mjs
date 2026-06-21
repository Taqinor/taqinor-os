import { test } from 'node:test'
import assert from 'node:assert/strict'
import { debounce } from './debounce.js'

/* O66 — Anti-rebond. Timers DÉTERMINISTES via `mock.timers` (node:test) : on
   avance le temps virtuellement (tick) au lieu d'attendre de vrais délais, ce qui
   supprime toute flakiness sous charge CI tout en testant le comportement réel. */

test('debounce: ne déclenche qu une fois après la pause (trailing)', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const d = debounce((v) => calls.push(v), 30)
  d('a')
  d('b')
  d('c')
  assert.deepEqual(calls, []) // avant l'échéance : rien
  t.mock.timers.tick(29)
  assert.deepEqual(calls, [])
  t.mock.timers.tick(1) // échéance franchie → un seul appel, derniers args
  assert.deepEqual(calls, ['c'])
})

test('debounce: chaque appel reporte l échéance', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const d = debounce((v) => calls.push(v), 40)
  d('x')
  t.mock.timers.tick(25) // < 40ms → pas encore
  assert.deepEqual(calls, [])
  d('y') // reporte de 40ms
  t.mock.timers.tick(25) // 25ms après le 2e appel → toujours rien
  assert.deepEqual(calls, [])
  t.mock.timers.tick(15) // franchit l'échéance reportée
  assert.deepEqual(calls, ['y'])
})

test('debounce: appels espacés déclenchent à chaque fois', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const d = debounce((v) => calls.push(v), 20)
  d('1')
  t.mock.timers.tick(20)
  d('2')
  t.mock.timers.tick(20)
  assert.deepEqual(calls, ['1', '2'])
})

test('debounce: cancel() annule l appel en attente', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const d = debounce((v) => calls.push(v), 30)
  d('a')
  d.cancel()
  t.mock.timers.tick(60)
  assert.deepEqual(calls, [])
})

test('debounce: transmet tous les arguments', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const seen = []
  const d = debounce((a, b, c) => seen.push([a, b, c]), 15)
  d(1, 2, 3)
  t.mock.timers.tick(15)
  assert.deepEqual(seen, [[1, 2, 3]])
})
