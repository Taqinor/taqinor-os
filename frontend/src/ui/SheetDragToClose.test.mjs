// VX43 — Glisser-vers-le-bas-pour-fermer sur les bottom-sheets (`side="bottom"`)
// de Sheet.jsx, le geste terrain attendu (MaJourneePage/InterventionsPage
// passent maintenant leurs sheets en side="bottom" sous 768px via
// ResponsiveDialog/Sheet directement). Verified against SOURCE (no
// node_modules in this worktree/lane — Sheet.jsx imports 'react' and
// '@radix-ui/react-dialog', neither resolvable here) — same convention as
// LeadCardSwipeAction.test.mjs / DataTableSwipeAction.test.mjs.
//   node --test src/ui/SheetDragToClose.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'Sheet.jsx'), 'utf8')

test('VX43 : le glisser-pour-fermer est réservé à side="bottom" (jamais right/left/top)', () => {
  assert.match(SRC, /const draggable = side === 'bottom'/)
})

test('VX43 : le geste ne s\'arme que vers le BAS (delta > 0), jamais vers le haut', () => {
  assert.match(SRC, /if \(delta <= 0\) return/)
})

test('VX43 : un lâcher au-delà du seuil ferme via un clic programmatique sur DialogPrimitive.Close', () => {
  assert.match(SRC, /const DRAG_CLOSE_THRESHOLD = 80/)
  assert.match(SRC, /if \(dragging\.current && dragY >= DRAG_CLOSE_THRESHOLD\) \{/)
  assert.match(SRC, /closeRef\.current\?\.click\(\)/)
})

test('VX43 : la poignée visuelle n\'apparaît que sur les bottom-sheets', () => {
  assert.match(SRC, /\{draggable && \(/)
  assert.match(SRC, /glisser pour\s*\n?\s*fermer/)
})

test('VX43 : les handlers tactiles sont conditionnés à `draggable` (aucun changement pour right\\/left\\/top)', () => {
  assert.match(SRC, /onTouchStart=\{draggable \? onTouchStart : undefined\}/)
  assert.match(SRC, /onTouchMove=\{draggable \? onTouchMove : undefined\}/)
  assert.match(SRC, /onTouchEnd=\{draggable \? onTouchEnd : undefined\}/)
})

test('VX43 : le clic programmatique fonctionne même quand showClose=false (bouton fermeture masqué mais présent)', () => {
  assert.match(SRC, /\{draggable && !showClose && \(/)
  assert.match(SRC, /<DialogPrimitive\.Close ref=\{closeRef\} className="sr-only"/)
})

test('VX43 : SIDE (right/left/bottom/top) reste inchangé (rétrocompatible)', () => {
  assert.match(SRC, /right: 'inset-y-0 right-0 h-full w-\[min\(26rem,calc\(100%-2rem\)\)\] border-l'/)
  assert.match(SRC, /bottom: 'inset-x-0 bottom-0 max-h-\[85vh\] w-full rounded-t-2xl border-t'/)
})
