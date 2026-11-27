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
// ACAL1823 — plus aucun fond noir/blanc translucide littéral (`bg-black/30` : pavé gris moyen en thème clair).
// Le champ actif lit `--cal-surface`, qui suit le thème.
test('ACAL1823 : aucune classe bg-black/ ni bg-white/ dans les écrans du module', () => {
  const FOND = /bg-(?:black|white)\/\d+/g
  const fautifs = []
  for (const p of fichiers(join(SRC, C))) {
    const trouves = readFileSync(p, 'utf8').match(FOND)
    if (trouves) fautifs.push(`${relative(SRC, p).split(sep).join('/')} : ${trouves.join(', ')}`)
  }
  assert.deepEqual(fautifs, [])
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

// ACAL1746 — la grille des chiffres de la cible (`AtelierPanneaux.jsx`) suit la colonne : prouvé en RENDANT le composant
// (`AtelierPanneaux.test.jsx`, cas « ACAL1746 »), pas en lisant son source.

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

// ACAL1823 (revue) — le jeton `--cal-surface` n'existe que sous `.cal-coque, .cliste, .cal-tel, .cal-client, .cal-reglages`
// (`49-jetons-v2.css`). Une PAGE (écran de route, hors coque) qui le lit doit poser elle-même l'une de ces classes,
// sinon le fond est indéfini, donc transparent.
test('ACAL1823 : une page qui lit --cal-surface porte la classe qui le définit', () => {
  const DEFINISSEURS = /\b(?:cal-coque|cliste|cal-tel|cal-client|cal-reglages)\b/
  const pages = fichiers(join(SRC, C)).filter((p) => /[\\/]reglages[\\/]/.test(p) || /Page\.jsx$/.test(p))
  const fautifs = pages.filter((p) => {
    const src = readFileSync(p, 'utf8')
    return src.includes('--cal-surface') && !DEFINISSEURS.test(src)
  }).map((p) => relative(SRC, p).split(sep).join('/'))
  assert.deepEqual(fautifs, [])
})
