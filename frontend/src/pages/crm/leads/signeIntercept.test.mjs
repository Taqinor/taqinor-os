// LB3 — sentinelle d'interception « Signé » (blueprint I3, bug recon2-03 #2).
//   node --test src/pages/crm/leads/signeIntercept.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { SIGNE_INTERCEPT, isSigneIntercept } from './signeIntercept.js'

test('SIGNE_INTERCEPT est une sentinelle unique (Symbol), jamais confondue avec une vraie erreur', () => {
  assert.equal(typeof SIGNE_INTERCEPT, 'symbol')
  assert.notEqual(SIGNE_INTERCEPT, Symbol('SIGNE_INTERCEPT')) // pas une valeur re-créable ailleurs
})

test('isSigneIntercept reconnaît UNIQUEMENT la sentinelle exportée', () => {
  assert.equal(isSigneIntercept(SIGNE_INTERCEPT), true)
  assert.equal(isSigneIntercept(new Error('boom')), false)
  assert.equal(isSigneIntercept(undefined), false)
  assert.equal(isSigneIntercept(null), false)
  assert.equal(isSigneIntercept('SIGNE_INTERCEPT'), false) // une chaîne homonyme n'est pas la sentinelle
})
