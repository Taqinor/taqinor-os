// ACAL427 — UN SEUL langage visuel dans le module Calepinage : les classes
// héritées du site public (liste L) migrent vers les jetons de l'ERP. Le garde
// lit les SOURCES (pas de node_modules requis) et compte L par fichier non-test
// de features/calepinage/ + ToitureDesign.jsx. `PLAFOND` = fichiers encore à
// migrer (n mesuré le 21/11) : un plafond ne peut que BAISSER ; un fichier
// absent de la table a un plafond de 0. ACAL428/429/432/442 retirent leurs
// fichiers, ACAL479 vide la table.
//   node --test src/features/calepinage/langageVisuel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
const SRC = fileURLToPath(new URL('../../', import.meta.url))
const L = /\b(?:cine-card|tech-label|rule-brass)\b|text-lune-(?:soft|faint)|text-brass-\d+|text-alert-\d+|bg-nuit-\d+|text-white|(?:border|bg|divide)-white\/\d+/g
const C = 'features/calepinage/'
const PLAFOND = {
  ...Object.fromEntries(Object.entries({
    'atelier/BarreEnregistrement.jsx': 6,
    'atelier/PanneauDetectionToit.jsx': 1,
    'atelier/PanneauOptimiser.jsx': 2,
    'atelier/ResumeAtelier.jsx': 1,
    'commun/RailGuide.jsx': 4,
  }).map(([k, v]) => [C + k, v])),
}
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
test('aucun fichier ne dépasse son plafond (absent de la table = 0)', () => {
  for (const f of cibles) assert.ok(compte(f) <= (PLAFOND[f] ?? 0), `${f} : ${compte(f)} classe(s) du site public, plafond ${PLAFOND[f] ?? 0}`)
})
const SOUS_DOSSIERS = [
  'pompage/PompagePanel.jsx', 'equipements/FichesIncompletes.jsx', 'electrique/SaisiesElectriques.jsx',
  'electrique/Raccordement.jsx', 'electrique/VerdictElectrique.jsx', 'electrique/MaterielElectrique.jsx',
  'electrique/DecisionsElectriques.jsx', 'production/BandeauProvenanceProduction.jsx', 'plan/AffectationChaines.jsx',
].map((n) => C + n)
test("ACAL442 : les 9 fichiers des sous-dossiers n'ont plus de classe de L", () => {
  for (const f of SOUS_DOSSIERS) {
    assert.equal(compte(f), 0, `${f} porte encore des classes du site public`)
    assert.equal(PLAFOND[f], undefined, `${f} doit sortir de PLAFOND`)
  }
})
test("PLAFOND ne nomme que des fichiers existants, jamais ceux de l'enveloppe", () => {
  for (const f of Object.keys(PLAFOND)) {
    assert.ok(cibles.includes(f), `${f} n'existe plus : retirer l'entrée`)
    assert.ok(!ENVELOPPE.includes(f), `${f} est dans l'enveloppe`)
  }
})
