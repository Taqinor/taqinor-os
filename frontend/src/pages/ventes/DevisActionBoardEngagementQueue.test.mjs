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
import { waHref } from '../../lib/contactLinks.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisActionBoardPage.jsx'), 'utf8')

test('QX30 : une 5e file "Relance engagement" est déclarée', () => {
  assert.match(SRC, /key: 'engagement_relance', label: 'Relance engagement'/)
})

// QJR635 — waHref n'est plus une copie locale : c'est LE constructeur
// partagé (lib/contactLinks), testé ici sur son COMPORTEMENT (brouillon
// pré-rempli, lien nu sans brouillon, numéro normalisé).
test('QX30 : waHref accepte un brouillon et pré-remplit ?text= (encodé)', () => {
  assert.match(SRC, /import \{ waHref \} from '\.\.\/\.\.\/lib\/contactLinks'/)
  assert.equal(waHref('+212661000029', 'Bonjour & merci'),
    `https://wa.me/212661000029?text=${encodeURIComponent('Bonjour & merci')}`)
})

test('QX30 : chaque ligne lit le brouillon depuis board.wa_drafts[id]', () => {
  assert.match(SRC, /const draft = board\.wa_drafts\?\.\[id\]/)
  assert.match(SRC, /waHref\(d\?\.client_whatsapp \|\| d\?\.client_telephone \|\| d\?\.telephone, draft\)/)
})

test('QX30 : sans brouillon, le lien wa.me reste nu (comportement QX29 inchangé)', () => {
  assert.equal(waHref('+212661000029', undefined), 'https://wa.me/212661000029')
})
