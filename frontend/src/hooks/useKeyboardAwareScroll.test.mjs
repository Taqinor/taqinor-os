// VX51 — Le champ focalisé ne passe plus SOUS le clavier iOS (VisualViewport).
// Avant ce hook, `grep visualViewport` était néant : un champ bas de
// LeadForm/DevisGenerator restait caché derrière le clavier iOS (on tape sans
// voir). Verified against SOURCE (no node_modules in this worktree/lane —
// the hook imports 'react' for useEffect, unrunnable standalone without it).
// Real-device/WebKit keyboard behaviour remains a manual control (noted in
// the plan spec); this test locks the CONTRACT: listener wiring, no-op when
// the API is absent, and the two page-level mount points.
//   node --test src/hooks/useKeyboardAwareScroll.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const HOOK_SRC = readFileSync(join(HERE, 'useKeyboardAwareScroll.js'), 'utf8')
// LW37 — le point de montage lead a migré de LeadForm.jsx vers SectionsPane
// (le seul conteneur scrollable du cockpit sur mobile).
const SECTIONS_PANE_SRC = readFileSync(join(HERE, '../features/crm/workspace/SectionsPane.jsx'), 'utf8')
const DEVIS_GEN_SRC = readFileSync(join(HERE, '../pages/ventes/DevisGenerator.jsx'), 'utf8')

test('VX51 : exporte useKeyboardAwareScroll (default + nommé)', () => {
  assert.match(HOOK_SRC, /export function useKeyboardAwareScroll/)
  assert.match(HOOK_SRC, /export default useKeyboardAwareScroll/)
})

test('VX51 : no-op silencieux si visualViewport est absent — jamais de throw', () => {
  const start = HOOK_SRC.indexOf('useEffect(() => {')
  const block = HOOK_SRC.slice(start, start + 400)
  assert.match(block, /window\.visualViewport/)
  assert.match(block, /if \(!viewport\) return undefined/)
})

test('VX51 : écoute resize ET scroll sur visualViewport, et nettoie au démontage', () => {
  assert.match(HOOK_SRC, /viewport\.addEventListener\('resize', handleViewportChange\)/)
  assert.match(HOOK_SRC, /viewport\.addEventListener\('scroll', handleViewportChange\)/)
  assert.match(HOOK_SRC, /viewport\.removeEventListener\('resize', handleViewportChange\)/)
  assert.match(HOOK_SRC, /viewport\.removeEventListener\('scroll', handleViewportChange\)/)
})

test('VX51 : la mesure/scroll se fait en requestAnimationFrame (viewport stabilisé)', () => {
  const start = HOOK_SRC.indexOf('handleViewportChange = ()')
  const block = HOOK_SRC.slice(start, start + 1100)
  assert.match(block, /requestAnimationFrame\(\(\) => \{/)
  assert.match(block, /scrollIntoView\(\{ block: 'center', behavior: 'smooth' \}\)/)
})

test('VX51 : ne recentre que si le champ actif dépasse le bord visible (haut ou bas)', () => {
  assert.match(HOOK_SRC, /const hiddenBelow = rect\.bottom > visibleBottom/)
  assert.match(HOOK_SRC, /const hiddenAbove = rect\.top < visibleTop/)
  assert.match(HOOK_SRC, /if \(hiddenBelow \|\| hiddenAbove\)/)
})

test('VX51 : monté dans SectionsPane (cockpit lead)', () => {
  assert.match(SECTIONS_PANE_SRC, /import \{ useKeyboardAwareScroll \} from '\.\.\/\.\.\/\.\.\/hooks\/useKeyboardAwareScroll'/)
  assert.match(SECTIONS_PANE_SRC, /useKeyboardAwareScroll\(\{ containerRef: scrollRef \}\)/)
})

test('VX51 : monté dans DevisGenerator', () => {
  assert.match(DEVIS_GEN_SRC, /import useKeyboardAwareScroll from '\.\.\/\.\.\/hooks\/useKeyboardAwareScroll'/)
  assert.match(DEVIS_GEN_SRC, /useKeyboardAwareScroll\(\)/)
})
