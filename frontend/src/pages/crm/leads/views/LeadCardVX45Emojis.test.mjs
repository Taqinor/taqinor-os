// VX45 — le bouton devis-auto (⚡) et la micro-icône readiness « prêt à
// deviser » de LeadCard.jsx rendent l'icône lucide Zap au lieu d'un emoji brut.
// LB13 — anatomie 4 zones : le bouton ⚡ vit dans la rangée d'actions rapides
// (kb-flash) ; la readiness « devis prêt » est une micro-icône 12px dans le
// pied. Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/LeadCardVX45Emojis.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

test('VX45 : Zap importé depuis lucide-react', () => {
  assert.match(SRC, /import \{[^}]*\bZap\b[^}]*\} from 'lucide-react'/)
})

test('VX45 : le bouton devis-auto (kb-flash) rend <Zap /> au lieu de ⚡', () => {
  const start = SRC.indexOf('"kb-flash')
  assert.ok(start > -1, 'bouton kb-flash introuvable')
  const block = SRC.slice(start, start + 900)
  assert.match(block, /<Zap size=\{14\} aria-hidden="true" \/>/)
})

test('VX45 : la micro-icône « prêt à deviser » rend <Zap /> au lieu de ⚡', () => {
  const start = SRC.indexOf('kb-readi-devis')
  assert.ok(start > -1, 'micro-icône readiness devis introuvable')
  const block = SRC.slice(start, start + 300)
  assert.match(block, /<Zap size=\{12\} aria-hidden="true" \/>/)
})
