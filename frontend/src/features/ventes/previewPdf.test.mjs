// Régression « aperçu devis cassé » (panneau lead).
// Exécutés en CI : node --test src/features/ventes/previewPdf.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  proposalParams, pdfBlob, PDF_MIME,
  previewView, classifyFetchError, PREVIEW_VIEW,
} from './previewPdf.js'

test('proposalParams : Premium = full, étude respectée', () => {
  assert.deepEqual(proposalParams('full', false), {
    pdf_mode: 'full', include_etude: 0,
  })
  assert.deepEqual(proposalParams('full', true), {
    pdf_mode: 'full', include_etude: 1,
  })
})

test('proposalParams : 1 page = onepage, et n’envoie JAMAIS l’étude', () => {
  assert.deepEqual(proposalParams('onepage', false), {
    pdf_mode: 'onepage', include_etude: 0,
  })
  // include_etude n’a pas de sens en 1 page : forcé à 0 même si coché.
  assert.deepEqual(proposalParams('onepage', true), {
    pdf_mode: 'onepage', include_etude: 0,
  })
})

test('proposalParams : tout mode inconnu retombe sur Premium (full)', () => {
  assert.equal(proposalParams(undefined, false).pdf_mode, 'full')
  assert.equal(proposalParams('', true).pdf_mode, 'full')
})

test('pdfBlob : emballe les octets en Blob application/pdf affichable', async () => {
  // Octets façon réponse axios responseType:'blob' (en-tête %PDF d’un vrai PDF).
  const bytes = new TextEncoder().encode('%PDF-1.7\n…octets…')
  const blob = pdfBlob(bytes)
  assert.equal(blob.type, PDF_MIME, 'le type DOIT être application/pdf')
  assert.equal(blob.size, bytes.byteLength)
  // Le contenu transite intact -> l’iframe affiche le PDF, pas une icône cassée.
  const head = new Uint8Array(await blob.arrayBuffer()).subarray(0, 5)
  assert.deepEqual([...head], [...new TextEncoder().encode('%PDF-')])
})

// ── Repli gracieux quand l'aperçu inline ne se rend pas ──────────────────────

test('previewView : aperçu bloqué (bloqueur/timeout) -> REPLI, pas le PDF brut', () => {
  // Le fetch a réussi (hasUrl) mais l'iframe ne s'est pas rendue (bloquée).
  // On NE doit PAS rester sur le cadre PDF/bloqué : on bascule sur le repli.
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: true, hasUrl: true }),
    PREVIEW_VIEW.FALLBACK,
  )
})

test('previewView : échec réseau du fetch -> REPLI (téléchargeable)', () => {
  // Pas d'URL (le fetch a échoué côté réseau) mais blocked=true -> repli.
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: true, hasUrl: false }),
    PREVIEW_VIEW.FALLBACK,
  )
})

test('previewView : rendu normal -> PDF ; chargement -> LOADING', () => {
  assert.equal(
    previewView({ loading: false, serverError: false, blocked: false, hasUrl: true }),
    PREVIEW_VIEW.PDF,
  )
  assert.equal(
    previewView({ loading: true, serverError: false, blocked: false, hasUrl: false }),
    PREVIEW_VIEW.LOADING,
  )
})

test('previewView : vrai échec serveur prime et reste un message d’ERREUR distinct', () => {
  // Un 4xx/5xx réel (PDF impossible à générer) ne doit PAS devenir le repli
  // "bloqueur" : il garde son message clair, même si blocked était vrai.
  assert.equal(
    previewView({ loading: false, serverError: true, blocked: true, hasUrl: false }),
    PREVIEW_VIEW.ERROR,
  )
})

test('classifyFetchError : réponse HTTP 4xx/5xx = serveur ; sinon réseau', () => {
  assert.equal(classifyFetchError({ response: { status: 500 } }), 'server')
  assert.equal(classifyFetchError({ response: { status: 404 } }), 'server')
  // Timeout / connexion coupée : pas de réponse -> réseau (repli gracieux).
  assert.equal(classifyFetchError({ code: 'ECONNABORTED' }), 'network')
  assert.equal(classifyFetchError({ request: {} }), 'network')
  assert.equal(classifyFetchError(undefined), 'network')
})
