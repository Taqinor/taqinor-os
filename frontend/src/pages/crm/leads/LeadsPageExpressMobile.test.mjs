// LB26→LB43→LB47 — Express vit dans le menu ⋯ sur TOUS les gabarits ; le
// gabarit (useIsMobile, hook CANONIQUE) redevient une fourche LÉGITIME au
// service du cockpit une-ligne : au téléphone le ⋯ porte AUSSI le changement
// de vue et les vues enregistrées, la création vit dans le FAB (l'en-tête ne
// rend plus de bouton Nouveau), et le bandeau KPI part en panelTop du
// panneau Filtres. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageExpressMobile.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB47 : useIsMobile importé depuis le hook CANONIQUE (jamais une copie locale)', () => {
  assert.match(SRC, /import \{ useIsMobile \} from '\.\.\/\.\.\/\.\.\/ui\/ResponsiveDialog'/)
  assert.match(SRC, /const isMobile = useIsMobile\(\)/)
  assert.doesNotMatch(SRC, /function useIsMobile\(/)
})

test('LB43 : Express est un item du menu ⋯ — sans condition de gabarit', () => {
  const idx = SRC.indexOf('onSelect={() => setShowExpressModal(true)}')
  assert.ok(idx > 0, 'item Express introuvable')
  const block = SRC.slice(Math.max(0, idx - 120), idx + 120)
  assert.match(block, /DropdownMenuItem/)
  assert.match(block, /Express/)
  assert.doesNotMatch(block, /isMobile/)
})

test('LB47→LB54 : au téléphone, ⋯ porte le changement de vue (items VIEWS) ; les vues enregistrées vivent dans le PICKER', () => {
  assert.match(SRC, /import ViewSwitcher, \{ VIEWS \} from '\.\/ViewSwitcher'/)
  const idx = SRC.indexOf('{VIEWS.map((vw) => {')
  assert.ok(idx > 0, 'items de vues ⋯ introuvables')
  const before = SRC.slice(Math.max(0, idx - 600), idx)
  assert.match(before, /\{isMobile && \(/)
  // LB54 : plus d'items SavedView dans ⋯ — le LeadViewPicker (rendu desktop
  // ET mobile) les porte.
  assert.doesNotMatch(SRC, /savedViews\.map\(\(v\) => \(\s*<DropdownMenuItem/)
  assert.match(SRC, /<LeadViewPicker/)
})

test('LB47 : la création au téléphone = le FAB (nom accessible « + Nouveau lead ») — plus de bouton d\'en-tête mobile', () => {
  assert.match(SRC, /\{!isMobile && <Button onClick=\{openNew\}>\+ Nouveau lead<\/Button>\}/)
  assert.match(SRC, /aria-label="\+ Nouveau lead"/)
})
