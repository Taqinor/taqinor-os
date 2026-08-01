// VX95 — câblage de toastWithUndo (primitive zéro consommateur avant cette
// tâche) : archivage/désarchivage leads (ListView + BulkActionBar via
// LeadsPage.runBulk), drop kanban en avant (LeadsPage.changeStage), et
// archivage/désarchivage stock (StockList). Vérifié contre la SOURCE (pas de
// node_modules dans ce worktree/lane) :
//   node --test src/pages/crm/leads/VX95ForgivenessKanbanArchive.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const LIST_VIEW = readFileSync(join(HERE, 'views', 'ListView.jsx'), 'utf8')
const LEADS_PAGE = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const STOCK_LIST = readFileSync(
  join(HERE, '..', '..', 'stock', 'StockList.jsx'), 'utf8',
)

// EZ14 — le motif VX95 (« appliquer tout de suite, l'inverse à l'annulation »)
// est INCHANGÉ ; il passe désormais par l'util unique `mutateWithUndo`, qui
// n'accepte PAS de commit différé. Ce que VX95 protège reste vrai : l'undo
// d'un archivage est une restauration, et réciproquement.
test('VX95/EZ14 : archiver un lead offre l’undo dont l’inverse est restoreLead', () => {
  const start = LIST_VIEW.indexOf('const onArchive =')
  assert.ok(start > 0)
  const block = LIST_VIEW.slice(start, start + 700)
  assert.match(block, /mutateWithUndo\(\{/)
  assert.match(block, /apply: \(\) => dispatch\(archiveLead\(lead\.id\)\)\.unwrap\(\)/)
  assert.match(block, /revert: \(\) => dispatch\(restoreLead\(lead\.id\)\)\.unwrap\(\)/)
})

test('VX95/EZ14 : restaurer un lead offre l’undo dont l’inverse est archiveLead', () => {
  const start = LIST_VIEW.indexOf('const onRestore =')
  assert.ok(start > 0)
  const block = LIST_VIEW.slice(start, start + 700)
  assert.match(block, /mutateWithUndo\(\{/)
  assert.match(block, /apply: \(\) => dispatch\(restoreLead\(lead\.id\)\)\.unwrap\(\)/)
  assert.match(block, /revert: \(\) => dispatch\(archiveLead\(lead\.id\)\)\.unwrap\(\)/)
})

test('LeadsPage.runBulk : archive/unarchive en masse déclenchent toastWithUndo avec action inverse sur le même lot', () => {
  const start = LEADS_PAGE.indexOf('const runBulk =')
  assert.ok(start > 0)
  const block = LEADS_PAGE.slice(start, start + 1200)
  assert.match(block, /toastWithUndo\(/)
  assert.match(block, /reverse = action === 'archive' \? 'unarchive' : 'archive'/)
  assert.match(block, /bulkLeads\(\{ ids, action: reverse \}\)/)
})

test('LeadsPage.changeStage : le drop kanban en avant réussi affiche toastWithUndo restaurant l’étape antérieure EXACTE', () => {
  const start = LEADS_PAGE.indexOf('const changeStage =')
  assert.ok(start > 0)
  const block = LEADS_PAGE.slice(start, start + 3000)
  assert.match(block, /toastWithUndo\(/)
  // Restaure `prev` (l'étape AVANT le drop), pas une valeur recalculée.
  assert.match(block, /leadStagePatched\(\{ id: lead\.id, stage: prev \}\)/)
  // LB39 — le PATCH arrière porte désormais le marqueur d'annulation : sans
  // lui, la garde funnel du serializer 400ait TOUT recul et chaque
  // « Annuler » finissait en « Annulation impossible » (undo mort en prod).
  // Le serveur revérifie le marqueur (mouvement inverse exact + fenêtre
  // courte) — il n'autorise rien à lui seul.
  assert.match(block, /updateLead\(\{\s*id: lead\.id, data: \{ stage: prev, undo: true \},\s*\}\)/)
  // Le chemin AVANT (le drop lui-même) ne porte JAMAIS le marqueur.
  const forward = block.slice(0, block.indexOf('toastWithUndo('))
  assert.match(forward, /data: \{ stage: newStage \}/)
  assert.doesNotMatch(forward, /undo: true/)
})

test('LeadsPage.changeStage : le recul-guard manuel (KanbanView) reste en amont — cette fonction ne le duplique pas', () => {
  // Le garde-fou anti-recul vit dans KanbanView.handleDragEnd, AVANT l'appel à
  // onChangeStage/changeStage : changeStage ne doit contenir aucune nouvelle
  // logique de blocage de recul (l'undo restaure `prev`, ce qui est un recul
  // volontaire de sa PROPRE action, pas un recul manuel).
  const start = LEADS_PAGE.indexOf('const changeStage =')
  const end = LEADS_PAGE.indexOf('\n  }', start)
  const block = LEADS_PAGE.slice(start, end)
  assert.doesNotMatch(block, /stageRank/)
})

test('StockList : archiver un produit (delete → archived) affiche toastWithUndo restaurant via unarchiveProduit', () => {
  const start = STOCK_LIST.indexOf('const handleDelete =')
  assert.ok(start > 0)
  const block = STOCK_LIST.slice(start, start + 900)
  assert.match(block, /toastWithUndo\(/)
  assert.match(block, /unarchiveProduit\(p\.id\)/)
})

test('StockList : désarchiver un produit affiche toastWithUndo relançant deleteProduit', () => {
  const start = STOCK_LIST.indexOf('const handleUnarchive =')
  assert.ok(start > 0)
  const block = STOCK_LIST.slice(start, start + 700)
  assert.match(block, /toastWithUndo\(/)
  assert.match(block, /deleteProduit\(p\.id\)/)
})
