// QX27 (FG30) — LeadActivity kinds 'appel'/'email' render as BLANK chatter
// items today (no conditional branch). Add branches with body + outcome
// labels so a seller preparing a call can see what happened. Verified against
// SOURCE (no node_modules in this worktree/lane).
//
// VX23 — ChatterTimeline devient la seule source de rendu du chatter : les
// branches kind === 'appel'/'email' (+ OUTCOME_LABELS) ont déménagé de
// LeadForm.jsx vers components/ChatterTimeline.jsx (composant réutilisable).
// Ce test suit le déménagement — la garantie QX27 reste intacte, juste dans
// son nouveau fichier source.
//   node --test src/pages/crm/LeadFormChatterActivities.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const CHATTER_SRC = readFileSync(join(HERE, '..', '..', 'components', 'ChatterTimeline.jsx'), 'utf8')
const LEADFORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')

test('QX27 : OUTCOME_LABELS reflète la taxonomie serveur LeadActivity.OUTCOMES', () => {
  assert.match(CHATTER_SRC, /export const OUTCOME_LABELS = \{/)
  for (const key of ['joint', 'non_joint', 'rappel', 'refuse', 'interesse']) {
    assert.match(CHATTER_SRC, new RegExp(`${key}:`))
  }
})

test('QX27 : le chatter rend une branche dédiée pour kind === \'appel\'', () => {
  assert.match(CHATTER_SRC, /a\.kind === 'appel'/)
  const start = CHATTER_SRC.indexOf("a.kind === 'appel'")
  const block = CHATTER_SRC.slice(start, start + 400)
  assert.match(block, /📞/)
  assert.match(block, /OUTCOME_LABELS\[a\.outcome\]/)
  assert.match(block, /a\.body/)
})

test('QX27 : le chatter rend une branche dédiée pour kind === \'email\'', () => {
  assert.match(CHATTER_SRC, /a\.kind === 'email'/)
  const start = CHATTER_SRC.indexOf("a.kind === 'email'")
  const block = CHATTER_SRC.slice(start, start + 400)
  assert.match(block, /✉️/)
  assert.match(block, /OUTCOME_LABELS\[a\.outcome\]/)
  assert.match(block, /a\.body/)
})

test('QX27 : les branches existantes (note/creation/modification) restent intactes', () => {
  assert.match(CHATTER_SRC, /a\.kind === 'note'/)
  assert.match(CHATTER_SRC, /a\.kind === 'creation'/)
  assert.match(CHATTER_SRC, /a\.kind === 'modification'/)
})

test('VX23 : LeadForm.jsx délègue le rendu du chatter à ChatterTimeline (plus de logique inline)', () => {
  assert.match(LEADFORM_SRC, /import ChatterTimeline from '\.\.\/\.\.\/components\/ChatterTimeline'/)
  assert.match(LEADFORM_SRC, /<ChatterTimeline entries=\{historique\} \/>/)
  // L'ancienne logique de branchement par kind n'est plus dupliquée ici.
  assert.doesNotMatch(LEADFORM_SRC, /a\.kind === 'appel'/)
})
