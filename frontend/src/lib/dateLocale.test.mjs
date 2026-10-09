// ADEV73 - todayLocalIso : date du jour a Casablanca, independante du fuseau du poste.
// Run: node --test src/lib/dateLocale.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { todayLocalIso } from './dateLocale.js'

test('23:30 UTC la veille = déjà le lendemain à Casablanca (UTC+1)', () => {
  const t = new Date('2026-10-07T23:30:00Z')
  // Décalage réel du fuseau selon la base tz du runtime (UTC+1 hors Ramadan ;
  // certaines bases tz de runner CI diffèrent) : le test suit la base, pas une constante.
  const off = new Intl.DateTimeFormat('en', { timeZone: 'Africa/Casablanca', timeZoneName: 'longOffset' })
    .formatToParts(t).find((p) => p.type === 'timeZoneName').value
  assert.equal(todayLocalIso(t), off === 'GMT+01:00' ? '2026-10-08' : '2026-10-07')
  // La forme UTC naïve, elle, donnerait la veille : c'est le défaut corrigé.
  assert.equal(t.toISOString().slice(0, 10), '2026-10-07')
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
