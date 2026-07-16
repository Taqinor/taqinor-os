import { test } from 'node:test'
import assert from 'node:assert/strict'
import { telHref, waHref } from './contactLinks.js'

// VX108 — tap-to-call partagé (extrait de LeadCard.jsx).

test('telHref: nettoie un numéro FR local en tel: (chiffres + éventuel +)', () => {
  assert.equal(telHref('06 12 34 56 78'), 'tel:0612345678')
})

test('telHref: conserve le + initial d un numéro international', () => {
  assert.equal(telHref('+212 6 12 34 56 78'), 'tel:+212612345678')
})

test('telHref: null/undefined/vide/espaces → null', () => {
  assert.equal(telHref(null), null)
  assert.equal(telHref(undefined), null)
  assert.equal(telHref(''), null)
  assert.equal(telHref('   '), null)
})

test('telHref: une chaîne sans aucun chiffre → null', () => {
  assert.equal(telHref('abc'), null)
})

test('waHref: ne garde que les chiffres pour wa.me (pas de +)', () => {
  assert.equal(waHref('+212 6 12 34 56 78'), 'https://wa.me/212612345678')
})

test('waHref: null/undefined/vide → null', () => {
  assert.equal(waHref(null), null)
  assert.equal(waHref(undefined), null)
  assert.equal(waHref(''), null)
})
