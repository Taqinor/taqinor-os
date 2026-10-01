import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildWaUrl, telHref, waHref } from './contactLinks.js'

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

// QJR635 — LE constructeur wa.me unique, qui NORMALISE le numéro.
test('waHref: un numéro local marocain prend son indicatif (06… → 2126…) et le texte', () => {
  assert.equal(waHref('06 61 23 45 67', 'x'), 'https://wa.me/212661234567?text=x')
})

test('waHref: un numéro déjà international (sans +) est gardé tel quel', () => {
  assert.equal(waHref('8613812345678'), 'https://wa.me/8613812345678')
})

test('waHref: trop court / inexploitable → null', () => {
  assert.equal(waHref('12'), null)
  assert.equal(waHref('abc'), null)
})

test('buildWaUrl: sans numéro → null ; sans texte → pas de ?text=', () => {
  assert.equal(buildWaUrl(null, 'x'), null)
  assert.equal(buildWaUrl('212661234567'), 'https://wa.me/212661234567')
  assert.equal(buildWaUrl('212661234567', 'a b'), 'https://wa.me/212661234567?text=a%20b')
})
