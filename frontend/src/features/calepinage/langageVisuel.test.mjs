// ACAL427 — UN SEUL langage visuel dans le module Calepinage : les classes
// héritées du site public (liste L) migrent vers les jetons de l'ERP. Le garde
// lit les SOURCES (pas de node_modules requis) et compte L par fichier non-test
// de features/calepinage/ + ToitureDesign.jsx. ACAL479 : STRICT, zéro classe
// tolérée dans tout fichier non-test (un fichier neuf compris), aucune table
// d'exception.
//   node --test src/features/calepinage/langageVisuel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
const SRC = fileURLToPath(new URL('../../', import.meta.url))
const L = /\b(?:cine|lune|nuit)-|\b(?:tech-label|rule-brass)\b|text-brass-\d+|text-alert-\d+|text-white|(?:border|bg|divide)-white\/\d+/g
const C = 'features/calepinage/'
const ENVELOPPE = [
  ...['BuilderDom', 'OutilsVue', 'Rail', 'RetourAtelier'].map((n) => `${C}atelier/${n}.jsx`),
  'pages/ventes/ToitureDesign.jsx',
]
function fichiers(dir, out = []) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name)
    if (e.isDirectory()) { if (e.name !== '__golden__' && e.name !== 'node_modules') fichiers(p, out) }
    else if (/\.(jsx?|mjs)$/.test(e.name) && !/\.test\./.test(e.name)) out.push(p)
  }
  return out
}
const cibles = [...fichiers(join(SRC, C)), join(SRC, ENVELOPPE[4])].map((p) => relative(SRC, p).split(sep).join('/'))
const compte = (f) => (readFileSync(join(SRC, f), 'utf8').match(L) || []).length
test("les 5 fichiers de l'enveloppe n'ont plus aucune classe de L", () => {
  for (const f of ENVELOPPE) assert.equal(compte(f), 0, `${f} porte encore des classes du site public`)
})
test('ACAL479 : aucune classe héritée du site public, nulle part, sans exception', () => {
  for (const f of cibles) assert.equal(compte(f), 0, `${f} : ${(readFileSync(join(SRC, f), 'utf8').match(L) || []).join(', ')} (classe(s) du site public)`)
})
const SOUS_DOSSIERS = [
  'pompage/PompagePanel.jsx', 'equipements/FichesIncompletes.jsx', 'electrique/SaisiesElectriques.jsx',
  'electrique/Raccordement.jsx', 'electrique/VerdictElectrique.jsx', 'electrique/MaterielElectrique.jsx',
  'electrique/DecisionsElectriques.jsx', 'production/BandeauProvenanceProduction.jsx', 'plan/AffectationChaines.jsx',
].map((n) => C + n)
test("ACAL442 : les 9 fichiers des sous-dossiers n'ont plus de classe de L", () => {
  for (const f of SOUS_DOSSIERS) {
    assert.equal(compte(f), 0, `${f} porte encore des classes du site public`)
  }
})
test("ACAL438 : aucun texte de l'atelier sous 12 px", () => {
  for (const f of ['DossiersReglementaires.jsx', 'commun/Provenance.jsx', 'plan/AffectationChaines.jsx']) {
    assert.ok(!/text-\[1[01]px\]/.test(readFileSync(join(SRC, C + f), 'utf8')), `${f} porte text-[10px]/text-[11px]`)
  }
  const css = readFileSync(join(SRC, 'styles/roofbuilder.css'), 'utf8')
  for (const m of css.matchAll(/font(?:-size)?:\s*(?:[0-9]+\s+)?(0?\.\d+)rem/g)) assert.ok(parseFloat(m[1]) >= 0.75, `roofbuilder.css : ${m[0]} < 0,75 rem`)
})

// ACAL969 — GARDE « K-STYLE » : toute classe `rp9-*` posée par le constructeur (`className = '…'` dans
// `apps/web/src/scripts/roof-tool-pro11.ts`) a une règle dans `roofbuilder.css`, un seul état « choisi »
// (`[aria-pressed='true']`, fond doré), un survol réservé aux pointeurs qui survolent, un badge « recommandé »
// distinct (sans fond, ≥ 12 px).
const CSS_ROOFBUILDER = readFileSync(join(SRC, 'styles/roofbuilder.css'), 'utf8')
const SCRIPT_PRO11 = readFileSync(join(SRC, '../../apps/web/src/scripts/roof-tool-pro11.ts'), 'utf8')
const declarations = (corps) => Object.fromEntries(corps.split(';')
  .map((d) => d.split(':').map((x) => x.trim())).filter(([nom, valeur]) => nom && valeur !== undefined))
const regles = (css) => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({ selecteur: m[1].trim(), corps: m[2] }))

test('ACAL969 : toute classe rp9-* créée par roof-tool-pro11.ts a une règle dans roofbuilder.css', () => {
  const creees = new Set()
  for (const m of SCRIPT_PRO11.matchAll(/\.className\s*=\s*'([^']*)'/g)) {
    for (const c of m[1].split(/\s+/)) if (/^rp9-/.test(c)) creees.add(c)
  }
  assert.ok(creees.size > 0, 'aucune classe rp9-* repérée : le motif de la garde ne lit plus le script')
  const sansRegle = [...creees].filter((c) => !new RegExp(`\.${c}(?![\w-])`).test(CSS_ROOFBUILDER))
  assert.deepEqual(sansRegle, [], `classe(s) créée(s) par le constructeur sans règle dans roofbuilder.css : ${sansRegle.join(', ')}`)
})

test('ACAL969 : le survol de rp9-chip n’existe que sous @media (hover: hover)', () => {
  const survolsNus = []
  let reste = CSS_ROOFBUILDER
  // On retire chaque bloc @media (hover: hover) { … } (accolades équilibrées) avant de chercher le survol.
  for (let i = reste.indexOf('@media (hover: hover)'); i !== -1; i = reste.indexOf('@media (hover: hover)')) {
    let profondeur = 0
    let fin = reste.indexOf('{', i)
    for (let j = fin; j < reste.length; j += 1) {
      if (reste[j] === '{') profondeur += 1
      if (reste[j] === '}') { profondeur -= 1; if (profondeur === 0) { fin = j; break } }
    }
    reste = reste.slice(0, i) + reste.slice(fin + 1)
  }
  for (const r of regles(reste)) if (/\.rp9-chip[^,{]*:hover/.test(r.selecteur)) survolsNus.push(r.selecteur)
  assert.deepEqual(survolsNus, [], 'survol collé après un toucher : le placer sous @media (hover: hover)')
})

test('ACAL969 : UN seul état « choisi » (fond doré sur [aria-pressed]) ; le badge « recommandé » reste distinct', () => {
  const dore = /background:\s*color-mix\(in srgb,\s*var\(--primary-text\)/
  for (const r of regles(CSS_ROOFBUILDER)) {
    if (/\.rp9-chip(?![\w-])/.test(r.selecteur) && dore.test(r.corps)) {
      assert.ok(r.selecteur.includes("aria-pressed='true'"), `${r.selecteur} : un second état « choisi » doré`)
    }
  }
  const badge = regles(CSS_ROOFBUILDER).find((r) => /\.rp9-reco-badge\s*$/.test(r.selecteur))
  assert.ok(badge, 'règle .rp9-reco-badge absente')
  assert.ok(!/background/.test(badge.corps), '.rp9-reco-badge ne doit pas porter de fond doré')
  assert.ok(parseFloat(declarations(badge.corps)['font-size']) >= 0.75, '.rp9-reco-badge : texte sous 12 px')
})

// ACAL1524 — un geste refusé se voit : le bouton désactivé n'a plus l'aspect du bouton actif.
test('ACAL1524 : un bouton rp9-btn désactivé se distingue d’un bouton actif (fond, bordure, texte), « Déplacer » compris', () => {
  const regle = regles(CSS_ROOFBUILDER).find((r) => /\.rp9-btn:disabled/.test(r.selecteur))
  assert.ok(regle, 'règle .rp9-btn:disabled absente')
  const d = declarations(regle.corps)
  assert.ok(/#rp9-layout-toggle:disabled/.test(regle.selecteur), 'le bouton « Déplacer les panneaux » (id, classes Tailwind) n’est pas couvert')
  assert.equal(d['border-style'], 'dashed')
  assert.ok(/var\(--muted\)/.test(d.background), 'fond éteint attendu (jeton --muted)')
  assert.ok(/var\(--muted-foreground\)/.test(d.color), 'texte lisible attendu (jeton --muted-foreground), pas une simple opacité')
  assert.equal(d['cursor'], 'not-allowed')
  assert.ok(!('opacity' in d), 'l’opacité seule rendait le refus invisible')
  assert.ok(regles(CSS_ROOFBUILDER).some((r) => /\.rp9-motif-refus/.test(r.selecteur)), 'ligne de motif sans règle')
})

// ACAL1443 — les champs de date de la photo (créés par mapDraw.ts) ont bordure, fond de champ et 44 px.
test('ACAL1443 : .rp9-image-capture-input est un vrai champ (bordure, fond, 44 px)', () => {
  const regle = regles(CSS_ROOFBUILDER).find((r) => /\.rp9-image-capture-input\s*$/.test(r.selecteur))
  assert.ok(regle, 'règle .rp9-image-capture-input absente : le champ est invisible')
  const d = declarations(regle.corps)
  assert.ok(/^1px solid/.test(d.border), 'bordure attendue')
  assert.ok(/var\(--muted\)/.test(d.background), 'fond de champ attendu')
  assert.ok(parseFloat(d['min-height']) >= 2.75, 'hauteur sous 44 px')
})

// ACAL1519 — « K-COLONNE-ETROITE » : les grilles du panneau de droite (retraits, bandeau de « Déplacer les panneaux »,
// bloc « Total — toutes les zones ») suivent la largeur de la COLONNE (auto-fit), jamais un point de rupture de fenêtre.
test('ACAL1519 : aucune grille du panneau de droite ne dépend du point de rupture de la fenêtre', () => {
  for (const f of ['atelier/InspecteurBuilder.jsx', 'atelier/BuilderPose.jsx']) {
    const src = readFileSync(join(SRC, C + f), 'utf8')
    assert.ok(!/(?:sm|md|lg|xl):grid-cols-/.test(src), `${f} : grille à point de rupture de fenêtre`)
    assert.ok(src.includes('grid-cols-[repeat(auto-fit,'), `${f} : grille à colonnes automatiques attendue`)
  }
  const bloc = /\.rp9-host \.rp9-setbacks\s*\{[^}]*\}/.exec(CSS_ROOFBUILDER)?.[0] ?? ''
  assert.match(bloc, /auto-fit/, 'roofbuilder.css : .rp9-setbacks doit suivre la largeur de la colonne')
  assert.ok(!/@media[^{]*\{[^{}]*\.rp9-setbacks/.test(CSS_ROOFBUILDER), 'roofbuilder.css : .rp9-setbacks sans repli par la fenêtre')
})
