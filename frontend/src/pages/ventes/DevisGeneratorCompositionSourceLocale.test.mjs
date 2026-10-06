// QJR577 (D-QJR5-9) — UN SEUL COMPOSEUR en résidentiel. Quand le dry-run
// serveur (`ventesApi.composerDevis`) échoue, l'écran ne recompose PLUS en
// JavaScript (`composeLocalement` → `autoFillLines`, moteur que le dépôt
// documente lui-même divergent du serveur) : les lignes restent inchangées,
// l'erreur est dite, et « Réessayer » rejoue le dry-run. (Ce fichier
// verrouillait jusqu'ici l'inverse : bannière QJR36 + repli local.)
// CIQ126 — `composeLocalement` est SUPPRIMÉ : le C&I compose par le moteur
// serveur C&I (`etude-ci/preview`), l'agricole par son kit serveur (AGR130).
//
// DevisGenerator.jsx est du JSX non exécutable par `node --test` : lecture du
// SOURCE (comportement rendu couvert par les tests vitest du générateur).
// Run : node --test src/pages/ventes/DevisGeneratorCompositionSourceLocale.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const CODE = DG.split(/\r?\n/).filter(l => !/^\s*(\/\/|\{\/\*)/.test(l)).join('\n')

function blocCatchResidentiel() {
  const idx = CODE.indexOf('const { data } = await ventesApi.composerDevis(body)')
  assert.ok(idx > -1, "l'appel composerDevis est introuvable")
  const fin = CODE.indexOf('} finally {', idx)
  assert.ok(fin > idx)
  return CODE.slice(idx, fin)
}

test('QJR577 — le catch du dry-run résidentiel ne compose JAMAIS localement', () => {
  const bloc = blocCatchResidentiel()
  assert.match(bloc, /setCompositionErreur\(null\)\s*\n\s*appliquerCompositionServeur\(data\)/)
  const catchIdx = bloc.indexOf('catch (err) {')
  assert.ok(catchIdx > -1)
  const dansCatch = bloc.slice(catchIdx)
  assert.doesNotMatch(dansCatch, /composeLocalement\(|autoFillLines\(|setLines\(|recomposerLignes\(/,
    'un dry-run en échec ne doit ni composer ni toucher aux lignes')
  assert.match(dansCatch, /setCompositionErreur\(/)
})

test('QJR577 — erreur visible + « Réessayer » qui rejoue le même dry-run', () => {
  const idx = DG.indexOf('data-testid="composition-erreur"')
  assert.ok(idx > -1, "le bandeau d'erreur de composition est introuvable")
  const bloc = DG.slice(Math.max(0, idx - 300), idx + 900)
  assert.match(bloc, /\{compositionErreur && \(/)
  assert.match(bloc, /data-testid="composition-reessayer"/)
  assert.match(bloc, /onClick=\{\(\) => avecQuantitesFigees\(handleAutoFill\)\}/)
  assert.match(bloc, /Réessayer/)
})

test('QJR577 — la bannière de composition de secours a disparu avec son dernier écrivain', () => {
  assert.doesNotMatch(CODE, /compositionSourceLocale|composition-source-locale/)
  assert.doesNotMatch(DG, /import \{ raisonRepli \}/)
})

test('CIQ126 — plus aucun composeur JavaScript : le C&I passe par le moteur serveur', () => {
  assert.doesNotMatch(CODE, /composeLocalement|autoFillLines\(/)
  // Branche de clôture de handleAutoFill (industriel / commercial) : un appel
  // à l'aperçu C&I puis les lignes de SA composition, APRÈS le résidentiel.
  const res = CODE.indexOf("if (modeInstallation === 'residentiel') {\n      if (kwp <= 0) {")
  const ci = CODE.indexOf('await ventesApi.etudeCiPreview(corps)')
  assert.ok(res > -1 && ci > res)
  assert.match(CODE.slice(ci, ci + 300), /lignesDepuisCompositionCi\(data\?\.composition, produits\)/)
})
