// LB38 — `selectionActive` enfin CÂBLÉ (comportement D3, blueprint
// docs/design/leads-board-blueprint.md §D3) : pendant qu'une sélection est en
// cours, la case de TOUTES les cartes visibles est révélée — plus besoin de
// survoler chaque carte pour retrouver sa case. La prop existait depuis LB13
// et la règle CSS aussi, mais AUCUN parent ne la passait : elle valait
// toujours `false`, la règle était morte et le comportement différé en
// silence. Vérifié contre la SOURCE + la feuille de style (pas de
// node_modules dans ce worktree/lane ; le suite frontend de la CI est
// `node --test "src/**/*.test.mjs"`).
//   node --test src/pages/crm/leads/views/LeadCardSelectionActive.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const CARD = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')
const KANBAN = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')
const CSS = readFileSync(join(HERE, '../../../../index.css'), 'utf8')

test('LB38 : une sélection NON VIDE arme la prop pour TOUTES les cartes du board (jamais seulement les sélectionnées)', () => {
  // Le board dérive un BOOLÉEN « il y a une sélection » et le passe à chaque
  // carte — indépendamment de `selected.has(lead.id)` (qui, lui, ne concerne
  // que la carte cochée).
  assert.match(KANBAN, /selectionActive=\{selected\.size > 0\}/)
  assert.match(KANBAN, /selected=\{selected\.has\(lead\.id\)\}/)
  // Les deux props sont bien posées sur la MÊME carte, dans le même appel.
  const idx = KANBAN.indexOf('selected={selected.has(lead.id)}')
  assert.ok(idx > 0)
  assert.match(KANBAN.slice(idx, idx + 160), /selectionActive=\{selected\.size > 0\}/)
})

test('LB38 : DraggableCard relaie la prop jusqu’à LeadCard (le maillon manquant)', () => {
  const start = KANBAN.indexOf('const DraggableCard = memo(function DraggableCard(')
  const end = KANBAN.indexOf("\n// Colonne d'étape", start)
  assert.ok(start > 0 && end > start, 'DraggableCard introuvable')
  const block = KANBAN.slice(start, end)
  // Reçue dans la signature…
  assert.match(block, /\r?\n\s*selectionActive,\r?\n/)
  // …et transmise à LeadCard.
  assert.match(block, /selectionActive=\{selectionActive\}/)
})

test('LB38 : la prop reste une PRIMITIVE booléenne — la mémoïsation LB6 n’est pas cassée', () => {
  // Jamais le `Set` entier (dont la référence change à chaque sélection) :
  // memo(DraggableCard)/memo(LeadCard) doivent comparer un booléen.
  assert.doesNotMatch(KANBAN, /selectionActive=\{selected\}/)
  assert.match(KANBAN, /const DraggableCard = memo\(function DraggableCard\(/)
})

test('LB38 : LeadCard traduit la prop en classe `kb-card-selection-active`', () => {
  assert.match(CARD, /selectionActive = false,/)
  assert.match(CARD, /selectionActive \? 'kb-card-selection-active' : '',/)
})

test('LB38 : la règle CSS n’est plus morte — elle révèle la case SANS survol', () => {
  // La case est masquée au repos…
  assert.match(CSS, /\.kb-card-check \{\s*\r?\n\s*opacity: 0;/)
  // …et révélée par la sélection active, dans le bloc NON gardé par
  // @media (hover: hover) — sinon « sans survol » serait faux au desktop.
  const idx = CSS.indexOf('.kb-card-selection-active .kb-card-check {')
  assert.ok(idx > 0, 'règle .kb-card-selection-active introuvable')
  const hoverIdx = CSS.search(/@media \(hover: hover\) \{\r?\n\s*\.kb-card:hover \.kb-card-check/)
  assert.ok(hoverIdx > idx, 'la révélation par sélection doit précéder (et vivre hors de) la garde hover')
  assert.match(CSS.slice(idx, idx + 90), /opacity: 1;/)
})
