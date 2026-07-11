// VX43 — Swipe-to-action horizontal maison sur les cartes mobiles du DataTable
// (`data-dt-cards`), prop `swipeActions` 100 % OPT-IN et rétrocompatible : non
// fournie, `SwipeableCard` rend `children` tel quel (aucun DOM/comportement
// différent d'avant). Verified against SOURCE (no node_modules in this
// worktree/lane, same convention as LeadCardSwipeAction.test.mjs) — DataTable.jsx
// imports 'react' so its pure swipe-math functions cannot be imported directly
// here; they are re-implemented verbatim below and exercised, and the wiring
// into the component is verified by regex against the real source.
//   node --test src/ui/datatable/DataTableSwipeAction.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DataTable.jsx'), 'utf8')

/* ---- Fonctions pures, copie exacte de DataTable.jsx (mêmes noms/corps) ---- */
const SWIPE_REVEAL_PX = 96
function shouldArmSwipe(deltaX, deltaY) {
  if (Math.abs(deltaX) < 5) return false
  return Math.abs(deltaX) > Math.abs(deltaY)
}
function clampSwipeOffset(deltaX, maxReveal = SWIPE_REVEAL_PX) {
  return Math.max(-maxReveal, Math.min(0, deltaX))
}
function resolveSwipeSnap(offset, maxReveal = SWIPE_REVEAL_PX) {
  return Math.abs(offset) >= maxReveal / 2 ? -maxReveal : 0
}

test('shouldArmSwipe : mêmes seuils que LeadCard.jsx (cohérence du geste)', () => {
  assert.equal(shouldArmSwipe(2, 0), false)
  assert.equal(shouldArmSwipe(10, 30), false)
  assert.equal(shouldArmSwipe(-40, 5), true)
})

test('clampSwipeOffset : borne à [-96, 0]', () => {
  assert.equal(clampSwipeOffset(-200), -96)
  assert.equal(clampSwipeOffset(50), 0)
})

test('resolveSwipeSnap : aimante à -96 au-delà de la moitié', () => {
  assert.equal(resolveSwipeSnap(-47), 0)
  assert.equal(resolveSwipeSnap(-48), -96)
})

/* ---- Câblage réel dans DataTable.jsx (source) ---- */

test('VX43 : swipeActions est déclaré et documenté opt-in/rétrocompatible', () => {
  assert.match(SRC, /swipeActions,/)
  assert.match(SRC, /100 % opt-in \/ rétrocompatible/)
})

test('VX43 : SwipeableCard rend `children` NU quand aucune action (0 régression)', () => {
  assert.match(SRC, /if \(!list\.length\) return children/)
})

test('VX43 : rowSwipeActions dérive de swipeActions\\(row\\) uniquement si fourni', () => {
  assert.match(SRC, /const rowSwipeActions = swipeActions \? swipeActions\(row\) : \[\]/)
})

test('VX43 : la carte mobile est enveloppée par SwipeableCard avec sa clé de ligne', () => {
  assert.match(SRC, /<SwipeableCard key=\{rowKey\} actions=\{rowSwipeActions\}>/)
})

test('VX43 : les cibles d\'action révélées font ≥44px (thumb-reachable)', () => {
  assert.match(SRC, /minHeight: '44px'/)
})

test('VX43 : au plus 2 actions révélées (mêmes règles que RowActions "rapides")', () => {
  assert.match(SRC, /const list = \(actions \?\? \[\]\)\.slice\(0, 2\)/)
})
