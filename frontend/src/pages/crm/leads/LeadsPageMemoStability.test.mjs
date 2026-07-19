// LB6 — mémo réparé : une frappe ne re-rend plus tout le board/la table (bug
// recon2-03 #4, blueprint I4). Vérifie que TOUS les callbacks de viewProps
// sont useCallback, viewProps est useMemo (placé AVANT les retours anticipés
// loading/error — règle des Hooks), DraggableCard est memo(), et la popover
// « ✗ Perdu » de la liste ne reçoit que des primitives + callbacks stables.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageMemoStability.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const KANBAN_SRC = readFileSync(join(HERE, 'views/KanbanView.jsx'), 'utf8')
const LIST_SRC = readFileSync(join(HERE, 'views/ListView.jsx'), 'utf8')

test('LB6 : TOUS les callbacks de viewProps sont useCallback (jamais une closure fraîche par rendu)', () => {
  for (const name of [
    'refetch', 'onToggleSelect', 'onToggleAll', 'reassign',
    'onPlanifierRelance', 'onInlineSave', 'onMarkPerdu',
  ]) {
    const start = PAGE_SRC.indexOf(`const ${name} = useCallback(`)
    assert.ok(start > 0, `${name} n'est pas useCallback`)
  }
  // onOpenLead/onAutoQuote/changeStage : déjà useCallback depuis VX187,
  // vérifiés ici pour couvrir la liste COMPLÈTE des callbacks de viewProps.
  assert.match(PAGE_SRC, /const onOpenLead = useCallback\(/)
  assert.match(PAGE_SRC, /const onAutoQuote = useCallback\(/)
  assert.match(PAGE_SRC, /const changeStage = useCallback\(/)
})

test('LB6→LB27 : viewProps est useMemo, placé AVANT useDelayedLoading et le retour anticipé error (règle des Hooks)', () => {
  const viewPropsIdx = PAGE_SRC.indexOf('const viewProps = useMemo(')
  assert.ok(viewPropsIdx > 0, 'viewProps n\'est pas useMemo')
  // LB27 — le retour anticipé PLEIN-PAGE loading a disparu (blueprint I9,
  // squelette EN FORME dans le shell) ; `initialLoading` reste un hook
  // dérivé placé, comme viewProps, AVANT le seul retour anticipé restant
  // (error).
  const initialLoadingIdx = PAGE_SRC.indexOf('const initialLoading = leadsLoading && leads.length === 0')
  const errorReturnIdx = PAGE_SRC.indexOf('if (error) return (')
  assert.ok(initialLoadingIdx > 0 && errorReturnIdx > 0, 'retour anticipé error ou initialLoading introuvable')
  assert.ok(viewPropsIdx < initialLoadingIdx, 'viewProps doit précéder initialLoading/useDelayedLoading')
  assert.ok(viewPropsIdx < errorReturnIdx, 'viewProps doit précéder le retour anticipé error')
})

test('LB6 : viewProps embarque onMarkPerdu (LB5) et tous les callbacks stabilisés', () => {
  const start = PAGE_SRC.indexOf('const viewProps = useMemo(() => ({')
  const block = PAGE_SRC.slice(start, start + 700)
  for (const key of [
    'onOpenLead', 'onChangeStage: changeStage', 'onAutoQuote', 'onPlanifierRelance',
    'onRefetch: refetch', 'onReassign: reassign', 'onToggleSelect', 'onToggleAll',
    'onInlineSave', 'onMarkPerdu',
  ]) {
    assert.match(block, new RegExp(key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

test('LB6 : KanbanView mémoïse DraggableCard (memo())', () => {
  assert.match(KANBAN_SRC, /const DraggableCard = memo\(function DraggableCard\(/)
})

test('LB6/LB21 : ListRow ne reçoit AUCUNE plomberie perdu — seulement onMarkPerdu (stable)', () => {
  const rowSignatureStart = LIST_SRC.indexOf('const ListRow = memo(function ListRow({')
  const rowSignature = LIST_SRC.slice(rowSignatureStart, rowSignatureStart + 400)
  assert.match(rowSignature, /onMarkPerdu/)
  assert.doesNotMatch(rowSignature, /\bperduTarget\b|\bperduOpen\b|\bperduMotif\b|\bperduBusy\b|\bmotifsPerte\b/)
})

test('LB6/LB21 : plus AUCUN état perdu dans le parent (le PerduPopover partagé le porte)', () => {
  assert.doesNotMatch(LIST_SRC, /setPerduTarget|setPerduMotif|setPerduBusy|setMotifsPerte/)
})

test('LB6 : ListView — onArchive/onRestore/onDelete/armCallNudgeFor sont useCallback', () => {
  for (const name of ['onArchive', 'onRestore', 'onDelete', 'armCallNudgeFor']) {
    const start = LIST_SRC.indexOf(`const ${name} = useCallback(`)
    assert.ok(start > 0, `${name} n'est pas useCallback`)
  }
})
