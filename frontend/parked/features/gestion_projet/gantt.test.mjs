// UX39 — Tests de la géométrie PURE du Gantt (date → offset/largeur).
//   Exécuté en CI : node --test src/features/gestion_projet/gantt.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  daysBetween, timelineBounds, barGeometry, markerGeometry, layoutGantt,
} from './gantt.js'

test('daysBetween — jours inclusifs, ordre inversé, invalide', () => {
  assert.equal(daysBetween('2026-01-01', '2026-01-11'), 10)
  assert.equal(daysBetween('2026-01-11', '2026-01-01'), 0)
  assert.equal(daysBetween(null, '2026-01-01'), 0)
})

test('timelineBounds — couvre toutes les barres', () => {
  const b = timelineBounds([
    { date_debut: '2026-01-05', date_fin: '2026-01-10' },
    { date_debut: '2026-01-01', date_fin: '2026-01-03' },
    { date_debut: '2026-01-20', date_fin: '2026-01-25' },
  ])
  assert.equal(b.min.toISOString().slice(0, 10), '2026-01-01')
  assert.equal(b.max.toISOString().slice(0, 10), '2026-01-25')
})

test('timelineBounds — null sans date exploitable', () => {
  assert.equal(timelineBounds([{ date_debut: null, date_fin: null }]), null)
})

test('barGeometry — début à offset 0, moitié de largeur', () => {
  const g = barGeometry('2026-01-01', '2026-01-06', '2026-01-01', '2026-01-11')
  assert.ok(Math.abs(g.offsetPct - 0) < 1e-6)
  assert.ok(Math.abs(g.widthPct - 50) < 1e-6)
})

test('barGeometry — barre au milieu', () => {
  const g = barGeometry('2026-01-06', '2026-01-11', '2026-01-01', '2026-01-11')
  assert.ok(Math.abs(g.offsetPct - 50) < 1e-6)
  assert.ok(Math.abs(g.widthPct - 50) < 1e-6)
})

test('barGeometry — ne déborde jamais de 100 %', () => {
  const g = barGeometry('2026-01-09', '2026-02-01', '2026-01-01', '2026-01-11')
  assert.ok(g.offsetPct + g.widthPct <= 100.0001)
})

test('barGeometry — largeur plancher minimale lisible', () => {
  const g = barGeometry('2026-01-05', '2026-01-05', '2026-01-01', '2026-01-11', { minWidthPct: 2 })
  assert.ok(g.widthPct >= 2)
})

test('barGeometry — bornes invalides → géométrie nulle', () => {
  assert.deepEqual(
    barGeometry('2026-01-01', '2026-01-02', 'x', 'y'),
    { offsetPct: 0, widthPct: 0 },
  )
})

test('markerGeometry — jalon proportionnel + bornage [0,100]', () => {
  assert.ok(Math.abs(markerGeometry('2026-01-06', '2026-01-01', '2026-01-11').leftPct - 50) < 1e-6)
  assert.equal(markerGeometry('2025-12-01', '2026-01-01', '2026-01-11').leftPct, 0)
  assert.equal(markerGeometry('2026-03-01', '2026-01-01', '2026-01-11').leftPct, 100)
  assert.equal(markerGeometry(null, '2026-01-01', '2026-01-11'), null)
})

test('layoutGantt — géométrie sur bornes communes + dégradé sans date', () => {
  const { bounds, rows } = layoutGantt([
    { id: 1, date_debut_prevue: '2026-01-01', date_fin_prevue: '2026-01-06' },
    { id: 2, date_debut_prevue: '2026-01-06', date_fin_prevue: '2026-01-11' },
  ])
  assert.notEqual(bounds, null)
  assert.ok(Math.abs(rows[0].geometry.offsetPct - 0) < 1e-6)
  assert.ok(Math.abs(rows[1].geometry.offsetPct - 50) < 1e-6)

  const empty = layoutGantt([{ id: 1 }])
  assert.equal(empty.bounds, null)
  assert.equal(empty.rows[0].geometry, null)
})
