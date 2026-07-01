// UX1 — Tests de la logique d'échéance (PURE). node --test, sans rendu DOM.
//   Exécuté en CI : node --test src/ui/module/urgency.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  daysUntil, urgencyLevel, urgencyTone, urgencyLabel, compareUrgency,
} from './urgency.js'

// Point d'ancrage fixe (minuit local) pour rendre daysUntil déterministe.
const NOW = new Date(2026, 6, 1) // 1er juillet 2026, 00:00 local

test('daysUntil — nul/invalide → null', () => {
  assert.equal(daysUntil(null, NOW), null)
  assert.equal(daysUntil(undefined, NOW), null)
  assert.equal(daysUntil('', NOW), null)
  assert.equal(daysUntil('pas-une-date', NOW), null)
})

test('daysUntil — jours calendaires positifs/négatifs/zéro', () => {
  assert.equal(daysUntil(new Date(2026, 6, 1), NOW), 0) // aujourd'hui
  assert.equal(daysUntil(new Date(2026, 6, 8), NOW), 7)
  assert.equal(daysUntil(new Date(2026, 5, 30), NOW), -1) // hier
  // Chaîne ISO acceptée
  assert.equal(daysUntil('2026-07-11', new Date('2026-07-01T00:00:00')), 10)
})

test('daysUntil — les heures ne décalent pas le compte du jour', () => {
  const now = new Date(2026, 6, 1, 23, 30) // presque minuit
  assert.equal(daysUntil(new Date(2026, 6, 2, 1, 0), now), 1) // demain 1h → 1 jour
})

test('urgencyLevel — bornes 0 / 7 / 8 / 30 / 31 / négatif / null', () => {
  assert.equal(urgencyLevel(null), 'none')
  assert.equal(urgencyLevel(undefined), 'none')
  assert.equal(urgencyLevel(-1), 'overdue')
  assert.equal(urgencyLevel(-30), 'overdue')
  assert.equal(urgencyLevel(0), 'urgent')
  assert.equal(urgencyLevel(7), 'urgent')
  assert.equal(urgencyLevel(8), 'soon')
  assert.equal(urgencyLevel(30), 'soon')
  assert.equal(urgencyLevel(31), 'ok')
  assert.equal(urgencyLevel(365), 'ok')
})

test('urgencyTone — mappe chaque niveau vers un ton Badge/StatusPill', () => {
  assert.equal(urgencyTone('overdue'), 'danger')
  assert.equal(urgencyTone('urgent'), 'danger')
  assert.equal(urgencyTone('soon'), 'warning')
  assert.equal(urgencyTone('ok'), 'success')
  assert.equal(urgencyTone('none'), 'neutral')
  assert.equal(urgencyTone('inconnu'), 'neutral')
})

test('urgencyLabel — libellés français aux bornes', () => {
  assert.equal(urgencyLabel(null), '—')
  assert.equal(urgencyLabel(undefined), '—')
  assert.equal(urgencyLabel(0), "Aujourd'hui")
  assert.equal(urgencyLabel(5), 'J-5')
  assert.equal(urgencyLabel(30), 'J-30')
  assert.equal(urgencyLabel(-1), 'En retard (J+1)')
  assert.equal(urgencyLabel(-12), 'En retard (J+12)')
})

test('compareUrgency — tri croissant (en retard en premier), nombres bruts', () => {
  const arr = [10, -3, 0, 5]
  arr.sort(compareUrgency)
  assert.deepEqual(arr, [-3, 0, 5, 10])
})

test('compareUrgency — objets {daysLeft}, nulls en dernier', () => {
  const rows = [
    { id: 'a', daysLeft: 12 },
    { id: 'b', daysLeft: null },
    { id: 'c', daysLeft: -2 },
    { id: 'd', daysLeft: 3 },
  ]
  rows.sort(compareUrgency)
  assert.deepEqual(rows.map((r) => r.id), ['c', 'd', 'a', 'b'])
})

test('compareUrgency — en retard trié AVANT une échéance future', () => {
  const overdue = { daysLeft: -1 }
  const future = { daysLeft: 20 }
  assert.ok(compareUrgency(overdue, future) < 0)
  assert.ok(compareUrgency(future, overdue) > 0)
})
