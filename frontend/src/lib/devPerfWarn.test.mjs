// VX189(d) — logique pure (topScripts) du helper DEV-only Long Animation
// Frame. `installDevPerfWarn` lui-même dépend de PerformanceObserver
// (absent en node --test) : il est déjà défensif (no-op si l'API manque),
// donc pas testé ici — seule la partie pure/déterministe l'est.
// Exécuté en CI : node --test src/lib/devPerfWarn.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { topScripts, installDevPerfWarn } from './devPerfWarn.js'

test('topScripts : trie par durée décroissante et limite à 3', () => {
  const entry = {
    scripts: [
      { name: 'a.js', duration: 10 },
      { name: 'b.js', duration: 80 },
      { name: 'c.js', duration: 40 },
      { name: 'd.js', duration: 5 },
    ],
  }
  const top = topScripts(entry)
  assert.equal(top.length, 3)
  assert.deepEqual(top.map((s) => s.nom), ['b.js', 'c.js', 'a.js'])
})

test('topScripts : repli sur sourceURL/invoker quand name est absent', () => {
  const entry = { scripts: [{ sourceURL: 'x.js', duration: 5 }, { invoker: 'y-invoker', duration: 3 }] }
  const top = topScripts(entry)
  assert.equal(top[0].nom, 'x.js')
  assert.equal(top[1].nom, 'y-invoker')
})

test('topScripts : liste vide/absente ne lève jamais', () => {
  assert.deepEqual(topScripts({}), [])
  assert.deepEqual(topScripts({ scripts: [] }), [])
})

test('installDevPerfWarn : no-op silencieux sans PerformanceObserver (environnement node)', () => {
  assert.doesNotThrow(() => installDevPerfWarn())
})
