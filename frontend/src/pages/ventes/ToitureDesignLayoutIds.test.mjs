// Lane restauration (25/08) — les DEUX modes de déplacement manuel des
// panneaux (« ▦ Emplacements validés » / « ✥ Placement libre ») avaient
// disparu de l'écran ERP /devis-design/:id : le bloc rp9-layout-window/
// rp9-layout-panel existait dans apps/web/toiture-3d-pro-11.astro mais
// n'avait JAMAIS été porté dans ToitureDesign.jsx (0 occurrence de
// rp9-layout avant ce correctif). Le moteur PARTAGÉ
// (apps/web/src/scripts/roofPro11/layoutEditor.ts) cherche ces ids par
// `document.getElementById` — un id manquant ou renommé rend le bouton
// mort SILENCIEUSEMENT (le module bascule sur un mini-panneau de repli
// si `rp9-layout-window` est absent, cf. layoutEditor.ts:170). Ce test
// épingle la présence de CHAQUE id contre la SOURCE (pas de node_modules
// installés dans ce worktree/lane — même convention que
// DevisListDeepLinks.test.mjs / MesActivitesPage.test.mjs).
//   node --test src/pages/ventes/ToitureDesignLayoutIds.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ToitureDesign.jsx'), 'utf8')

// Liste EXHAUSTIVE des ids rp9-layout-*/rp9-free-* interrogés par
// roofPro11/layoutEditor.ts (et le sous-ensemble repris par
// roof-tool-pro11.ts pour le reset). Un id absent ici = bouton mort.
const REQUIRED_IDS = [
  'rp9-layout-window',
  'rp9-layout-toggle',
  'rp9-layout-panel',
  'rp9-layout-mode-lattice',
  'rp9-layout-mode-free',
  'rp9-free-controls',
  'rp9-free-setback',
  'rp9-free-gap',
  'rp9-free-add',
  'rp9-free-measure',
  'rp9-layout-count',
  'rp9-layout-kwc',
  'rp9-layout-free',
  'rp9-layout-cover',
  'rp9-layout-minus',
  'rp9-layout-plus',
  'rp9-layout-fill',
  'rp9-layout-reset',
  'rp9-layout-select',
  'rp9-layout-row',
  'rp9-layout-clear-sel',
  // PV34 — compteur PERMANENT « N panneaux sélectionnés » (l'un des deux manques
  // signalés par le fondateur le 25/08 : on ne savait jamais ce qu'on tenait).
  'rp9-layout-selcount',
  'rp9-layout-undo',
  'rp9-layout-redo',
  'rp9-layout-azimuth',
  'rp9-layout-az-minus',
  'rp9-layout-az-value',
  'rp9-layout-az-plus',
  'rp9-layout-grid',
  'rp9-layout-note',
]

for (const id of REQUIRED_IDS) {
  test(`ToitureDesign.jsx porte id="${id}" (moteur layoutEditor.ts)`, () => {
    assert.match(SRC, new RegExp(`id="${id}"`),
      `id="${id}" absent de ToitureDesign.jsx — layoutEditor.ts ne le trouvera pas`)
  })
}

test('les DEUX modes d\'édition (lattice/libre) sont bien deux boutons distincts', () => {
  assert.match(SRC, /id="rp9-layout-mode-lattice"[^>]*aria-pressed="true"/)
  assert.match(SRC, /id="rp9-layout-mode-free"[^>]*aria-pressed="false"/)
})

test('le bloc rp9-layout-window est masqué par défaut (hidden, dévoilé par script)', () => {
  const idx = SRC.indexOf('id="rp9-layout-window"')
  assert.ok(idx !== -1)
  const tagStart = SRC.lastIndexOf('<div', idx)
  const tagEnd = SRC.indexOf('>', idx)
  const openingTag = SRC.slice(tagStart, tagEnd)
  assert.match(openingTag, /\bhidden\b/)
})

test('le plan tactile (rp9-layout-grid) est un conteneur role=group, la souris/le doigt y déposent des cellules', () => {
  assert.match(SRC, /id="rp9-layout-grid"[^>]*role="group"/)
})

test('les réglages de placement libre (retrait de rive / écart) sont bien reliés par htmlFor', () => {
  assert.match(SRC, /htmlFor="rp9-free-setback"/)
  assert.match(SRC, /id="rp9-free-setback"/)
  assert.match(SRC, /htmlFor="rp9-free-gap"/)
  assert.match(SRC, /id="rp9-free-gap"/)
})
