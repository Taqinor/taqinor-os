// VX43 — Gestes natifs terrain sur les écrans interventions :
//   - MaJourneePage.jsx / InterventionsPage.jsx : sheet terrain alignée sur le
//     bottom-sheet mobile (side="bottom" sous 768px via useIsMobile, tiroir
//     latéral inchangé sur desktop) + pull-to-refresh maison (usePullToRefresh)
//     qui relance le fetch existant sans changer son contrat.
//   - InterventionsPage.jsx : repli « changer le statut au menu » sans drag
//     sous 768px sur InterventionCard (le glisser-déposer @dnd-kit reste actif).
// Verified against SOURCE (no node_modules in this worktree/lane — les deux
// fichiers importent 'react'/'@dnd-kit/core' non résolvables ici), même
// convention que LeadCardSwipeAction.test.mjs / SheetDragToClose.test.mjs.
//   node --test src/pages/interventions/InterventionsVX43.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const MJ = readFileSync(join(HERE, 'MaJourneePage.jsx'), 'utf8')
const IP = readFileSync(join(HERE, 'InterventionsPage.jsx'), 'utf8')

/* ===================== MaJourneePage.jsx ===================== */

test('MaJourneePage : importe useIsMobile + usePullToRefresh (zéro nouvelle dépendance externe)', () => {
  assert.match(MJ, /import \{ useIsMobile \} from '\.\.\/\.\.\/ui\/ResponsiveDialog'/)
  assert.match(MJ, /import \{ usePullToRefresh \} from '\.\.\/\.\.\/ui\/usePullToRefresh'/)
})

test('MaJourneePage : la sheet terrain bascule en side="bottom" sur mobile, "right" sur desktop', () => {
  assert.match(MJ, /side=\{isMobile \? 'bottom' : 'right'\}/)
})

test('MaJourneePage : le pull-to-refresh relance `load` (le fetch existant, sans changer son contrat)', () => {
  assert.match(MJ, /const \{ containerProps, pullDistance, refreshing \} = usePullToRefresh\(load\)/)
  assert.match(MJ, /\{\.\.\.containerProps\}/)
})

/* ===================== InterventionsPage.jsx ===================== */

test('InterventionsPage : importe useIsMobile + usePullToRefresh', () => {
  assert.match(IP, /import \{ useIsMobile \} from '\.\.\/\.\.\/ui\/ResponsiveDialog'/)
  assert.match(IP, /import \{ usePullToRefresh \} from '\.\.\/\.\.\/ui\/usePullToRefresh'/)
})

test('InterventionsPage : la sheet détail bascule en side="bottom" sur mobile, "right" sur desktop', () => {
  assert.match(IP, /side=\{isMobile \? 'bottom' : 'right'\}/)
})

test('InterventionsPage : le pull-to-refresh relance `fetchData` (rafraîchissement de fond, pas `reload`)', () => {
  assert.match(IP, /const \{ containerProps, pullDistance, refreshing \} = usePullToRefresh\(fetchData\)/)
})

test('InterventionsPage : InterventionCard reçoit onChangeStatus et rend un <select> replié sous 768px', () => {
  assert.match(IP, /function InterventionCard\(\{ it, users, onReassign, onChangeStatus \}\)/)
  assert.match(IP, /className="kc-status-mover sm:hidden"/)
  assert.match(IP, /onChange=\{\(e\) => onChangeStatus\(it, e\.target\.value\)\}/)
})

test('InterventionsPage : le repli statut liste les VRAIS statuts (INTERVENTION_STATUSES/LABELS, jamais en dur)', () => {
  assert.match(IP, /\{INTERVENTION_STATUSES\.map\(\(s\) => \(\r?\n\s*<option key=\{s\} value=\{s\}>\{INTERVENTION_STATUS_LABELS\[s\]\}<\/option>/)
})

test('InterventionsPage : le repli statut ne vole pas le drag (stopPropagation pointer/touch/click)', () => {
  assert.match(IP, /onPointerDown=\{\(e\) => e\.stopPropagation\(\)\}\s*\r?\n\s*onTouchStart=\{\(e\) => e\.stopPropagation\(\)\}\s*\r?\n\s*onClick=\{\(e\) => e\.stopPropagation\(\)\}>\s*\r?\n\s*<label className="sr-only" htmlFor=\{`kc-status-/)
})

test('InterventionsPage : DraggableCard et KanbanView threadent onChangeStatus jusqu\'à la carte', () => {
  assert.match(IP, /function DraggableCard\(\{ it, users, onReassign, onChangeStatus \}\)/)
  assert.match(IP, /<InterventionCard it=\{it\} users=\{users\} onReassign=\{onReassign\} onChangeStatus=\{onChangeStatus\} \/>/)
  assert.match(IP, /<DraggableCard it=\{it\} users=\{users\} onReassign=\{onReassign\} onChangeStatus=\{onChangeStatus\} \/>/)
})
