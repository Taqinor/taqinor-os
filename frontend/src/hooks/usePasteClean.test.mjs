// VX237 — Collage intelligent : parseurs purs exécutés réellement (module
// `lib/paste.js`, aucune dépendance React, donc testable tel quel avec
// `node --test`, sans node_modules/vitest requis dans ce worktree/lane).
//   node --test src/hooks/usePasteClean.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { parsePastedPhone, parsePastedAmount, parsePasteCard } from '../lib/paste.js'

test('VX237 — téléphone : "+212 6-12.34.56.78" stocke la forme canonique', () => {
  assert.equal(parsePastedPhone('+212 6-12.34.56.78'), '+212612345678')
})

test('VX237 — téléphone : 8 formats réels reconnus', () => {
  const cases = [
    ['0612345678', '+212612345678'],
    ['06 12 34 56 78', '+212612345678'],
    ['06.12.34.56.78', '+212612345678'],
    ['06-12-34-56-78', '+212612345678'],
    ['+212612345678', '+212612345678'],
    ['+212 6 12 34 56 78', '+212612345678'],
    ['00212612345678', '+212612345678'],
    ['0712345678', '+212712345678'],
  ]
  for (const [input, expected] of cases) {
    assert.equal(parsePastedPhone(input), expected, `input: ${input}`)
  }
})

test('VX237 — téléphone : texte non reconnaissable renvoie null (jamais de valeur inventée)', () => {
  assert.equal(parsePastedPhone('Ahmed Alami'), null)
  assert.equal(parsePastedPhone(''), null)
  assert.equal(parsePastedPhone('123'), null)
})

test('VX237 — montant : "12 500,00" donne "12500"', () => {
  assert.equal(parsePastedAmount('12 500,00'), '12500')
})

test('VX237 — montant : formats Excel/DH réels', () => {
  const cases = [
    ['12 500,00', '12500'],
    ['12500', '12500'],
    ['12500 DH', '12500'],
    ['12 500 MAD', '12500'],
    ['12.500,50', '12500.5'],
    ['1250,5', '1250.5'],
    ['  9000  ', '9000'],
    ['3 200,00 dh', '3200'],
  ]
  for (const [input, expected] of cases) {
    assert.equal(parsePastedAmount(input), expected, `input: ${input}`)
  }
})

test('VX237 — montant : texte non numérique renvoie null', () => {
  assert.equal(parsePastedAmount('Ahmed Alami'), null)
  assert.equal(parsePastedAmount(''), null)
})

test('VX237 — carte de visite : "Nom Ahmed Alami Tel 0612345678" détecte nom + téléphone', () => {
  const result = parsePasteCard('Nom Ahmed Alami\nTel 0612345678')
  assert.deepEqual(result, { nom: 'Ahmed Alami', telephone: '+212612345678' })
})

test('VX237 — carte de visite : sans téléphone reconnaissable renvoie null (jamais de répartition silencieuse)', () => {
  assert.equal(parsePasteCard('Ahmed Alami'), null)
})
