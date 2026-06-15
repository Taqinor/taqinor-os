// Régression « aperçu devis cassé » (panneau lead).
// Exécutés en CI : node --test src/features/ventes/previewPdf.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { proposalParams, pdfBlob, PDF_MIME } from './previewPdf.js'

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
