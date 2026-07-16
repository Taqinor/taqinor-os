// QX27 — Action-row sanity: secondary/rare devis actions (Réviser, Approuver
// remise, Contacter mon supérieur, Email) move into a "⋯" DropdownMenu
// (pattern already used in crm/leads/views/ListView.jsx) instead of gonflating
// the row with 10-14 buttons. Verified against SOURCE (no node_modules in
// this worktree/lane).
//   node --test src/pages/ventes/DevisListActionsMenu.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

test('QX27 : DropdownMenu importé depuis ../../ui (même primitive que ListView.jsx)', () => {
  assert.match(SRC, /DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,\s*\n\s*DropdownMenuItem, DropdownMenuLabel,/)
})

test('QX27 : les actions secondaires sont dans le menu « ⋯ », plus des boutons directs', () => {
  // VX20 a réaligné le menu de ligne sur `align="end"` et y a replié davantage
  // d'actions : on découpe TOUT le contenu du menu (jusqu'à sa fermeture).
  const start = SRC.indexOf('<DropdownMenuContent align="end">')
  assert.ok(start > 0, 'menu de la ligne devis introuvable')
  const block = SRC.slice(start, SRC.indexOf('</DropdownMenuContent>', start))
  assert.match(block, /Réviser \(nouvelle version\)/)
  assert.match(block, /Approuver la remise/)
  assert.match(block, /Contacter mon supérieur/)
  assert.match(block, /Envoyer par email/)
})

test('QX27 : les anciens boutons directs « Réviser »/« Approuver remise »/« Email » ont disparu', () => {
  assert.doesNotMatch(SRC, />\s*Réviser\s*<\/Button>/)
  assert.doesNotMatch(SRC, />\s*Approuver remise\s*<\/Button>/)
  assert.doesNotMatch(SRC, />\s*Email\s*<\/Button>/)
})

test('QX27 : les actions qui font avancer le funnel restent des boutons directs (jamais dans le menu)', () => {
  // Envoyer / Accepter / Refuser / BC / Chantier / Générer facture / PDF /
  // Variante / Copier le lien / Supprimer conservent leur bouton visible.
  for (const label of ['Envoyer', 'Accepter', 'Refuser', 'BC', 'Générer facture', 'Variante', 'Copier le lien', 'Supprimer']) {
    assert.match(SRC, new RegExp(label))
  }
  // Ils ne sont pas rendus comme DropdownMenuItem.
  const menuBlock = SRC.slice(SRC.indexOf('<DropdownMenuContent align="start">'), SRC.indexOf('</DropdownMenu>'))
  assert.doesNotMatch(menuBlock, /Accepter|Refuser|Générer facture/)
})
