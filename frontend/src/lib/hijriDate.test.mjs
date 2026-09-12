import test from 'node:test'
import assert from 'node:assert/strict'
import { formatHijriDate, formatWithHijri, shouldShowHijri } from './hijriDate.js'

/* NTI18N12 — conversion d'affichage grégorien -> hégirien (calendrier
   islamique NATIF d'Intl, umalqura). Les valeurs de référence ci-dessous
   sont calculées par le MÊME moteur ICU que celui utilisé en production
   (Node embarque ICU complet) — jamais une valeur inventée à la main. */

test('formatHijriDate: conversion réelle (calendrier umalqura ICU)', () => {
  // 2026-03-15 -> 26 ramadan 1447 (vérifié via Intl.DateTimeFormat ICU direct).
  assert.equal(formatHijriDate('2026-03-15T00:00:00Z'), '26 Ramadan 1447')
})

test('formatHijriDate: null pour une valeur non parseable, jamais d’exception', () => {
  assert.equal(formatHijriDate('pas une date'), null)
  assert.equal(formatHijriDate(null), null)
  assert.equal(formatHijriDate(undefined), null)
})

test('formatWithHijri: hégirien EN PLUS de la date grégorienne ISO, jamais en remplacement', () => {
  const rendu = formatWithHijri('2026-03-15T00:00:00Z')
  assert.equal(rendu, '26 Ramadan 1447 (2026-03-15)')
  // La date grégorienne ISO reste bien présente, intacte, dans le rendu.
  assert.match(rendu, /\(2026-03-15\)$/)
})

test('formatWithHijri: null pour une valeur non parseable', () => {
  assert.equal(formatWithHijri('nawak'), null)
})

test('shouldShowHijri: exige les DEUX conditions (locale=ar ET préférence active)', () => {
  assert.equal(shouldShowHijri({ locale: 'ar', calendrierHegirien: true }), true)
  assert.equal(shouldShowHijri({ locale: 'fr', calendrierHegirien: true }), false)
  assert.equal(shouldShowHijri({ locale: 'ar', calendrierHegirien: false }), false)
  assert.equal(shouldShowHijri({ locale: 'en', calendrierHegirien: true }), false)
  assert.equal(shouldShowHijri({ locale: 'ar' }), false)
  assert.equal(shouldShowHijri({}), false)
})
