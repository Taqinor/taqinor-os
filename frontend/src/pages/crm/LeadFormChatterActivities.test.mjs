// QX27 (FG30) — LeadActivity kinds 'appel'/'email' render as BLANK chatter
// items today (no conditional branch). Add branches with body + outcome
// labels so a seller preparing a call can see what happened. Verified against
// SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormChatterActivities.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')

test('QX27 : OUTCOME_LABELS reflète la taxonomie serveur LeadActivity.OUTCOMES', () => {
  assert.match(SRC, /const OUTCOME_LABELS = \{/)
  for (const key of ['joint', 'non_joint', 'rappel', 'refuse', 'interesse']) {
    assert.match(SRC, new RegExp(`${key}:`))
  }
})

test('QX27 : le chatter rend une branche dédiée pour kind === \'appel\'', () => {
  assert.match(SRC, /\{a\.kind === 'appel' && \(/)
  const start = SRC.indexOf("{a.kind === 'appel' && (")
  const block = SRC.slice(start, start + 400)
  assert.match(block, /📞/)
  assert.match(block, /OUTCOME_LABELS\[a\.outcome\]/)
  assert.match(block, /a\.body/)
})

test('QX27 : le chatter rend une branche dédiée pour kind === \'email\'', () => {
  assert.match(SRC, /\{a\.kind === 'email' && \(/)
  const start = SRC.indexOf("{a.kind === 'email' && (")
  const block = SRC.slice(start, start + 400)
  assert.match(block, /✉️/)
  assert.match(block, /OUTCOME_LABELS\[a\.outcome\]/)
  assert.match(block, /a\.body/)
})

test('QX27 : les branches existantes (note/creation/modification) restent intactes', () => {
  assert.match(SRC, /a\.kind === 'note' &&/)
  assert.match(SRC, /a\.kind === 'creation' &&/)
  assert.match(SRC, /a\.kind === 'modification' &&/)
})
