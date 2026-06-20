import test from 'node:test'
import assert from 'node:assert/strict'
import {
  toNumber, formatMAD, formatNumber, formatPercent,
  formatDate, formatDateTime, formatPhoneMA, canonicalPhoneMA, normalizeMaPhone,
} from './format.js'

// Intl fr-FR utilise des espaces insécables variables (U+00A0 / U+202F) comme
// séparateur de milliers — on normalise pour des assertions stables.
const norm = (s) => s.replace(/[  \s]/g, ' ').trim()

test('toNumber: nombres, chaînes fr/en, invalides', () => {
  assert.equal(toNumber(1234.5), 1234.5)
  assert.equal(toNumber('1234.56'), 1234.56)
  assert.equal(toNumber('1 234,56'), 1234.56)
  assert.equal(toNumber('1.234,56'), 1234.56)
  assert.equal(toNumber('19 %'), 19)
  assert.equal(toNumber(''), null)
  assert.equal(toNumber(null), null)
  assert.equal(toNumber('abc'), null)
  assert.equal(toNumber(NaN), null)
})

// ERR106 — Sans virgule décimale, un point est un VRAI point décimal : un
// nombre technique « 1.234 » reste 1,234 et n'est PAS écrasé en 1234. Les
// points de milliers ne sont retirés que dans la notation fr (virgule présente).
test('toNumber: décimale « 1.234 » préservée (pas un séparateur de milliers)', () => {
  assert.equal(toNumber('1.234'), 1.234)
  assert.equal(toNumber('0.500'), 0.5)
  assert.equal(toNumber('12.000'), 12) // vraie décimale .000
  // Notation fr avec virgule : le point RESTE un séparateur de milliers.
  assert.equal(toNumber('1.234,5'), 1234.5)
  assert.equal(toNumber('1.234.567,89'), 1234567.89)
})

test('formatMAD: 2 décimales + suffixe MAD, tiret si invalide', () => {
  assert.equal(norm(formatMAD(1234.5)), '1 234,50 MAD')
  assert.equal(norm(formatMAD(0)), '0,00 MAD')
  assert.equal(norm(formatMAD('1234.5', { decimals: 0 })), '1 235 MAD')
  assert.equal(norm(formatMAD(1000, { withSymbol: false })), '1 000,00')
  assert.equal(formatMAD(null), '—')
  assert.equal(formatMAD('xx'), '—')
})

test('formatNumber + formatPercent', () => {
  assert.equal(norm(formatNumber(1234567)), '1 234 567')
  assert.equal(norm(formatNumber(3.14159, { decimals: 2 })), '3,14')
  assert.equal(norm(formatPercent(19)), '19 %')
  assert.equal(norm(formatPercent(0.5, { decimals: 1 })), '0,5 %')
  assert.equal(formatPercent(null), '—')
})

test('formatDate / formatDateTime jj/mm/aaaa', () => {
  const iso = '2026-06-18T14:05:00Z'
  assert.equal(formatDate('2026-06-18'), '18/06/2026')
  assert.match(formatDate(iso, { long: true }), /juin 2026/)
  assert.match(formatDateTime(iso), /18\/06\/2026/)
  assert.equal(formatDate(null), '—')
  assert.equal(formatDate('pas une date'), '—')
})

test('formatPhoneMA: local + international', () => {
  assert.equal(formatPhoneMA('0612345678'), '06 12 34 56 78')
  assert.equal(formatPhoneMA('06 12-34 56 78'), '06 12 34 56 78')
  assert.equal(formatPhoneMA('+212612345678'), '+212 6 12 34 56 78')
  assert.equal(formatPhoneMA('00212612345678'), '+212 6 12 34 56 78')
  assert.equal(formatPhoneMA('212612345678'), '+212 6 12 34 56 78')
  assert.equal(formatPhoneMA(''), '')
  // non reconnu → renvoyé tel quel, sans exception
  assert.equal(formatPhoneMA('1234'), '1234')
})

test('canonicalPhoneMA: forme de stockage/dédup', () => {
  assert.equal(canonicalPhoneMA('0612345678'), '+212612345678')
  assert.equal(canonicalPhoneMA('+212 6 12 34 56 78'), '+212612345678')
  assert.equal(canonicalPhoneMA('06 12-34 56 78'), '+212612345678')
  assert.equal(canonicalPhoneMA('0712345678'), '+212712345678')
  assert.equal(canonicalPhoneMA(''), '')
})

// L853 — miroir exact de normalize_ma_phone (apps/ventes/utils/phone.py) :
// sert à valider/désactiver le bouton WhatsApp côté front.
test('normalizeMaPhone: format wa.me 212XXXXXXXXX ou null', () => {
  assert.equal(normalizeMaPhone('0612345678'), '212612345678')
  assert.equal(normalizeMaPhone('+212612345678'), '212612345678')
  assert.equal(normalizeMaPhone(' +212 (6) 12-34-56-78 '), '212612345678')
  assert.equal(normalizeMaPhone('00212612345678'), '212612345678')
  assert.equal(normalizeMaPhone('612345678'), '212612345678')
  // vide / non normalisable → null (bouton désactivé)
  assert.equal(normalizeMaPhone(''), null)
  assert.equal(normalizeMaPhone(null), null)
  assert.equal(normalizeMaPhone('   '), null)
  assert.equal(normalizeMaPhone('abc'), null)
})
