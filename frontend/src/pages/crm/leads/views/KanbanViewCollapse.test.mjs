// LB10 — Repli de colonne persisté (rail droppable),
// docs/design/leads-board-blueprint.md D2. Vérifié contre la SOURCE (pas de
// node_modules dans ce worktree/lane, donc pas de rendu RTL possible) — même
// convention que KanbanViewColumns.test.mjs. La persistance PURE elle-même
// (readCollapsedStages/writeCollapsedStages) est testée en profondeur, avec
// un vrai state factice, dans collapsedColumns.test.mjs.
//   node --test src/pages/crm/leads/views/KanbanViewCollapse.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const KANBAN = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')

test('LB10 : importe la persistance depuis features/kanban/collapsedColumns (jamais une localStorage ad-hoc)', () => {
  assert.match(
    KANBAN,
    /import \{ readCollapsedStages, writeCollapsedStages \} from '\.\.\/\.\.\/\.\.\/\.\.\/features\/kanban\/collapsedColumns'/,
  )
})

test('LB10 : aucun repli par défaut — l’état initial vient EXCLUSIVEMENT de readCollapsedStages()', () => {
  assert.match(
    KANBAN,
    /useState\(\(\) => new Set\(readCollapsedStages\(\)\)\)/,
  )
})

test('LB10 : chaque bascule persiste immédiatement (writeCollapsedStages appelé dans le toggler)', () => {
  const idx = KANBAN.indexOf('const toggleCollapsed = useCallback(')
  assert.ok(idx > 0, 'toggleCollapsed introuvable')
  const block = KANBAN.slice(idx, idx + 400)
  assert.match(block, /writeCollapsedStages\(\[\.\.\.next\]\)/)
})

test('LB10 : la colonne repliée reste EXACTEMENT la même zone droppable (même useDroppable, même section)', () => {
  const start = KANBAN.indexOf('function StageColumn(')
  const end = KANBAN.indexOf('\nexport default function KanbanView')
  const block = KANBAN.slice(start, end)
  // Un SEUL useDroppable dans StageColumn, posé AVANT toute branche
  // collapsed/déplié — la logique de repli ne touche jamais au registre dnd-kit.
  assert.equal((block.match(/useDroppable\(\{ id: col\.key \}\)/g) || []).length, 1)
  assert.match(block, /ref=\{setNodeRef\}[\s\S]*?className=\{sectionClassName\}/)
  // `kb-over` (surbrillance de survol) reste possible que la colonne soit
  // repliée ou non — la classe est construite AVANT toute branche collapsed.
  assert.match(block, /isOver && 'kb-over'/)
  assert.match(block, /collapsed && 'kb-col-collapsed'/)
})

test('LB10 : rail replié = chevron + compteur + libellé pivoté, pas les cartes', () => {
  const start = KANBAN.indexOf('function StageColumn(')
  const end = KANBAN.indexOf('\nexport default function KanbanView')
  const block = KANBAN.slice(start, end)
  assert.match(block, /aria-expanded=\{!collapsed\}/)
  assert.match(block, /className="kb-col-rail-label"/)
  // En repli, `children` (les cartes) ne sont PAS rendues.
  const railBranch = block.slice(block.indexOf('{collapsed ? ('), block.indexOf('kb-col-body'))
  assert.doesNotMatch(railBranch, /\{children\}/)
})

test('LB10 : bouton de repli labellisé FR (jamais icône seule sans nom accessible)', () => {
  assert.match(KANBAN, /Déplier la colonne \$\{col\.label\}/)
  assert.match(KANBAN, /Replier la colonne \$\{col\.label\}/)
  assert.match(KANBAN, /aria-label=\{chevronLabel\}/)
})
