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
// SPL216 : le DOM du builder (rp9-*) vit désormais dans atelier/BuilderDom.jsx ;
// on lit ce fichier ET ToitureDesign.jsx (qui l'appelle).
// Coque (22/11) : BuilderDom est découpé en quatre groupes DÉPLACÉS tels quels (même sous-arbre
// chacun) — on lit les quatre, dans l'ordre du DOM, puis BuilderDom et ToitureDesign.
const SRC = ['BuilderCarte', 'BuilderOutils', 'BuilderToit', 'BuilderPose', 'BuilderDom']
  .map((n) => readFileSync(join(HERE, `../../features/calepinage/atelier/${n}.jsx`), 'utf8')).join(String.fromCharCode(10))
  + readFileSync(join(HERE, 'ToitureDesign.jsx'), 'utf8')

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

test('ACAL434 : le bandeau du soleil est monté dans BuilderDom', () => {
  for (const id of ['rp9-sun-controls', 'rp9-sun-hour', 'rp9-sun-hour-value']) {
    assert.match(SRC, new RegExp(`id="${id}"`), `id="${id}" absent de BuilderDom.jsx`)
  }
  assert.match(SRC, /id="rp9-sun-hour" type="range" min="6" max="18"/)
  assert.equal((SRC.match(/data-sun-season="/g) || []).length, 2)
})

test('ACAL436 : la bascule de la carte d\'accès solaire est montée dans BuilderDom', () => {
  for (const id of ['rp9-heatmap-toggle', 'rp9-heatmap-note']) {
    assert.match(SRC, new RegExp(`id="${id}"`), `id="${id}" absent de BuilderDom.jsx`)
  }
  assert.match(SRC, /id="rp9-heatmap-toggle"[^>]*aria-pressed="false"/)
})

test('ACAL503 : `.rp9-btn` et `.rp9-input` ont une règle (cadre, 44 px, aucune couleur littérale)', () => {
  const CSS = readFileSync(join(HERE, '../../styles/roofbuilder.css'), 'utf8')
  for (const sel of ['.rp9-host .rp9-btn', '.rp9-host .rp9-input']) {
    const debut = CSS.indexOf(`${sel} {`)
    assert.ok(debut >= 0, `${sel} sans règle dans roofbuilder.css`)
    const bloc = CSS.slice(debut, CSS.indexOf('}', debut))
    assert.match(bloc, /min-height:\s*2\.75rem/, `${sel} : min-height 2.75rem absent`)
    assert.match(bloc, /border/, `${sel} : bordure absente`)
    assert.doesNotMatch(bloc, /#|rgb\(/, `${sel} : couleur littérale`)
  }
  assert.match(CSS, /\.rp9-host \.rp9-btn\[aria-pressed='true'\]/)
  assert.match(CSS, /\.rp9-host \.rp9-btn:focus-visible/)
  assert.match(CSS, /\.rp9-host \.rp9-input:focus-visible/)
})

test('ACAL493 : hauteur et bandeau « Compte NON engageable » montés', () => {
  const debut = SRC.indexOf('id="rp9-obs-edit"')
  assert.ok(debut >= 0)
  const fin = SRC.indexOf('id="rp9-obs-engage"')
  assert.ok(fin > debut, 'rp9-obs-engage absent ou avant rp9-obs-edit')
  const carte = SRC.slice(debut, fin)
  assert.match(carte, /id="rp9-obs-height"[^>]*inputMode="decimal"/)
  assert.doesNotMatch(carte.slice(carte.indexOf('id="rp9-obs-height"'), carte.indexOf('id="rp9-obs-height"') + 200), /value=/)
  // le bandeau est HORS de la carte (la carte se ferme avant lui) et masqué par défaut
  assert.match(SRC.slice(fin - 40, fin + 80), /id="rp9-obs-engage" role="status" hidden/)
  assert.match(carte, /<\/div>\s*\{\/\* ACAL493/, 'le bandeau doit suivre la fermeture de la carte')
})

test('ACAL1032 : Dupliquer et trame sont montés dans `rp9-obs-edit`', () => {
  const debut = SRC.indexOf('id="rp9-obs-edit"')
  const fin = SRC.indexOf('id="rp9-obs-engage"')
  const carte = SRC.slice(debut, fin)
  for (const id of ['rp9-obs-duplicate', 'rp9-obs-grid-place']) {
    assert.ok(carte.includes(`id="${id}"`), `${id} absent de la carte obstacle`)
  }
  // les trois champs de la trame : ids `rp9-obs-grid-<clé>` bâtis sur la liste des clés
  assert.match(carte, /\['spacing', [^\]]*\], \['cols', [^\]]*\], \['rows', [^\]]*\]/)
  const i = carte.indexOf('id={`rp9-obs-grid-${k}`}')
  assert.ok(i >= 0, 'champ de la trame absent')
  const balise = carte.slice(i, carte.indexOf('className', i))
  assert.match(balise, /inputMode="decimal"/)
  assert.doesNotMatch(balise, /value=|defaultValue=/, 'aucune valeur initiale')
  assert.match(carte, /<details[^>]*>\s*<summary[^>]*>[^<]*Poser en série/, 'trame dans un <details>')
  assert.doesNotMatch(carte, /<details[^>]*open/, '<details> fermé par défaut')
})

test("ACAL497 : l'outil d'ombre est monté", () => {
  const debut = SRC.indexOf('id="rp9-shade-add"')
  assert.ok(debut >= 0, 'rp9-shade-add absent de BuilderDom')
  const bloc = SRC.slice(debut - 800, debut + 3000)
  for (const id of ['rp9-shade-add', 'rp9-shade-clear', 'rp9-shade-hour', 'rp9-shade-hour-value', 'rp9-shade-list', 'rp9-shade-note']) {
    assert.ok(bloc.includes(`id="${id}"`), `${id} absent`)
  }
  const h = bloc.indexOf('id="rp9-shade-hour"')
  const balise = bloc.slice(h, bloc.indexOf('/>', h))
  assert.match(balise, /inputMode="decimal"/)
  assert.doesNotMatch(balise, /value=|type="range"/, 'aucune heure proposée')
  assert.match(bloc, /id="rp9-shade-note"[^>]*aria-live="polite"/)
})

test('ACAL504 : la hauteur du bâtiment est montée', () => {
  const i = SRC.indexOf('id="rp9-shade-height"')
  assert.ok(i >= 0, 'rp9-shade-height absent de BuilderDom')
  const balise = SRC.slice(i, SRC.indexOf('/>', i))
  assert.match(balise, /inputMode="decimal"/)
  assert.doesNotMatch(balise, /value=|defaultValue=/, 'aucune valeur initiale')
  // la note est dans le MÊME parent que le champ : c'est là que `ensurePanneauBatiment` accroche `rp11-batiment`
  const parent = SRC.slice(SRC.lastIndexOf('<div', i), SRC.indexOf('id="rp9-shade-list"', i))
  assert.ok(parent.includes('id="rp9-shade-height-note"'), 'rp9-shade-height-note hors du parent du champ')
  assert.match(parent, /id="rp9-shade-height-note"[^>]*aria-live="polite"/)
})
