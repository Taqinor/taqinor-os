import test from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeTheme, normalizeDensity, resolveTheme, THEMES, DENSITIES,
} from './theme.js'

test('normalizeTheme: valeurs valides + repli système', () => {
  assert.equal(normalizeTheme('light'), 'light')
  assert.equal(normalizeTheme('dark'), 'dark')
  assert.equal(normalizeTheme('system'), 'system')
  assert.equal(normalizeTheme('bidon'), 'system')
  assert.equal(normalizeTheme(null), 'system')
  assert.deepEqual(THEMES, ['light', 'dark', 'system'])
})

test('normalizeDensity: défaut comfortable', () => {
  assert.equal(normalizeDensity('compact'), 'compact')
  assert.equal(normalizeDensity('comfortable'), 'comfortable')
  assert.equal(normalizeDensity('xxl'), 'comfortable')
  assert.deepEqual(DENSITIES, ['comfortable', 'compact'])
})

test('resolveTheme: système suit l’OS, explicite est respecté', () => {
  assert.equal(resolveTheme('system', true), 'dark')
  assert.equal(resolveTheme('system', false), 'light')
  assert.equal(resolveTheme('light', true), 'light')
  assert.equal(resolveTheme('dark', false), 'dark')
  assert.equal(resolveTheme('bidon', true), 'dark') // repli système
})
