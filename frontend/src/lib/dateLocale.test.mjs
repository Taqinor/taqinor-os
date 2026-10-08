// ADEV73 - todayLocalIso : date du jour a Casablanca, independante du fuseau du poste.
// Run: node --test src/lib/dateLocale.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { todayLocalIso } from './dateLocale.js'

test('23:30 UTC la veille = déjà le lendemain à Casablanca (UTC+1)', () => {
  assert.equal(todayLocalIso(new Date('2026-10-07T23:30:00Z')), '2026-10-08')
  // La forme UTC naïve, elle, donnerait la veille : c'est le défaut corrigé.
  assert.equal(new Date('2026-10-07T23:30:00Z').toISOString().slice(0, 10), '2026-10-07')
})

test('milieu de journée : même date', () => {
  assert.equal(todayLocalIso(new Date('2026-10-08T12:00:00Z')), '2026-10-08')
})

test('00:30 UTC (01:30 à Casablanca) : même jour UTC et local', () => {
  assert.equal(todayLocalIso(new Date('2026-10-08T00:30:00Z')), '2026-10-08')
})

test('sans argument : une date AAAA-MM-JJ', () => {
  assert.match(todayLocalIso(), /^\d{4}-\d{2}-\d{2}$/)
})
