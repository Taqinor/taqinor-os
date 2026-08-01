// VX43 — Swipe-to-action horizontal maison sur LeadCard.jsx (touchstart/move/
// end, zéro dépendance, seuil de distance anti-scroll) qui révèle
// Appeler/WhatsApp en grand (≥44px) — les liens tel:/wa.me existaient déjà
// (kb-card-contact) mais en texte 12px noyé dans la carte. Verified against
// SOURCE (no node_modules in this worktree/lane, same convention as
// LeadCardFirstTouchTimer.test.mjs / LeadCardReadinessChips.test.mjs).
//   node --test src/pages/crm/leads/views/LeadCardSwipeAction.test.mjs
//
// The pure swipe-math functions (resolveAxisLock/clampSwipeOffset/
// resolveSwipeSnap) are ALSO re-implemented verbatim below and exercised
// directly (not just grepped) so their actual arithmetic is proven correct —
// they cannot be imported from LeadCard.jsx under plain `node --test` because
// that file imports 'react' (absent here, no node_modules in this lane).
//
// VERROU D'AXE — `shouldArmSwipe` (|dx| >= 5 && |dx| > |dy|, RÉ-ÉVALUÉ à
// chaque touchmove) est remplacé par `resolveAxisLock`, décidé UNE SEULE fois
// par geste : pendant un scroll vertical, le bruit horizontal du pouce armait
// l'ancien seuil dès qu'une frame le franchissait, la carte suivait ce bruit,
// et le relâchement l'aimantait toute seule à -96px.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

/* ---- Fonctions pures, copie exacte de LeadCard.jsx (mêmes noms/corps) ---- */
const SWIPE_REVEAL_PX = 96
const AXIS_LOCK_PX = 10
const SWIPE_ARM_PX = 12
const SWIPE_ARM_RATIO = 1.5
function resolveAxisLock(deltaX, deltaY) {
  const dx = Math.abs(deltaX)
  const dy = Math.abs(deltaY)
  if (Math.max(dx, dy) < AXIS_LOCK_PX) return 'pending'
  if (dy >= dx) return 'rejected'
  return dx >= SWIPE_ARM_PX && dx > SWIPE_ARM_RATIO * dy ? 'armed' : 'pending'
}
function clampSwipeOffset(deltaX, maxReveal = SWIPE_REVEAL_PX) {
  return Math.max(-maxReveal, Math.min(0, deltaX))
}
function resolveSwipeSnap(offset, maxReveal = SWIPE_REVEAL_PX) {
  return Math.abs(offset) >= maxReveal / 2 ? -maxReveal : 0
}

test('resolveAxisLock : ne tranche RIEN tant qu\'aucun axe n\'a fait 10px', () => {
  assert.equal(resolveAxisLock(0, 0), 'pending')
  assert.equal(resolveAxisLock(9, 3), 'pending')
  assert.equal(resolveAxisLock(-3, -9), 'pending')
})

test('resolveAxisLock : un geste vertical est REJETÉ (le scroll possède le geste)', () => {
  assert.equal(resolveAxisLock(4, 30), 'rejected')
  assert.equal(resolveAxisLock(-25, -60), 'rejected')
  // Diagonale stricte : |dy| >= |dx| → le scroll gagne (jamais le swipe).
  assert.equal(resolveAxisLock(-20, -20), 'rejected')
})

test('resolveAxisLock : le BRUIT horizontal d\'un scroll vertical est rejeté (le bug)', () => {
  // Le pouce descend de 40px en dérivant de 8px : l'ancien shouldArmSwipe
  // n'armait pas ici, mais il se ré-évaluait à CHAQUE move — il suffisait
  // d'une seule frame plus horizontale que verticale pour armer. Le verrou
  // d'axe, lui, tombe sur 'rejected' au premier move et n'en sort plus.
  assert.equal(resolveAxisLock(8, 40), 'rejected')
  assert.equal(resolveAxisLock(14, 12), 'pending') // horizontal, mais mou → on attend
})

test('resolveAxisLock : n\'arme que sur un geste horizontal FRANC (>=12px et >1.5x |dy|)', () => {
  assert.equal(resolveAxisLock(-40, 5), 'armed')
  assert.equal(resolveAxisLock(40, -2), 'armed')
  // 12px pile, quasi pur horizontal → armé ; 11px → toujours en attente.
  assert.equal(resolveAxisLock(-12, 0), 'armed')
  assert.equal(resolveAxisLock(-11, 0), 'pending')
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

test('verrou d\'axe : l\'axe est décidé UNE fois par geste (ref), plus ré-évalué à chaque move', () => {
  // Plus aucun seuil ré-évalué : `shouldArmSwipe` a disparu au profit du
  // verrou à trois états, stocké dans une ref pour tenir tout le geste.
  assert.doesNotMatch(SRC, /shouldArmSwipe/)
  assert.match(SRC, /function resolveAxisLock\(deltaX, deltaY\)/)
  assert.match(SRC, /const axis = useRef\('pending'\)/)
  // Un geste rejeté sort IMMÉDIATEMENT du touchmove : rien ne peut le réarmer.
  assert.match(SRC, /if \(axis\.current === 'rejected'\) return/)
  // Le verrou n'est (re)posé qu'au touchstart.
  assert.match(SRC, /axis\.current = 'pending'\s*\n\s*setPhase\('idle'\)/)
})

test('verrou d\'axe : la transition 150ms n\'habille QUE l\'aimantation (jamais la traîne du doigt)', () => {
  // Pendant que le doigt traîne la carte, transform 1:1 sans transition —
  // sinon la carte arrive 150ms derrière le pouce. Hors geste tactile
  // ('idle'), la valeur d'origine est conservée : le desktop (aucun
  // touchevent, donc jamais autre chose que 'idle') est inchangé, transitions
  // de survol `.kb-card` comprises.
  assert.match(SRC, /transition: swipe\.phase === 'dragging' \? 'none' : 'transform 150ms ease'/)
  // 'dragging' n'est posé QUE sur un move déjà armé (jamais sur du bruit).
  assert.match(SRC, /if \(axis\.current !== 'armed'\) return\s*\n\s*\}\s*\n\s*setPhase\('dragging'\)/)
  // 'snapping' n'est posé qu'au relâchement d'un geste armé, et à la
  // fermeture après un tap sur une action révélée.
  assert.match(SRC, /if \(axis\.current === 'armed'\) \{[\s\S]{0,140}?setPhase\('snapping'\)/)
  assert.match(SRC, /const close = \(\) => \{ setPhase\('snapping'\); setOffset\(0\) \}/)
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

test('LB17 : la bande swipe cachée est INERTE (inert), plus seulement aria-hidden', () => {
  // recon-05 : aria-hidden seul laissait les <a> de la bande tabbables ;
  // `inert` (React 19) les sort du tab order + de l'interaction tant que le
  // panneau n'est pas révélé (offset === 0).
  assert.match(SRC, /aria-hidden=\{swipe\.offset === 0\}/)
  assert.match(SRC, /inert=\{swipe\.offset === 0\}/)
})
