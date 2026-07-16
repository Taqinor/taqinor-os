// QX30fe — Engagement-triggered follow-up engine (frontend half): the action
// board renders the engagement-triggered queue rows the backend produces
// (Notifications + queue) with a prefilled wa.me draft. Backend contract:
// board.buckets.engagement_relance (same {count, ids} shape) + optional
// board.wa_drafts[id]. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/ventes/DevisActionBoardEngagementQueue.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisActionBoardPage.jsx'), 'utf8')

test('QX30 : une 5e file "Relance engagement" est déclarée', () => {
  assert.match(SRC, /key: 'engagement_relance', label: 'Relance engagement'/)
})

test('QX30 : waHref accepte un brouillon et pré-remplit ?text= (encodé)', () => {
  const start = SRC.indexOf('const waHref = (raw, draft)')
  assert.ok(start > 0, 'waHref(raw, draft) introuvable — signature non mise à jour')
  const body = SRC.slice(start, start + 400)
  assert.match(body, /encodeURIComponent\(draft\)/)
  assert.match(body, /draft \? `https:\/\/wa\.me\/\$\{digits\}\?text=/)
})

test('QX30 : chaque ligne lit le brouillon depuis board.wa_drafts[id]', () => {
  assert.match(SRC, /const draft = board\.wa_drafts\?\.\[id\]/)
  assert.match(SRC, /waHref\(d\?\.client_whatsapp \?\? d\?\.client_telephone \?\? d\?\.telephone, draft\)/)
})

test('QX30 : sans brouillon, le lien wa.me reste nu (comportement QX29 inchangé)', () => {
  const start = SRC.indexOf('const waHref = (raw, draft)')
  const body = SRC.slice(start, start + 400)
  assert.match(body, /: `https:\/\/wa\.me\/\$\{digits\}`/)
})
