import test from 'node:test'
import assert from 'node:assert/strict'
import {
  weekdayMondayFirst, startOfDay, isSameDay, isSameMonth, daysInMonth,
  addDays, addMonths, diffDays, buildMonthGrid, isDateDisabled,
  isWithinRange, applyRangeSelection, parseTime, formatTime, timeOptions,
} from './date-utils.js'

const D = (y, m, d) => new Date(y, m - 1, d) // mois humain (1–12)

test('weekdayMondayFirst : lundi=0 … dimanche=6', () => {
  assert.equal(weekdayMondayFirst(D(2026, 6, 15)), 0) // 15 juin 2026 = lundi
  assert.equal(weekdayMondayFirst(D(2026, 6, 21)), 6) // dimanche
})

test('startOfDay supprime l’heure et ne mute pas', () => {
  const src = new Date(2026, 5, 18, 14, 30, 12)
  const d = startOfDay(src)
  assert.equal(d.getHours(), 0)
  assert.equal(d.getMinutes(), 0)
  assert.equal(src.getHours(), 14) // pas de mutation
})

test('isSameDay / isSameMonth', () => {
  assert.equal(isSameDay(D(2026, 6, 18), new Date(2026, 5, 18, 23, 59)), true)
  assert.equal(isSameDay(D(2026, 6, 18), D(2026, 6, 19)), false)
  assert.equal(isSameDay(null, D(2026, 6, 18)), false)
  assert.equal(isSameMonth(D(2026, 6, 1), D(2026, 6, 30)), true)
  assert.equal(isSameMonth(D(2026, 6, 30), D(2026, 7, 1)), false)
})

test('daysInMonth gère février bissextile', () => {
  assert.equal(daysInMonth(2026, 1), 28) // février 2026 (non bissextile)
  assert.equal(daysInMonth(2024, 1), 29) // février 2024 (bissextile)
  assert.equal(daysInMonth(2026, 0), 31)
})

test('addDays traverse les fins de mois et n’est pas muté', () => {
  const base = D(2026, 6, 30)
  assert.ok(isSameDay(addDays(base, 1), D(2026, 7, 1)))
  assert.ok(isSameDay(addDays(base, -1), D(2026, 6, 29)))
  assert.ok(isSameDay(base, D(2026, 6, 30))) // intact
})

test('addMonths clampe le jour en fin de mois court', () => {
  assert.ok(isSameDay(addMonths(D(2026, 1, 31), 1), D(2026, 2, 28))) // 31 janv → 28 fév
  assert.ok(isSameDay(addMonths(D(2026, 12, 15), 1), D(2027, 1, 15))) // passage d’année
  assert.ok(isSameDay(addMonths(D(2026, 1, 15), -1), D(2025, 12, 15)))
})

test('diffDays compte les jours pleins', () => {
  assert.equal(diffDays(D(2026, 6, 1), D(2026, 6, 11)), 10)
  assert.equal(diffDays(D(2026, 6, 11), D(2026, 6, 1)), -10)
  assert.equal(diffDays(D(2026, 6, 1), D(2026, 6, 1)), 0)
})

test('buildMonthGrid : 42 cellules commençant un lundi', () => {
  const cells = buildMonthGrid(2026, 5) // juin 2026
  assert.equal(cells.length, 42)
  assert.equal(weekdayMondayFirst(cells[0].date), 0) // première cellule = lundi
  // 1er juin 2026 est un lundi → première cellule EST le 1er juin, inMonth
  assert.ok(isSameDay(cells[0].date, D(2026, 6, 1)))
  assert.equal(cells[0].inMonth, true)
  // un jour du mois suivant est marqué inMonth=false
  const last = cells[cells.length - 1]
  assert.equal(last.inMonth, false)
})

test('buildMonthGrid : mois démarrant en milieu de semaine porte des jours du mois précédent', () => {
  // juillet 2026 : le 1er est un mercredi (weekday lundi-first = 2)
  const cells = buildMonthGrid(2026, 6)
  assert.equal(cells[0].inMonth, false) // cellule du mois précédent (juin)
  assert.ok(isSameDay(cells[2].date, D(2026, 7, 1)))
  assert.equal(cells[2].inMonth, true)
})

test('isDateDisabled : bornes min/max incluses + prédicat', () => {
  const min = D(2026, 6, 10)
  const max = D(2026, 6, 20)
  assert.equal(isDateDisabled(D(2026, 6, 9), { min, max }), true)
  assert.equal(isDateDisabled(D(2026, 6, 10), { min, max }), false) // borne incluse
  assert.equal(isDateDisabled(D(2026, 6, 20), { min, max }), false) // borne incluse
  assert.equal(isDateDisabled(D(2026, 6, 21), { min, max }), true)
  // prédicat : désactive les dimanches
  const disabled = (d) => d.getDay() === 0
  assert.equal(isDateDisabled(D(2026, 6, 21), { disabled }), true) // dimanche
  assert.equal(isDateDisabled(D(2026, 6, 22), { disabled }), false) // lundi
})

test('isWithinRange : bornes incluses, ordre indifférent', () => {
  const a = D(2026, 6, 10)
  const b = D(2026, 6, 20)
  assert.equal(isWithinRange(D(2026, 6, 15), a, b), true)
  assert.equal(isWithinRange(a, a, b), true)
  assert.equal(isWithinRange(b, a, b), true)
  assert.equal(isWithinRange(D(2026, 6, 21), a, b), false)
  assert.equal(isWithinRange(D(2026, 6, 15), b, a), true) // ordre inversé toléré
  assert.equal(isWithinRange(D(2026, 6, 15), null, b), false)
})

test('applyRangeSelection : ouvre, ferme, réordonne, redémarre', () => {
  // rien sélectionné → ouvre
  let r = applyRangeSelection(null, D(2026, 6, 10))
  assert.ok(isSameDay(r.start, D(2026, 6, 10)))
  assert.equal(r.end, null)
  // un bord posé, clic après → ferme
  r = applyRangeSelection(r, D(2026, 6, 20))
  assert.ok(isSameDay(r.start, D(2026, 6, 10)))
  assert.ok(isSameDay(r.end, D(2026, 6, 20)))
  // intervalle complet, nouveau clic → redémarre
  r = applyRangeSelection(r, D(2026, 6, 5))
  assert.ok(isSameDay(r.start, D(2026, 6, 5)))
  assert.equal(r.end, null)
  // un bord posé, clic AVANT → réordonne
  r = applyRangeSelection({ start: D(2026, 6, 10), end: null }, D(2026, 6, 3))
  assert.ok(isSameDay(r.start, D(2026, 6, 3)))
  assert.ok(isSameDay(r.end, D(2026, 6, 10)))
})

test('parseTime : valide HH:mm, rejette le reste', () => {
  assert.deepEqual(parseTime('09:30'), { h: 9, m: 30 })
  assert.deepEqual(parseTime('9:05'), { h: 9, m: 5 })
  assert.deepEqual(parseTime('23:59'), { h: 23, m: 59 })
  assert.deepEqual(parseTime('00:00'), { h: 0, m: 0 })
  assert.equal(parseTime('24:00'), null)
  assert.equal(parseTime('12:60'), null)
  assert.equal(parseTime('12'), null)
  assert.equal(parseTime('abc'), null)
  assert.equal(parseTime(''), null)
  assert.equal(parseTime(null), null)
})

test('formatTime : zéro-padding + clamp', () => {
  assert.equal(formatTime(9, 5), '09:05')
  assert.equal(formatTime(0, 0), '00:00')
  assert.equal(formatTime({ h: 14, m: 30 }), '14:30')
  assert.equal(formatTime(25, 70), '23:59') // clamp
})

test('timeOptions : nombre de créneaux selon le pas', () => {
  assert.equal(timeOptions(30).length, 48)
  assert.equal(timeOptions(60).length, 24)
  assert.equal(timeOptions(15).length, 96)
  assert.equal(timeOptions(30)[0], '00:00')
  assert.equal(timeOptions(30)[1], '00:30')
  assert.equal(timeOptions(60)[9], '09:00')
})
