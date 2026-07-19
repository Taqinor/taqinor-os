// QX25 — "Planifier une relance" on every Kanban card has ALWAYS been dead:
// the prop is never passed from LeadsPage's viewProps (LeadCard already
// supports onPlanifierRelance, KanbanView already forwards it — only
// LeadsPage was missing the wire). Verified against SOURCE (no node_modules
// in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPagePlanifierRelance.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const KANBAN_SRC = readFileSync(join(HERE, 'views/KanbanView.jsx'), 'utf8')
const CARD_SRC = readFileSync(join(HERE, 'views/LeadCard.jsx'), 'utf8')
// LW37 — `focusSection` traverse désormais LeadWorkspace (prop threadée vers
// SectionsPane) ; le saut réel (jumpTo) vit dans SectionsPane. LeadsPage passe
// toujours la prop de la même façon (adaptateur LeadForm inchangé côté contrat).
const WORKSPACE_SRC = readFileSync(
  join(HERE, '..', '..', '..', 'features', 'crm', 'workspace', 'LeadWorkspace.jsx'), 'utf8')
const SECTIONS_SRC = readFileSync(
  join(HERE, '..', '..', '..', 'features', 'crm', 'workspace', 'SectionsPane.jsx'), 'utf8')

test('QX25 : LeadsPage définit onPlanifierRelance (setEditLead/setShowForm, comme les autres ouvertures de fiche)', () => {
  assert.match(PAGE_SRC, /const onPlanifierRelance = \(lead\) => \{/)
  const start = PAGE_SRC.indexOf('const onPlanifierRelance = (lead) => {')
  const body = PAGE_SRC.slice(start, start + 250)
  assert.match(body, /setEditLead\(lead\)/)
  assert.match(body, /setShowForm\(true\)/)
})

test('QX25 : viewProps transmet désormais onPlanifierRelance (c\'était le trou verifié)', () => {
  const start = PAGE_SRC.indexOf('const viewProps = {')
  const block = PAGE_SRC.slice(start, start + 400)
  assert.match(block, /onPlanifierRelance,/)
})

test('QX25 : focusSection traverse LeadWorkspace → SectionsPane et saute vers la section', () => {
  assert.match(PAGE_SRC, /focusSection=\{showForm \? formFocusSection : null\}/)
  // Le shell accepte la prop et la thread vers SectionsPane.
  assert.match(WORKSPACE_SRC, /focusSection = null,/)
  assert.match(WORKSPACE_SRC, /focusSection=\{focusSection\}/)
  // VX223 — SectionsPane consomme AUSSI un canal sessionStorage quand
  // `focusSection` est absent ; `target` vaut `focusSection` en priorité,
  // `jumpTo(target)` reste le même geste.
  assert.match(SECTIONS_SRC, /focusSection = null,/)
  assert.match(SECTIONS_SRC, /let target = focusSection/)
  assert.match(SECTIONS_SRC, /jumpTo\(target\)/)
})

test('QX25 : KanbanView forwarde déjà onPlanifierRelance à LeadCard (non modifié, déjà correct)', () => {
  assert.match(KANBAN_SRC, /onPlanifierRelance/)
})

test('QX25 : LeadCard.jsx utilise déjà onPlanifierRelance pour rendre le raccourci cliquable', () => {
  assert.match(CARD_SRC, /onPlanifierRelance/)
  assert.match(CARD_SRC, /onClick=\{\(e\) => \{ e\.stopPropagation\(\); onPlanifierRelance\(lead\) \}\}/)
})
