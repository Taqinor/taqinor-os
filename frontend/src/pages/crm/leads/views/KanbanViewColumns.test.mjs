// LB9 — Colonnes : en-têtes riches épinglés, régions nommées, colonne vide =
// zone de drop (docs/design/leads-board-blueprint.md D2). Vérifié contre la
// SOURCE (pas de node_modules dans ce worktree/lane, donc pas de rendu RTL
// possible) — même convention que LeadsPageVX147EmptyState.test.mjs.
//   node --test src/pages/crm/leads/views/KanbanViewColumns.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const KANBAN = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')

function stageColumnBody() {
  const start = KANBAN.indexOf('function StageColumn(')
  const end = KANBAN.indexOf('\nexport default function KanbanView')
  assert.ok(start > 0 && end > start, 'StageColumn introuvable')
  return KANBAN.slice(start, end)
}

test('LB9 : chaque colonne est une région nommée (axe) — libellé + compteur', () => {
  const block = stageColumnBody()
  assert.match(
    block,
    /aria-label=\{`Étape \$\{col\.label\} — \$\{col\.count\} lead\$\{col\.count === 1 \? '' : 's'\}`\}/,
  )
  assert.match(block, /<section[\s\S]*?ref=\{setNodeRef\}/)
})

test('LB41 : le BOARD (scrolleur unique) est atteignable au clavier — plus le corps de colonne', () => {
  // LB41 (retour fondateur) : le corps ne scrolle plus, le tabindex vit sur
  // .kb-board — un tabindex résiduel sur .kb-col-body serait un stop de
  // tabulation mort (a11y régressive).
  const boardIdx = KANBAN.indexOf('className="kb-board"')
  assert.ok(boardIdx > 0, '.kb-board introuvable')
  const boardLocal = KANBAN.slice(boardIdx, boardIdx + 150)
  assert.match(boardLocal, /tabIndex=\{0\}/)
  assert.match(boardLocal, /aria-label="Board du pipeline"/)
  const block = stageColumnBody()
  const idx = block.indexOf('className="kb-col-body"')
  assert.ok(idx > 0, '.kb-col-body introuvable')
  const local = block.slice(idx, idx + 150)
  assert.doesNotMatch(local, /tabIndex/)
})

test('LB9 : colonne à 0 lead = zone de dépôt en pointillés, plus « Aucun lead »', () => {
  const block = stageColumnBody()
  assert.match(block, /<div className="kb-col-empty">Déposer un lead ici<\/div>/)
  assert.doesNotMatch(block, />Aucun lead</)
})

test('LB9 : une SEULE rangée montant + prévisionnel pondéré, tooltip STAGE_PROBABILITY (jamais une 2e table)', () => {
  const block = stageColumnBody()
  // Une seule occurrence de kb-col-money (fini les deux <span> empilés).
  assert.equal((block.match(/className="kb-col-money"/g) || []).length, 1)
  assert.doesNotMatch(block, /kb-col-forecast/)
  assert.match(block, /STAGE_PROBABILITY\[col\.key\]/)
  assert.match(block, /Prév\. \{formatMAD\(forecast\)\}/)
})

test('LB9 : STAGE_PROBABILITY importée de KanbanView, jamais re-déclarée ailleurs dans ce fichier', () => {
  // Une SEULE déclaration `export const STAGE_PROBABILITY` dans tout le fichier.
  assert.equal((KANBAN.match(/export const STAGE_PROBABILITY/g) || []).length, 1)
})
