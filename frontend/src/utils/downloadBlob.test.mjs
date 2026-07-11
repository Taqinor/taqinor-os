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

// VX81 — stampedFilename : nom de fichier horodaté pour les exports tableur
// (pas de Content-Disposition serveur à lire). Deux exports le même jour
// doivent produire deux noms distincts (base différente ou société différente).
test('le nom contient la date AAAAMMJJ', () => {
  const d = new Date(2026, 6, 11) // 11 juillet 2026 (mois 0-indexé)
  assert.equal(
    stampedFilename('analyse-achats', 'xlsx', 'TAQINOR', d),
    'analyse-achats_TAQINOR_20260711.xlsx')
})

test('deux exports (bases différentes) le même jour = deux noms distincts', () => {
  const d = new Date(2026, 6, 11)
  const a = stampedFilename('mouvements-stock', 'xlsx', 'TAQINOR', d)
  const b = stampedFilename('mouvements-agregation', 'xlsx', 'TAQINOR', d)
  assert.notEqual(a, b)
})

test('societe absente : repli silencieux (pas de segment vide ni "undefined")', () => {
  const d = new Date(2026, 6, 11)
  assert.equal(stampedFilename('FEC', 'txt', undefined, d), 'FEC_20260711.txt')
  assert.equal(stampedFilename('FEC', 'txt', '', d), 'FEC_20260711.txt')
})

test('slugifie les caractères spéciaux/accents de la société', () => {
  const d = new Date(2026, 6, 11)
  assert.equal(
    stampedFilename('etat', 'csv', "Société d'Énergie & Co.", d),
    'etat_Societe-d-Energie-Co_20260711.csv')
})

test('extension acceptée avec ou sans point initial', () => {
  const d = new Date(2026, 6, 11)
  assert.equal(stampedFilename('x', '.csv', 'ACME', d), 'x_ACME_20260711.csv')
  assert.equal(stampedFilename('x', 'csv', 'ACME', d), 'x_ACME_20260711.csv')
})
