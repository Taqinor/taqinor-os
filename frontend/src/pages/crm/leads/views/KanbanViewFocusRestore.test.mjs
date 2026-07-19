// LB12 — Restauration du focus après un drop (souris ET clavier),
// docs/design/leads-board-blueprint.md D2, recon-05 a11y #4. Vérifié contre
// la SOURCE (pas de node_modules dans ce worktree/lane, donc pas de rendu
// RTL possible ni de jsdom pour exercer un VRAI focus) — même convention que
// KanbanViewColumns.test.mjs. Le comportement `requestAnimationFrame` +
// `querySelector` est un idiome DOM standard, déjà éprouvé ailleurs dans ce
// repo (useKeyboardAwareScroll.js) : ce test verrouille le CONTRAT (le bon
// nœud porte l'attribut, le bon sélecteur est requêté, au bon endroit du
// handler) plutôt que de simuler un focus réel.
//   node --test src/pages/crm/leads/views/KanbanViewFocusRestore.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const KANBAN = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')

function draggableCardBody() {
  const start = KANBAN.indexOf('const DraggableCard = memo(')
  const end = KANBAN.indexOf("\n// Colonne d'étape", start)
  assert.ok(start > 0 && end > start, 'DraggableCard introuvable')
  return KANBAN.slice(start, end)
}

function dragEndBody() {
  const start = KANBAN.indexOf('const handleDragEnd = ')
  const end = KANBAN.indexOf('const handleDragCancel', start)
  assert.ok(start > 0 && end > start, 'handleDragEnd introuvable')
  return KANBAN.slice(start, end)
}

test('LB12 : `data-lead-id` posé sur le MÊME nœud que `{...listeners} {...attributes}` (celui réellement focalisable)', () => {
  const block = draggableCardBody()
  assert.match(block, /<div data-lead-id=\{lead\.id\} \{\.\.\.listeners\} \{\.\.\.attributes\}>/)
})

test('LB12 : un déplacement RÉUSSI programme requestAnimationFrame → querySelector(data-lead-id) → focus()', () => {
  const block = dragEndBody()
  const idx = block.indexOf('onChangeStage(lead, over.id)')
  assert.ok(idx > 0, 'appel onChangeStage introuvable')
  const after = block.slice(idx, idx + 950)
  assert.match(after, /requestAnimationFrame\(\(\) => \{/)
  assert.match(after, /document\.querySelector\(`\[data-lead-id="\$\{lead\.id\}"\]`\)\?\.focus\(\)/)
})

test('LB12 : les sorties anticipées (pas de over / drop sur place / recul refusé) ne touchent PAS au focus — le nœud d’origine n’est jamais démonté', () => {
  const block = dragEndBody()
  const guardIdx = block.indexOf('if (!lead || !over || over.id === lead.stage) return')
  const reculIdx = block.indexOf('if (!isStageMoveAllowed(lead.stage, over.id)) {')
  const focusIdx = block.indexOf('requestAnimationFrame(')
  assert.ok(guardIdx > 0 && reculIdx > guardIdx, 'ordre des gardes inattendu')
  // Le `requestAnimationFrame` de restauration de focus vient APRÈS les deux
  // gardes — aucune des deux sorties anticipées ne l'atteint jamais.
  assert.ok(focusIdx > reculIdx, 'la restauration de focus doit suivre les gardes, pas les précéder')
})

test('LB12 : même handler pour la souris ET le clavier — un seul handleDragEnd, câblé sur DndContext', () => {
  assert.equal((KANBAN.match(/const handleDragEnd = /g) || []).length, 1)
  assert.match(KANBAN, /onDragEnd=\{handleDragEnd\}/)
  // KeyboardSensor est bien un des sensors de CE DndContext (parité clavier).
  assert.match(KANBAN, /useSensor\(KeyboardSensor\)/)
})
