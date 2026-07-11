// VX42 — Tests purs (node --test, aucune dépendance) du helper haptique
// défensif : jamais de plantage si `navigator`/`vibrate` sont absents ou
// lèvent, appelle bien `vibrate` avec la durée demandée quand disponible.
import { test } from 'node:test'
import assert from 'node:assert/strict'

// Charge le module avec un `navigator` global contrôlé (défini avant l'import
// dynamique pour que le module le lise au moment de l'appel, pas de l'import —
// hapticTap lit `navigator` à l'appel, donc un simple global suffit). Node 24+
// expose un `navigator` global EN LECTURE SEULE (getter) : on doit redéfinir
// la propriété via `Object.defineProperty`, une simple affectation lève.
const { hapticTap } = await import('./haptics.js')

function setNavigator(value) {
  Object.defineProperty(globalThis, 'navigator', {
    value, configurable: true, writable: true,
  })
}

test('hapticTap() appelle navigator.vibrate avec la durée par défaut (10ms)', () => {
  const calls = []
  setNavigator({ vibrate: (ms) => { calls.push(ms); return true } })
  hapticTap()
  assert.deepEqual(calls, [10])
})

test('hapticTap(durationMs) transmet une durée personnalisée', () => {
  const calls = []
  setNavigator({ vibrate: (ms) => { calls.push(ms); return true } })
  hapticTap(25)
  assert.deepEqual(calls, [25])
})

test('hapticTap() ne plante jamais quand navigator.vibrate est absent', () => {
  setNavigator({})
  assert.doesNotThrow(() => hapticTap())
})

test('hapticTap() ne plante jamais quand navigator est absent', () => {
  setNavigator(undefined)
  assert.doesNotThrow(() => hapticTap())
})

test('hapticTap() ne plante jamais si vibrate lève une exception', () => {
  setNavigator({ vibrate: () => { throw new Error('nope') } })
  assert.doesNotThrow(() => hapticTap())
})
