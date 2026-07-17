import test from 'node:test'
import assert from 'node:assert/strict'
import {
  GOTO_SHORTCUTS, GLOBAL_SHORTCUTS, CREATE_SHORTCUTS, EDIT_SHORTCUTS,
  isTypingTarget, isMacPlatform, quickSearchShortcutLabel, filterShortcutGroups,
} from './shortcuts.js'

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

test('GLOBAL_SHORTCUTS: contient un raccourci "K" (⌘ ou Ctrl selon plateforme) et ?', () => {
  const keys = GLOBAL_SHORTCUTS.map((s) => s.keys)
  assert.ok(keys.some((k) => k.includes('K')))
  assert.ok(keys.includes('?'))
})

// VX73 — la plateforme RÉELLE de l'ERP est Windows/Linux : le glyphe ⌘ codé en
// dur mentait. quickSearchShortcutLabel() détecte la plateforme au lieu de
// supposer macOS.
test('isMacPlatform: détecte macOS via navigator.platform', () => {
  assert.equal(isMacPlatform({ platform: 'MacIntel' }), true)
  assert.equal(isMacPlatform({ platform: 'Win32' }), false)
  assert.equal(isMacPlatform({ platform: 'Linux x86_64' }), false)
  assert.equal(isMacPlatform(null), false)
  assert.equal(isMacPlatform(undefined), false)
})

test('isMacPlatform: retombe sur navigator.userAgentData.platform si présent', () => {
  assert.equal(isMacPlatform({ userAgentData: { platform: 'macOS' } }), true)
  assert.equal(isMacPlatform({ userAgentData: { platform: 'Windows' } }), false)
})

test('quickSearchShortcutLabel: "⌘ K" sur Mac, "Ctrl K" sur Windows/Linux (la plateforme réelle de l\'ERP)', () => {
  assert.equal(quickSearchShortcutLabel({ platform: 'MacIntel' }), '⌘ K')
  assert.equal(quickSearchShortcutLabel({ platform: 'Win32' }), 'Ctrl K')
  assert.equal(quickSearchShortcutLabel({ platform: 'Linux x86_64' }), 'Ctrl K')
})

// NTUX18 — cheatsheet enrichie : raccourcis d'édition (NTUX8) + recherche EN
// DIRECT filtrant les groupes de la cheatsheet.
test('EDIT_SHORTCUTS: bien formés (keys + libellé), couvre Tab/Maj+Tab/Entrée/Échap', () => {
  assert.ok(EDIT_SHORTCUTS.length >= 4)
  for (const s of EDIT_SHORTCUTS) {
    assert.ok(s.keys && s.keys.length > 0)
    assert.ok(s.label && s.label.length > 0)
  }
  const keys = EDIT_SHORTCUTS.map((s) => s.keys)
  assert.ok(keys.includes('Tab'))
  assert.ok(keys.includes('Entrée'))
  assert.ok(keys.includes('Échap'))
})

test('filterShortcutGroups: requête vide renvoie tous les groupes inchangés', () => {
  const groups = [{ title: 'Créer', items: CREATE_SHORTCUTS }, { title: 'Édition', items: EDIT_SHORTCUTS }]
  assert.deepEqual(filterShortcutGroups(groups, ''), groups)
  assert.deepEqual(filterShortcutGroups(groups, '   '), groups)
})

test('filterShortcutGroups: "créer" filtre vers les raccourcis de création (insensible à la casse)', () => {
  const groups = [
    { title: 'Créer', items: CREATE_SHORTCUTS },
    { title: 'Édition', items: EDIT_SHORTCUTS },
  ]
  const result = filterShortcutGroups(groups, 'CRÉER')
  assert.equal(result.length, 1)
  assert.equal(result[0].title, 'Créer')
  assert.equal(result[0].items.length, CREATE_SHORTCUTS.length)
})

test('filterShortcutGroups: un groupe sans correspondance disparaît entièrement', () => {
  const groups = [
    { title: 'Créer', items: CREATE_SHORTCUTS },
    { title: 'Édition', items: EDIT_SHORTCUTS },
  ]
  const result = filterShortcutGroups(groups, 'cellule')
  assert.deepEqual(result.map((g) => g.title), ['Édition'])
})

test('filterShortcutGroups: aucune correspondance nulle part renvoie une liste vide', () => {
  const groups = [{ title: 'Créer', items: CREATE_SHORTCUTS }]
  assert.deepEqual(filterShortcutGroups(groups, 'zzz-introuvable'), [])
})
