// QD2 — filenameFromResponse : lit le nom cohérent posé par le serveur dans
// l'en-tête Content-Disposition (TAQINOR_Facture_Client_FAC-….pdf), sinon repli.
// Exécuté en CI : node --test src/utils/downloadBlob.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { filenameFromResponse } from './downloadBlob.js'

test('lit filename="…" de Content-Disposition', () => {
  const res = {
    headers: {
      'content-disposition':
        'inline; filename="TAQINOR_Facture_Reda-Kasri_FAC-202607-0001.pdf"',
    },
  }
  assert.equal(
    filenameFromResponse(res, 'x.pdf'),
    'TAQINOR_Facture_Reda-Kasri_FAC-202607-0001.pdf')
})

test('gère filename* RFC 5987 (UTF-8)', () => {
  const res = {
    headers: {
      'content-disposition':
        "attachment; filename*=UTF-8''TAQINOR_Devis_Client_DEV-1.pdf",
    },
  }
  assert.equal(
    filenameFromResponse(res, 'x.pdf'), 'TAQINOR_Devis_Client_DEV-1.pdf')
})

test('gère les headers via getter (Headers-like)', () => {
  const res = {
    headers: {
      get: (k) => (k === 'content-disposition'
        ? 'inline; filename="A_B_C.pdf"' : null),
    },
  }
  assert.equal(filenameFromResponse(res, 'x.pdf'), 'A_B_C.pdf')
})

test('repli sur le fallback quand aucun header', () => {
  assert.equal(filenameFromResponse({}, 'DEV-1.pdf'), 'DEV-1.pdf')
  assert.equal(filenameFromResponse(null, 'DEV-1.pdf'), 'DEV-1.pdf')
  assert.equal(filenameFromResponse(undefined), 'document.pdf')
})
