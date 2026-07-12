import { test } from 'node:test'
import assert from 'node:assert/strict'
import { getApiError, apiErrorMessage } from './apiError.js'

/* VX203 — Contrat d'erreur UNIQUE : `getApiError` couvre les formes DRF
   réelles (detail/non_field_errors/champ/429/500 HTML/timeout/réseau). */

test('getApiError: detail simple', () => {
  const err = { response: { status: 400, data: { detail: 'Client requis' } } }
  assert.deepEqual(getApiError(err), { message: 'Client requis', fieldErrors: undefined })
})

test('getApiError: non_field_errors', () => {
  const err = { response: { status: 400, data: { non_field_errors: ['Combinaison déjà utilisée'] } } }
  assert.equal(getApiError(err).message, 'Combinaison déjà utilisée')
})

test('getApiError: erreurs par champ → fieldErrors + message = premier champ', () => {
  const err = { response: { status: 400, data: { nom: ['Ce champ est requis'], email: ['Email invalide'] } } }
  const { message, fieldErrors } = getApiError(err)
  assert.equal(message, 'Ce champ est requis')
  assert.deepEqual(fieldErrors, { nom: 'Ce champ est requis', email: 'Email invalide' })
})

test('getApiError: 429 throttle', () => {
  const err = { response: { status: 429, data: { detail: 'Throttled' } } }
  assert.match(getApiError(err).message, /Trop de requêtes/)
})

test('getApiError: 500 HTML brut → message générique, jamais le HTML', () => {
  const err = {
    response: {
      status: 500,
      data: '<!DOCTYPE html><html><body>Server Error</body></html>',
      headers: { 'content-type': 'text/html; charset=utf-8' },
    },
  }
  const { message } = getApiError(err)
  assert.ok(!message.includes('<'))
  assert.match(message, /Erreur serveur/)
})

test('getApiError: timeout (ECONNABORTED)', () => {
  const err = { code: 'ECONNABORTED' }
  assert.match(getApiError(err).message, /expiré/)
})

test('getApiError: Network Error', () => {
  // VX156 — le moment « erreur réseau » porte désormais la voix Taqinor
  // (honnête, rassurante : la saisie n'est pas perdue).
  const err = { message: 'Network Error' }
  assert.match(getApiError(err).message, /[Cc]onnexion/)
})

test('getApiError: fallback si aucune forme reconnue', () => {
  const err = { response: { status: 400, data: {} } }
  assert.equal(getApiError(err, 'Repli FR').message, 'Repli FR')
})

test('getApiError: chaîne brute (non-JSON, non-HTML)', () => {
  const err = { response: { status: 400, data: 'Erreur texte simple' } }
  assert.equal(getApiError(err).message, 'Erreur texte simple')
})

test('apiErrorMessage: raccourci message-seul (compat lib/toast.js)', () => {
  const err = { response: { status: 400, data: { detail: 'X' } } }
  assert.equal(apiErrorMessage(err), 'X')
})
