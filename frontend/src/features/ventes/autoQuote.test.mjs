// QJR245 / QJR602 (D-QJR5-13) — plus aucun palier n'est appliqué à une taille
// explicite : la notice `noticePalierKwc` (stub qui rendait toujours `null`,
// sans appelant de production) est supprimée (ERR-QJR576-602-RESIDUS-SUPERSEDE).
// Ce fichier ne garde que les gardes de non-réintroduction du texte
// « Palier appliqué » (le comportement exécuté vit dans
// autoQuote.tailleExplicite.test.jsx).
//
// Run : node --test src/features/ventes/autoQuote.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')
const LEAD_DEVIS_PANEL = readFileSync(
  join(HERE, '..', '..', 'pages', 'crm', 'leads', 'LeadDevisPanel.jsx'), 'utf8')
const DEVIS_TAB = readFileSync(
  join(HERE, '..', 'crm', 'workspace', 'DevisTab.jsx'), 'utf8')

test('QJR602 — plus aucun texte « Palier appliqué » dans autoQuote.js, DevisTab.jsx ni LeadDevisPanel.jsx', () => {
  assert.doesNotMatch(SRC, /Palier appliqué :/)
  assert.doesNotMatch(DEVIS_TAB, /Palier appliqué :/)
  assert.doesNotMatch(LEAD_DEVIS_PANEL, /Palier appliqué :/)
})

test('le stub noticePalierKwc est supprimé (aucun appelant de production)', () => {
  assert.doesNotMatch(SRC, /noticePalierKwc/)
  assert.doesNotMatch(DEVIS_TAB, /noticePalierKwc/)
  assert.doesNotMatch(LEAD_DEVIS_PANEL, /noticePalierKwc/)
})

// AGR126 — l'agricole part au SERVEUR (POST /ventes/devis/auto/, AGR124) :
// la composition JS du pompage et ses défauts supposés (« tri », « immergée »,
// 20 m) ne reviennent jamais dans createAutoQuote. Le comportement exécuté
// (un seul appel serveur, 422 rendu tel quel) vit dans
// autoQuote.atomique.test.jsx.
test('AGR126 — plus de composition agricole JS ni de défauts supposés dans autoQuote.js', () => {
  assert.doesNotMatch(SRC, /autoFillPompage\(/)
  assert.doesNotMatch(SRC, /pompageSelection\(/)
  assert.doesNotMatch(SRC, /alim: 'tri', typePompe: 'immergee', distance: '20'/)
})
