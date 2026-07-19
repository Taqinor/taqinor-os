// LB11 — Prédicats purs du drag-to-pan (features/kanban/usePanScroll.js).
// Zéro import React/DOM réel : réellement exécutable ici.
//   node --test src/features/kanban/panScrollPredicates.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PAN_IGNORE_SELECTOR,
  PAN_ACTIVATION_DISTANCE_PX,
  shouldIgnorePanStart,
  isPannablePointerType,
  exceedsPanThreshold,
} from './panScrollPredicates.js'

// Mini-fac-similé DOM : `.closest(selector)` renvoie `this` si `selector`
// figure dans `matches` (liste des sélecteurs que l'élément fictif "satisfait"),
// sinon `null` — suffisant pour exercer `shouldIgnorePanStart` sans jsdom.
function fakeElement(matches = []) {
  return {
    matches,
    closest(selector) {
      // `selector` est la liste combinée `PAN_IGNORE_SELECTOR` — on simule le
      // comportement réel de `Element.closest` : match si AU MOINS un des
      // sélecteurs simples de la liste correspond à `matches`.
      const parts = selector.split(',').map((s) => s.trim())
      return parts.some((p) => matches.includes(p)) ? this : null
    },
  }
}

test('LB11 : shouldIgnorePanStart — ignore les cibles listées (carte, colonne, contrôles)', () => {
  for (const sel of PAN_IGNORE_SELECTOR.split(',').map((s) => s.trim())) {
    assert.equal(shouldIgnorePanStart(fakeElement([sel])), true, `devrait ignorer ${sel}`)
  }
})

test('LB11 : shouldIgnorePanStart — le fond vide du board arme le pan', () => {
  assert.equal(shouldIgnorePanStart(fakeElement(['.kb-board'])), false)
  assert.equal(shouldIgnorePanStart(fakeElement([])), false)
})

test('LB11 : shouldIgnorePanStart — défensif sur une cible absente/sans .closest', () => {
  assert.equal(shouldIgnorePanStart(null), false)
  assert.equal(shouldIgnorePanStart(undefined), false)
  assert.equal(shouldIgnorePanStart({}), false)
})

test('LB11 : isPannablePointerType — souris seulement (tactile/stylet scrollent nativement)', () => {
  assert.equal(isPannablePointerType('mouse'), true)
  assert.equal(isPannablePointerType('touch'), false)
  assert.equal(isPannablePointerType('pen'), false)
  assert.equal(isPannablePointerType(undefined), false)
})

test('LB11 : exceedsPanThreshold — seuil 4px par défaut, distance euclidienne', () => {
  assert.equal(exceedsPanThreshold(0, 0), false)
  assert.equal(exceedsPanThreshold(3, 0), false)
  assert.equal(exceedsPanThreshold(4, 0), true)
  assert.equal(exceedsPanThreshold(3, 3), true) // hypot(3,3) ≈ 4.24 ≥ 4
  assert.equal(exceedsPanThreshold(1, 1, 10), false)
  assert.equal(PAN_ACTIVATION_DISTANCE_PX, 4)
})
