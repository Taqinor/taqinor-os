// QX32 — Unified lead timeline: the backend merges devis lifecycle events
// (sent/opened/signed/refused + engagement summary) into the crm `historique`
// payload (apps/ventes/selectors.py::devis_events_for_lead, per the
// cross-app boundary rule — ventes' selector, consumed read-only here).
// LeadForm's chatter renders them with distinct icons, so a seller
// preparing a call sees the quote lifecycle inline instead of opening two
// screens. Verified against SOURCE (no node_modules in this worktree/lane).
//
// VX23 — the rendering branches moved from LeadForm.jsx into the reusable
// components/ChatterTimeline.jsx (LeadForm now just delegates via
// <ChatterTimeline entries={historique} />). This test follows the move.
//   node --test src/pages/crm/LeadFormUnifiedTimeline.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, '..', '..', 'components', 'ChatterTimeline.jsx'), 'utf8')

const KIND_ICONS = {
  devis_sent: '📤',
  devis_opened: '👁️',
  devis_signed: '✅',
  devis_refused: '❌',
  devis_engagement: '📊',
}

test('QX32 : chaque kind de cycle de vie devis a une branche de rendu dédiée avec une icône distincte', () => {
  for (const [kind, icon] of Object.entries(KIND_ICONS)) {
    const marker = `a.kind === '${kind}'`
    assert.ok(SRC.includes(marker), `branche manquante pour ${kind}`)
    const start = SRC.indexOf(marker)
    const block = SRC.slice(start, start + 200)
    assert.ok(block.includes(icon), `icône ${icon} manquante pour ${kind}`)
  }
})

test('QX32 : toutes les icônes de cycle de vie sont mutuellement distinctes', () => {
  const icons = Object.values(KIND_ICONS)
  assert.equal(new Set(icons).size, icons.length)
})

test('QX32 : les branches existantes (note/creation/modification/appel/email) restent intactes', () => {
  for (const kind of ['note', 'creation', 'modification', 'appel', 'email']) {
    assert.ok(SRC.includes(`a.kind === '${kind}'`), `régression sur la branche ${kind}`)
  }
})
