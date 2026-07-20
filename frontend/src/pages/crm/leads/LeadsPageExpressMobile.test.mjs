// LB26→LB43 — Express vit dans le menu ⋯ sur TOUS les gabarits (retour
// fondateur : une seule ligne de contrôle façon Odoo — plus de bouton
// standalone desktop, plus de fourche isMobile dans LeadsPage). Verified
// against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageExpressMobile.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB43 : Express est un item du menu ⋯ — sans condition de gabarit', () => {
  const idx = SRC.indexOf('onSelect={() => setShowExpressModal(true)}')
  assert.ok(idx > 0, 'item Express introuvable')
  const block = SRC.slice(Math.max(0, idx - 120), idx + 120)
  assert.match(block, /DropdownMenuItem/)
  assert.match(block, /Express/)
  assert.doesNotMatch(block, /isMobile/)
})

test('LB43 : plus AUCUNE fourche isMobile dans LeadsPage (la ligne de contrôle est unique)', () => {
  assert.doesNotMatch(SRC, /useIsMobile/)
  assert.doesNotMatch(SRC, /\bisMobile\b/)
})

test('LB43 : plus de bouton Express standalone dans l’en-tête', () => {
  assert.doesNotMatch(SRC, /Saisie express : nom \+ téléphone \+ canal/)
})
