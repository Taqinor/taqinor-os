// VX45 — le bouton devis-auto (⚡) et le chip « Prêt à deviser en 1 clic »
// de LeadCard.jsx rendent l'icône lucide Zap au lieu d'un emoji brut.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/LeadCardVX45Emojis.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

test('VX45 : Zap importé depuis lucide-react', () => {
  assert.match(SRC, /import \{ Zap \} from 'lucide-react'/)
})

test('VX45 : le bouton devis-auto (kb-flash) rend <Zap /> au lieu de ⚡', () => {
  const start = SRC.indexOf('className="kb-flash"')
  const block = SRC.slice(start, start + 900)
  assert.match(block, /<Zap size=\{14\} aria-hidden="true" \/>/)
})

test('VX45 : le chip « Prêt à deviser en 1 clic » rend <Zap /> au lieu de ⚡', () => {
  assert.match(SRC, /<Zap size=\{11\} aria-hidden="true" \/> Prêt à deviser en 1 clic/)
})
