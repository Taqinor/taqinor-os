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
