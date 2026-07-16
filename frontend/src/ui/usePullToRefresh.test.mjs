import test from 'node:test'
import assert from 'node:assert/strict'
import { dampenPull, shouldArmPull, shouldTriggerRefresh } from './pullToRefreshMath.js'

/* ===================== dampenPull ===================== */

test('dampenPull: zéro ou négatif → 0', () => {
  assert.equal(dampenPull(0), 0)
  assert.equal(dampenPull(-10), 0)
})

test('dampenPull: croît avec la distance mais ne dépasse jamais maxPull', () => {
  const a = dampenPull(10, 120)
  const b = dampenPull(50, 120)
  const c = dampenPull(1000, 120)
  assert.ok(a > 0 && a < b)
  assert.ok(b < c)
  assert.ok(c <= 120)
  assert.ok(c > 100) // proche de l'asymptote pour une très grande distance
})

test('dampenPull: résistance — la sortie croît moins vite que l\'entrée', () => {
  const raw = 200
  const damped = dampenPull(raw, 120)
  assert.ok(damped < raw)
})

/* ===================== shouldArmPull ===================== */

test('shouldArmPull: refuse si le conteneur n\'est pas tout en haut', () => {
  assert.equal(shouldArmPull({ scrollTop: 5, deltaY: 20 }), false)
  assert.equal(shouldArmPull({ scrollTop: 1, deltaY: 100 }), false)
})

test('shouldArmPull: refuse un mouvement vers le haut ou nul', () => {
  assert.equal(shouldArmPull({ scrollTop: 0, deltaY: 0 }), false)
  assert.equal(shouldArmPull({ scrollTop: 0, deltaY: -20 }), false)
})

test('shouldArmPull: refuse un geste surtout horizontal (anti-scroll)', () => {
  assert.equal(shouldArmPull({ scrollTop: 0, deltaX: 50, deltaY: 10 }), false)
})

test('shouldArmPull: arme un tirage vertical vers le bas depuis le haut', () => {
  assert.equal(shouldArmPull({ scrollTop: 0, deltaX: 2, deltaY: 30 }), true)
  assert.equal(shouldArmPull({ scrollTop: 0, deltaY: 5 }), true) // deltaX par défaut = 0
})

/* ===================== shouldTriggerRefresh ===================== */

test('shouldTriggerRefresh: sous le seuil → false, au-delà → true', () => {
  assert.equal(shouldTriggerRefresh(10, 64), false)
  assert.equal(shouldTriggerRefresh(63, 64), false)
  assert.equal(shouldTriggerRefresh(64, 64), true)
  assert.equal(shouldTriggerRefresh(120, 64), true)
})

test('shouldTriggerRefresh: seuil par défaut (64)', () => {
  assert.equal(shouldTriggerRefresh(50), false)
  assert.equal(shouldTriggerRefresh(70), true)
})
