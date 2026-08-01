// APX23 — Tests purs (node --test, meme pattern que lib/haptics.test.mjs) du
// canal haptique du scan : `triggerScanHaptic` delegue a `hapticTap` (VX42) —
// aucun nouveau canal sonore/haptique, juste le point d'entree partage
// accepte/refuse consomme par ReceptionScanPanel.
import { test } from 'node:test'
import assert from 'node:assert/strict'

const { triggerScanHaptic } = await import('./scanFeedback.js')

function setNavigator(value) {
  Object.defineProperty(globalThis, 'navigator', {
    value, configurable: true, writable: true,
  })
}

test('triggerScanHaptic() declenche navigator.vibrate(10) — canal VX42', () => {
  const calls = []
  setNavigator({ vibrate: (ms) => { calls.push(ms); return true } })
  triggerScanHaptic()
  assert.deepEqual(calls, [10])
})

test('triggerScanHaptic() ne plante jamais quand navigator.vibrate est absent', () => {
  setNavigator({})
  assert.doesNotThrow(() => triggerScanHaptic())
})

test('triggerScanHaptic() ne plante jamais quand navigator est absent', () => {
  setNavigator(undefined)
  assert.doesNotThrow(() => triggerScanHaptic())
})
