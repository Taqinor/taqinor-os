// VX89 — LeadForm : Escape + autofocus via ResponsiveDialog (et correction du
// « done » menteur de MB4 — fact-check : LeadForm.jsx utilisait encore un
// shell brut `div.modal-overlay`, jamais migré). Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormVX89ResponsiveDialog.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')

test('VX89 : LeadForm.jsx importe ResponsiveDialog (comme ClientForm.jsx)', () => {
  assert.match(SRC, /import \{ ResponsiveDialog \} from '\.\.\/\.\.\/ui\/ResponsiveDialog'/)
})

test('VX89 : le shell brut div.modal-overlay a disparu', () => {
  assert.doesNotMatch(SRC, /className="modal-overlay"/)
  assert.doesNotMatch(SRC, /className="modal modal-xl"/)
})

test('VX89 : ResponsiveDialog est monté avec open + onOpenChange → onClose', () => {
  assert.match(SRC, /<ResponsiveDialog/)
  assert.match(SRC, /onOpenChange=\{\(o\) => \{ if \(!o\) onClose\(\) \}\}/)
})

test('VX89 : le champ Nom porte autoFocus', () => {
  // VX193 — migré vers <Input> (FormField) pour aria-invalid/aria-describedby ;
  // l'autoFocus reste posé explicitement sur ce même champ.
  assert.match(SRC, /<Input id="lf-nom" autoFocus/)
})

test('VX89 : le lead-form-layout interne (nav + modal-body) reste intact', () => {
  assert.match(SRC, /<div className="lead-form-layout">/)
  assert.match(SRC, /<nav className="lead-nav" aria-label="Sections du lead">/)
  assert.match(SRC, /<div className="modal-body" ref=\{bodyRef\} onScroll=\{onBodyScroll\}>/)
})

test('VX89 : le bouton fermer existant reste l\'unique fermeture (showClose désactivé sur ResponsiveDialog)', () => {
  assert.match(SRC, /showClose=\{false\}/)
  assert.match(SRC, /className="modal-close" onClick=\{onClose\}/)
})
