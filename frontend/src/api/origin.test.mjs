// Garde-fou : la page Paramètres ne doit plus jamais mourir sur une
// variable d'URL vide. Run with: node --test src/api/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { originFrom } from './origin.js'

test('variable vide ou absente → même origine (chaîne vide), jamais d\'exception', () => {
  assert.equal(originFrom(''), '')
  assert.equal(originFrom(undefined), '')
  assert.equal(originFrom(null), '')
  assert.equal(originFrom('   '), '')
})

test('URL valide → origine extraite', () => {
  assert.equal(originFrom('http://localhost/api/django'), 'http://localhost')
  assert.equal(originFrom('https://178-105-192-116.sslip.io/api'), 'https://178-105-192-116.sslip.io')
})

test('valeur invalide → repli même origine, jamais d\'exception', () => {
  assert.equal(originFrom('pas-une-url'), '')
})
