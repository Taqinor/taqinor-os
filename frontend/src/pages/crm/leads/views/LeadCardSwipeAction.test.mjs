// VX43 — Swipe-to-action horizontal maison sur LeadCard.jsx (touchstart/move/
// end, zéro dépendance, seuil de distance anti-scroll) qui révèle
// Appeler/WhatsApp en grand (≥44px) — les liens tel:/wa.me existaient déjà
// (kb-card-contact) mais en texte 12px noyé dans la carte. Verified against
// SOURCE (no node_modules in this worktree/lane, same convention as
// LeadCardFirstTouchTimer.test.mjs / LeadCardReadinessChips.test.mjs).
//   node --test src/pages/crm/leads/views/LeadCardSwipeAction.test.mjs
//
// The pure swipe-math functions (shouldArmSwipe/clampSwipeOffset/
// resolveSwipeSnap) are ALSO re-implemented verbatim below and exercised
// directly (not just grepped) so their actual arithmetic is proven correct —
// they cannot be imported from LeadCard.jsx under plain `node --test` because
// that file imports 'react' (absent here, no node_modules in this lane).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

/* ---- Fonctions pures, copie exacte de LeadCard.jsx (mêmes noms/corps) ---- */
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

test('shouldArmSwipe : refuse un micro-mouvement (< 5px)', () => {
  assert.equal(shouldArmSwipe(2, 0), false)
  assert.equal(shouldArmSwipe(-3, 0), false)
})

test('shouldArmSwipe : refuse un geste surtout vertical (anti-scroll)', () => {
  assert.equal(shouldArmSwipe(10, 30), false)
  assert.equal(shouldArmSwipe(-10, -30), false)
})

test('shouldArmSwipe : arme un geste nettement horizontal', () => {
  assert.equal(shouldArmSwipe(-40, 5), true)
  assert.equal(shouldArmSwipe(40, -2), true)
})

test('clampSwipeOffset : borne à [-96, 0], jamais de révélation vers la droite', () => {
  assert.equal(clampSwipeOffset(-200), -96)
  assert.equal(clampSwipeOffset(-30), -30)
  assert.equal(clampSwipeOffset(50), 0) // un balayage vers la droite ne fait rien
  assert.equal(clampSwipeOffset(0), 0)
})

test('resolveSwipeSnap : aimante à -96 au-delà de la moitié, sinon referme à 0', () => {
  assert.equal(resolveSwipeSnap(-10), 0)
  assert.equal(resolveSwipeSnap(-47), 0)
  assert.equal(resolveSwipeSnap(-48), -96)
  assert.equal(resolveSwipeSnap(-96), -96)
})

/* ---- Câblage réel dans LeadCard.jsx (source) ---- */

test('VX43 : useSwipeReveal ne s\'active que si tel/wa existe', () => {
  assert.match(SRC, /const swipe = useSwipeReveal\(!!\(tel \|\| wa\)\)/)
})

test('VX43 : la carte porte les handlers tactiles + la transform révélée', () => {
  assert.match(SRC, /\{\.\.\.swipe\.handlers\}/)
  assert.match(SRC, /transform: swipe\.offset \? `translateX\(\$\{swipe\.offset\}px\)` : undefined/)
})

test('VX43 : les cibles Appeler/WhatsApp révélées font ≥44px (thumb-reachable)', () => {
  assert.match(SRC, /minHeight: '44px'/)
})

test('VX43 : un clic sur l\'action révélée referme le panneau (stopPropagation + close)', () => {
  assert.match(SRC, /onClick=\{\(e\) => \{ e\.stopPropagation\(\); swipe\.close\(\) \}\}/)
})

test('VX43 : aucune dépendance externe importée pour le geste (zéro dépendance)', () => {
  assert.doesNotMatch(SRC, /from ['"]react-swipeable['"]/)
  assert.doesNotMatch(SRC, /from ['"]@use-gesture/)
})
