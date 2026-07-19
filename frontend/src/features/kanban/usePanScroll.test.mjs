// LB11 — usePanScroll (drag-to-pan sur l'espace vide du board). Verified
// against SOURCE (no node_modules in this worktree/lane — the hook imports
// 'react' for useRef/useEffect, unrunnable standalone without it), même
// convention que useKeyboardAwareScroll.test.mjs. Les prédicats PURS qu'il
// utilise (panScrollPredicates.js) sont testés en profondeur, avec un vrai
// runtime, dans panScrollPredicates.test.mjs.
//   node --test src/features/kanban/usePanScroll.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const HOOK_SRC = readFileSync(join(HERE, 'usePanScroll.js'), 'utf8')
const KANBAN_SRC = readFileSync(join(HERE, '../../pages/crm/leads/views/KanbanView.jsx'), 'utf8')

test('LB11 : exporte usePanScroll (default + nommé)', () => {
  assert.match(HOOK_SRC, /export function usePanScroll/)
  assert.match(HOOK_SRC, /export default usePanScroll/)
})

test('LB11 : réutilise les prédicats PURS testés (jamais de logique dupliquée dans le hook)', () => {
  assert.match(
    HOOK_SRC,
    /import \{\s*shouldIgnorePanStart,\s*isPannablePointerType,\s*exceedsPanThreshold,\s*\} from '\.\/panScrollPredicates'/,
  )
  assert.match(HOOK_SRC, /if \(!isPannablePointerType\(e\.pointerType\)\) return/)
  assert.match(HOOK_SRC, /if \(shouldIgnorePanStart\(e\.target\)\) return/)
  assert.match(HOOK_SRC, /if \(!exceedsPanThreshold\(dx, dy\)\) return/)
})

test('LB11 : arme via setPointerCapture APRÈS le seuil, jamais avant (pas de pan fantôme sur un simple clic)', () => {
  const idx = HOOK_SRC.indexOf('const onPointerMove')
  const block = HOOK_SRC.slice(idx, idx + 600)
  assert.match(block, /if \(!p\.armed\) \{/)
  assert.match(block, /setPointerCapture\(e\.pointerId\)/)
})

test('LB11 : pointerup/pointercancel relâchent la capture et nettoient l’état (jamais un pan collé)', () => {
  assert.match(HOOK_SRC, /board\.addEventListener\('pointerup', release\)/)
  assert.match(HOOK_SRC, /board\.addEventListener\('pointercancel', release\)/)
  const idx = HOOK_SRC.indexOf('const release')
  const block = HOOK_SRC.slice(idx, idx + 500)
  assert.match(block, /releasePointerCapture\(e\.pointerId\)/)
  assert.match(block, /panRef\.current = null/)
})

test('LB11 : écouteurs natifs nettoyés au démontage (cleanup useEffect)', () => {
  assert.match(HOOK_SRC, /board\.removeEventListener\('pointerdown', onPointerDown\)/)
  assert.match(HOOK_SRC, /board\.removeEventListener\('pointermove', onPointerMove\)/)
  assert.match(HOOK_SRC, /board\.removeEventListener\('pointerup', release\)/)
  assert.match(HOOK_SRC, /board\.removeEventListener\('pointercancel', release\)/)
})

test('LB11 : état de pan en useRef, PAS en useState — un pointermove pendant le pan ne re-rend jamais KanbanView', () => {
  assert.doesNotMatch(HOOK_SRC, /useState/)
  assert.match(HOOK_SRC, /const panRef = useRef\(null\)/)
})

test('LB11 : KanbanView pose le ref sur .kb-board (rien d’autre à câbler)', () => {
  assert.match(KANBAN_SRC, /import \{? ?usePanScroll ?\}? from '\.\.\/\.\.\/\.\.\/\.\.\/features\/kanban\/usePanScroll'/)
  const idx = KANBAN_SRC.indexOf('className="kb-board"')
  assert.ok(idx > 0, '.kb-board introuvable')
  const block = KANBAN_SRC.slice(idx - 10, idx + 60)
  assert.match(block, /ref=\{boardRef\}/)
})

test('LB11 : autoScroll dnd-kit réglé sur DndContext (config, jamais de scroll maison pendant un drag)', () => {
  const idx = KANBAN_SRC.indexOf('<DndContext')
  assert.ok(idx > 0, '<DndContext introuvable')
  const block = KANBAN_SRC.slice(idx, idx + 700)
  assert.match(block, /autoScroll=\{\{ thresholds: \{ x: 0\.18, y: 0\.22 \} \}\}/)
})
