// LB26 — Express rejoint le menu ⋯ sous 768px (le header respire, blueprint
// D5) : hook CANONIQUE `useIsMobile` (ui/ResponsiveDialog, déjà adopté par
// LeadWorkspace) décide lequel des DEUX rend — jamais les deux à la fois, et
// jamais une nouvelle copie locale du hook. Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageExpressMobile.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB26 : useIsMobile importé depuis le hook CANONIQUE (jamais une copie locale)', () => {
  assert.match(SRC, /import \{ useIsMobile \} from '\.\.\/\.\.\/\.\.\/ui\/ResponsiveDialog'/)
  assert.match(SRC, /const isMobile = useIsMobile\(\)/)
  assert.doesNotMatch(SRC, /function useIsMobile\(/)
})

test('LB26 : le bouton Express standalone ne rend QUE sur desktop (!isMobile)', () => {
  const idx = SRC.indexOf('{!isMobile && (')
  assert.ok(idx > 0)
  const block = SRC.slice(idx, idx + 250)
  assert.match(block, /Saisie express : nom \+ téléphone \+ canal/)
  assert.match(block, /setShowExpressModal\(true\)/)
})

test('LB26 : l’item de menu Express ne rend QUE sur mobile (isMobile), dans le menu ⋯', () => {
  const idx = SRC.indexOf('{isMobile && (')
  assert.ok(idx > 0)
  const block = SRC.slice(idx, idx + 200)
  assert.match(block, /onSelect=\{\(\) => setShowExpressModal\(true\)\}/)
  assert.match(block, /Express/)
})
