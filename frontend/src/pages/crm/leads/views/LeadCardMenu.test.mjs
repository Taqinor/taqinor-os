// LB15 — Menu ••• (DropdownMenu) sur la carte + adoption du PerduPopover
// PARTAGÉ. Le bouton ✗ 20×20 a quitté la face ; toutes les actions du lead
// sont dans le menu (atteignables au clavier via Radix). La popover perdu
// dupliquée byte-à-byte a disparu de LeadCard (un seul composant perdu dans le
// code). Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/LeadCardMenu.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

test('LB15 : LeadCard adopte le PerduPopover partagé', () => {
  assert.match(SRC, /import PerduPopover from '\.\.\/PerduPopover'/)
  assert.match(SRC, /<PerduPopover\b/)
  // La popover perdu dupliquée locale a disparu (plus de datalist kb-motifs
  // inline ni de crmApi.getMotifsPerte dans LeadCard).
  assert.doesNotMatch(SRC, /<datalist id=\{`kb-motifs-\$\{lead\.id\}`\}>/)
  assert.doesNotMatch(SRC, /crmApi\.getMotifsPerte/)
})

test('LB15 : la popover perdu est CONTRÔLÉE par le menu et ancrée à la carte', () => {
  assert.match(SRC, /open=\{perduOpen\}/)
  assert.match(SRC, /onOpenChange=\{setPerduOpen\}/)
  assert.match(SRC, /anchor=\{<span className="kb-perdu-anchor" aria-hidden="true" \/>\}/)
})

test('LB15 : menu ••• (DropdownMenu) avec bouton labellisé « Actions du lead »', () => {
  assert.match(SRC, /import \{\s*\n?\s*DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,/)
  assert.match(SRC, /<DropdownMenu>/)
  assert.match(SRC, /className="kb-card-menu-btn"/)
  assert.match(SRC, /aria-label=\{`Actions du lead \$\{nomComplet\}`\}/)
  assert.match(SRC, /<MoreHorizontal size=\{16\} aria-hidden="true" \/>/)
})

test('LB15 : le menu expose Ouvrir · Planifier · Devis auto · Marquer perdu · Archiver (conditionnels aux callbacks)', () => {
  assert.match(SRC, /<DropdownMenuItem onSelect=\{\(\) => onOpen\(lead\)\}>Ouvrir<\/DropdownMenuItem>/)
  assert.match(SRC, /onSelect=\{\(\) => onPlanifierRelance\(lead\)\}/)
  assert.match(SRC, /\{onAutoQuote && lead\.devis_auto\?\.pret && \(/)
  assert.match(SRC, /\{!perdu && onMarkPerdu && \(/)
  assert.match(SRC, /destructive/)
  assert.match(SRC, /✗ Marquer perdu/)
  assert.match(SRC, /\{onArchive && \(/)
})

test('LB15 : « Marquer perdu » depuis le menu ouvre la popover au frame suivant (anti-fermeture)', () => {
  assert.match(SRC, /requestAnimationFrame\(\(\) => setPerduOpen\(true\)\)/)
})
