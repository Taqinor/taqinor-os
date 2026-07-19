// QX25 — mobile Leads ListView hides the phone column entirely (m-hide) with
// no tap-to-call fallback; compact tel/wa icons now live in the name cell
// (never hidden). Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/views/ListViewCallReady.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ListView.jsx'), 'utf8')

test('QX25 : telHref/waHref helpers ajoutés', () => {
  assert.match(SRC, /const telHref = /)
  assert.match(SRC, /const waHref = /)
})

test('QX25 : la cellule "Lead" (jamais masquée) porte les icônes tel/wa, contrairement à la colonne Téléphone (m-hide)', () => {
  // LB18 — la cellule porte désormais aussi `.lv-sticky-name` (colonne nom
  // épinglée) : recherche sur le préfixe SANS le `>` fermant pour survivre
  // à l'ajout d'attributs (className…) sur ce même <td>.
  const start = SRC.indexOf('<td data-label="Lead"')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 2000)
  assert.match(block, /telHref\(lead\.telephone\)/)
  assert.match(block, /waHref\(lead\.whatsapp\)/)
  assert.match(block, /PhoneCall/)
  assert.match(block, /MessageCircle/)
})

test('QX25 : le clic sur les icônes de contact n\'ouvre pas la fiche (stopPropagation)', () => {
  const start = SRC.indexOf('<td data-label="Lead"')
  const block = SRC.slice(start, start + 2000)
  assert.match(block, /onClick=\{\(e\) => e\.stopPropagation\(\)\}/)
})
