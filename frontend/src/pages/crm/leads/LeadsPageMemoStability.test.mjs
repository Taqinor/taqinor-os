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

test('LB6 : viewProps est useMemo, placé AVANT les retours anticipés loading/error (règle des Hooks)', () => {
  const viewPropsIdx = PAGE_SRC.indexOf('const viewProps = useMemo(')
  assert.ok(viewPropsIdx > 0, 'viewProps n\'est pas useMemo')
  const loadingReturnIdx = PAGE_SRC.indexOf('if (leadsLoading && leads.length === 0)')
  const errorReturnIdx = PAGE_SRC.indexOf('if (error) return (')
  assert.ok(loadingReturnIdx > 0 && errorReturnIdx > 0, 'retours anticipés introuvables')
  assert.ok(viewPropsIdx < loadingReturnIdx, 'viewProps doit précéder le retour anticipé loading')
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

test('LB6 : ListView — la popover « ✗ Perdu » ne reçoit plus perdu Target (objet) mais perduOpen (booléen)', () => {
  const rowSignatureStart = LIST_SRC.indexOf('const ListRow = memo(function ListRow({')
  const rowSignature = LIST_SRC.slice(rowSignatureStart, rowSignatureStart + 400)
  assert.match(rowSignature, /perduOpen, onRequestPerduOpen, closePerdu, perduMotif, setPerduMotif/)
  assert.doesNotMatch(rowSignature, /\bperduTarget\b/)
})

test('LB6 : ListView — confirmPerdu prend (lead, motif) en PARAMÈTRES (jamais perduTarget/perduMotif en closure)', () => {
  assert.match(LIST_SRC, /const confirmPerdu = useCallback\(async \(lead, motif\) => \{/)
})

test('LB6 : ListView — seule la ligne ciblée reçoit la valeur live de perduMotif\\/perduBusy (les autres : constante)', () => {
  const start = LIST_SRC.indexOf('const isPerduTarget = perduTarget?.id === lead.id')
  assert.ok(start > 0)
  const block = LIST_SRC.slice(start, start + 1300)
  assert.match(block, /perduMotif=\{isPerduTarget \? perduMotif : ''\}/)
  assert.match(block, /perduBusy=\{isPerduTarget \? perduBusy : false\}/)
})

test('LB6 : ListView — onArchive/onRestore/onDelete/armCallNudgeFor/closePerdu sont useCallback', () => {
  for (const name of ['onArchive', 'onRestore', 'onDelete', 'armCallNudgeFor', 'closePerdu']) {
    const start = LIST_SRC.indexOf(`const ${name} = useCallback(`)
    assert.ok(start > 0, `${name} n'est pas useCallback`)
  }
})
