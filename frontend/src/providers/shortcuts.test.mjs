import test from 'node:test'
import assert from 'node:assert/strict'
import { GOTO_SHORTCUTS, GLOBAL_SHORTCUTS, isTypingTarget } from './shortcuts.js'

test('isTypingTarget: vrai pour les champs de saisie', () => {
  assert.equal(isTypingTarget({ tagName: 'INPUT' }), true)
  assert.equal(isTypingTarget({ tagName: 'TEXTAREA' }), true)
  assert.equal(isTypingTarget({ tagName: 'SELECT' }), true)
  assert.equal(isTypingTarget({ tagName: 'DIV', isContentEditable: true }), true)
})

test('isTypingTarget: rôles ARIA de saisie', () => {
  const mk = (role) => ({ tagName: 'DIV', getAttribute: (a) => (a === 'role' ? role : null) })
  assert.equal(isTypingTarget(mk('textbox')), true)
  assert.equal(isTypingTarget(mk('combobox')), true)
  assert.equal(isTypingTarget(mk('searchbox')), true)
  assert.equal(isTypingTarget(mk('button')), false)
})

test('isTypingTarget: faux pour le reste et tolère null', () => {
  assert.equal(isTypingTarget({ tagName: 'BUTTON' }), false)
  assert.equal(isTypingTarget({ tagName: 'DIV' }), false)
  assert.equal(isTypingTarget(null), false)
})

test('GOTO_SHORTCUTS: bien formés (keys "g x" + route absolue + libellé)', () => {
  assert.ok(GOTO_SHORTCUTS.length >= 4)
  for (const s of GOTO_SHORTCUTS) {
    assert.match(s.keys, /^g [a-z]$/)
    assert.ok(s.to.startsWith('/'))
    assert.ok(s.label && s.label.length > 0)
  }
  // pas de lettre de raccourci en double
  const letters = GOTO_SHORTCUTS.map((s) => s.keys.split(' ')[1])
  assert.equal(new Set(letters).size, letters.length)
})

test('GLOBAL_SHORTCUTS: contient ⌘K et ?', () => {
  const keys = GLOBAL_SHORTCUTS.map((s) => s.keys)
  assert.ok(keys.some((k) => k.includes('K')))
  assert.ok(keys.includes('?'))
})
