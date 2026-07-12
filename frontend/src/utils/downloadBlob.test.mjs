// QD2 — filenameFromResponse : lit le nom cohérent posé par le serveur dans
// l'en-tête Content-Disposition (TAQINOR_Facture_Client_FAC-….pdf), sinon repli.
// Exécuté en CI : node --test src/utils/downloadBlob.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { filenameFromResponse, stampedFilename } from './downloadBlob.js'

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

// VX81 — stampedFilename : le nom contient toujours la date du jour (format
// AAAAMMJJ), et deux exports le même jour ne se confondent plus derrière un
// (1)/(2) de navigateur dès que la société diffère (ou que l'appelant varie
// la base). Deux exports STRICTEMENT identiques (même base/ext/société) le
// même jour restent volontairement homonymes — le navigateur gère déjà ce cas
// (téléchargement en double, jamais un export réellement différent).
test('stampedFilename : contient la date du jour AAAAMMJJ', () => {
  const today = new Date()
  const stamp = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`
  const name = stampedFilename('analyse-achats', 'xlsx', 'TAQINOR Démo')
  assert.match(name, new RegExp(`_${stamp}\\.xlsx$`))
})

test('stampedFilename : deux exports de bases différentes le même jour donnent deux noms distincts', () => {
  const a = stampedFilename('mouvements-stock', 'xlsx', 'TAQINOR Démo')
  const b = stampedFilename('mouvements-agregation', 'xlsx', 'TAQINOR Démo')
  assert.notEqual(a, b)
})

test('stampedFilename : slugifie la société (accents/espaces) sans casser le nom', () => {
  const name = stampedFilename('liasse-fiscale', 'csv', 'Société Générale & Co')
  assert.match(name, /^liasse-fiscale_Societe-Generale-Co_\d{8}\.csv$/)
})

test('stampedFilename : société absente → repli propre sur base + date', () => {
  const name = stampedFilename('provisions-fnp-fae', 'csv')
  assert.match(name, /^provisions-fnp-fae_\d{8}\.csv$/)
})

test('stampedFilename : accepte une extension avec ou sans point de tête', () => {
  assert.equal(
    stampedFilename('x', 'csv').split('.').pop(),
    stampedFilename('x', '.csv').split('.').pop(),
  )
})
