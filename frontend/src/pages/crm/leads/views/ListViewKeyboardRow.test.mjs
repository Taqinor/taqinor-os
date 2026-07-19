// LB21 — lignes ouvrables au clavier (recon-05 a11y #5 : onClick sur <tr>,
// aucun tabIndex/role/onKeyDown) + le nom devient un vrai élément
// interactif sémantique. L'adoption du PerduPopover partagé (LB15) est
// DIFFÉRÉE — frontend/src/pages/crm/leads/PerduPopover.jsx n'existe pas
// encore dans cette lane (lane LB2) ; le popover local (« ✗ Perdu ») reste
// donc tel quel ici, à câbler par l'orchestrateur au fold. Verified against
// SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/ListViewKeyboardRow.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ListView.jsx'), 'utf8')

test('LB21 : tr.lv-row est focusable (tabIndex=0) et gère Enter/Espace via un handler DÉDIÉ', () => {
  const m = SRC.match(/<tr\s*\n\s*className=\{`lv-row/)
  assert.ok(m, 'ouverture de <tr> lv-row introuvable')
  const start = m.index
  const block = SRC.slice(start, start + 300)
  assert.match(block, /tabIndex=\{0\}/)
  assert.match(block, /onKeyDown=\{onRowKeyDown\}/)
  assert.match(block, /onClick=\{\(\) => onOpenLead\(lead\)\}/)
})

test('LB21 : onRowKeyDown ne réagit qu\'à Enter/Espace ET jamais depuis un contrôle interne (e.target.closest)', () => {
  const start = SRC.indexOf('const onRowKeyDown = (e) => {')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 350)
  assert.match(block, /e\.key !== 'Enter' && e\.key !== ' '/)
  assert.match(block, /e\.target\.closest\('button, a, input, select, textarea, \[role="button"\]'\)/)
  assert.match(block, /e\.preventDefault\(\)/)
  assert.match(block, /onOpenLead\(lead\)/)
})

test('LB21 : le nom du lead (.lv-lead-name) est un vrai <button> sémantique, stopPropagation contre le double déclenchement', () => {
  const m = SRC.match(/<button\s*\n\s*type="button"\s*\n\s*className="lv-lead-name"/)
  assert.ok(m, 'bouton .lv-lead-name introuvable')
  const start = m.index
  const block = SRC.slice(start, start + 250)
  assert.match(block, /onClick=\{\(e\) => \{ e\.stopPropagation\(\); onOpenLead\(lead\) \}\}/)
  assert.match(block, /\{fullName\(lead\) \|\| '—'\}/)
})

test('LB21 : contrat conservé — tr.lv-row/.ie-cell/select.ie-input toujours intacts (aucune régression du refit clavier)', () => {
  assert.match(SRC, /className=\{`lv-row/)
  // InlineEdit (composants/InlineEdit.jsx) pose déjà .ie-cell/.ie-input —
  // non retouché par cette lane, juste vérifié toujours importé/utilisé.
  assert.match(SRC, /import InlineEdit from '\.\.\/\.\.\/\.\.\/\.\.\/components\/InlineEdit'/)
  assert.match(SRC, /<InlineEdit\b/)
})

test('LB21 : le popover local « ✗ Perdu » est CONSERVÉ tel quel (adoption PerduPopover différée à cette lane)', () => {
  // La lane LB2 (carte) n'a pas encore livré PerduPopover.jsx dans ce
  // worktree — cette lane garde donc le Popover en ligne existant plutôt
  // que de dupliquer une seconde copie. Le fold de l'orchestrateur
  // effectuera le remplacement une fois PerduPopover disponible.
  assert.match(SRC, /label="Marquer perdu"/)
  assert.match(SRC, /Popover$/m)
})
