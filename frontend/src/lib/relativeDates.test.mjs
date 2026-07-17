import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveRelativeRange, RELATIVE_DATE_PRESETS } from './relativeDates.js'

// Ancre fixe pour des assertions déterministes : mercredi 15 juillet 2026.
const NOW = new Date(2026, 6, 15, 14, 30, 0)

test('RELATIVE_DATE_PRESETS liste les 9 presets attendus', () => {
  const ids = RELATIVE_DATE_PRESETS.map((p) => p.id)
  assert.deepEqual(ids, [
    'today', 'this_week', 'this_month', 'this_quarter', 'this_year',
    'last_7_days', 'last_30_days', 'last_90_days', 'last_month',
  ])
})

test('today: bornes du jour courant', () => {
  const { debut, fin } = resolveRelativeRange('today', NOW)
  assert.equal(debut.getDate(), 15)
  assert.equal(debut.getHours(), 0)
  assert.equal(fin.getDate(), 15)
  assert.equal(fin.getHours(), 23)
})

test('this_week: lundi → dimanche (semaine ISO), 15/07/2026 est un mercredi', () => {
  const { debut, fin } = resolveRelativeRange('this_week', NOW)
  assert.equal(debut.getDay(), 1) // lundi
  assert.equal(debut.getDate(), 13)
  assert.equal(fin.getDay(), 0) // dimanche
  assert.equal(fin.getDate(), 19)
})

test('this_month: 1er au dernier jour de juillet 2026', () => {
  const { debut, fin } = resolveRelativeRange('this_month', NOW)
  assert.equal(debut.getDate(), 1)
  assert.equal(debut.getMonth(), 6)
  assert.equal(fin.getDate(), 31)
  assert.equal(fin.getMonth(), 6)
})

test('this_quarter: Q3 2026 = juillet-septembre', () => {
  const { debut, fin } = resolveRelativeRange('this_quarter', NOW)
  assert.equal(debut.getMonth(), 6) // juillet
  assert.equal(debut.getDate(), 1)
  assert.equal(fin.getMonth(), 8) // septembre
  assert.equal(fin.getDate(), 30)
})

test('this_year: 1er janvier → 31 décembre 2026', () => {
  const { debut, fin } = resolveRelativeRange('this_year', NOW)
  assert.equal(debut.getFullYear(), 2026)
  assert.equal(debut.getMonth(), 0)
  assert.equal(fin.getMonth(), 11)
  assert.equal(fin.getDate(), 31)
})

test('last_7_days: inclut aujourd\'hui, 7 jours au total', () => {
  const { debut, fin } = resolveRelativeRange('last_7_days', NOW)
  const days = Math.round((fin - debut) / 86400000)
  assert.ok(days >= 6 && days <= 7)
  assert.equal(fin.getDate(), 15)
})

test('last_month: juin 2026 entier', () => {
  const { debut, fin } = resolveRelativeRange('last_month', NOW)
  assert.equal(debut.getMonth(), 5) // juin
  assert.equal(debut.getDate(), 1)
  assert.equal(fin.getMonth(), 5)
  assert.equal(fin.getDate(), 30)
})

test('preset inconnu → null (aucun filtre)', () => {
  assert.equal(resolveRelativeRange('bogus', NOW), null)
})

test('RÉÉVALUÉ à chaque appel : deux `now` différents donnent des bornes différentes (jamais persisté figé)', () => {
  const laterNow = new Date(2026, 9, 1) // 1er octobre 2026 → Q4
  const q3 = resolveRelativeRange('this_quarter', NOW)
  const q4 = resolveRelativeRange('this_quarter', laterNow)
  assert.notEqual(q3.debut.getMonth(), q4.debut.getMonth())
})
