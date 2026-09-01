// QJR40 (audit L3 29/08/2026, décision fondateur D8, jumelle backend = QJR25)
// — `selectors.contexte_conception_devis` calcule `cible_avec` exprès pour
// que l'écran 3D connaisse l'option 2 (« Avec batterie ») d'un devis
// « Les deux » (CTX3D, 25/08) — mais `ToitureDesign.jsx`, son unique
// consommateur, ne la lisait JAMAIS : la cible 3D ciblait toujours l'option
// SANS (celle de `contexte.cible`), à l'opposé de la politique AVEC-d'abord
// d'`electrical_service._option_choisie`/`_lignes_option_choisie` pour le
// MÊME devis (QJR25). Décision fondateur D8 du 29/08 : « Les deux »
// mono-config = AVEC partout, cible 3D comprise.
//
// ToitureDesign.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE, même patron que
// ToitureDesignLayoutIds.test.mjs / DevisGeneratorBuildDimensionnementAvec.test.mjs.
//
// Run : node --test src/pages/ventes/ToitureDesignCibleAvec.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ToitureDesign.jsx'), 'utf8')

test('QJR40 — un helper module-scope lit cible_avec en priorité sur cible', () => {
  assert.match(
    SRC,
    /function cibleActiveDuContexte\(contexte\) \{\s*\n\s*return contexte\?\.cible_avec \?\? contexte\?\.cible \?\? \{\}\s*\n\}/,
    'cibleActiveDuContexte doit préférer cible_avec, avec repli sur cible puis {}',
  )
})

test('QJR40 — contexteToDevisPayload (mode devis, hydrate.devis du builder 3D) cible via cibleActiveDuContexte', () => {
  const idx = SRC.indexOf('function contexteToDevisPayload(contexte) {')
  assert.ok(idx > -1, 'contexteToDevisPayload introuvable')
  const bloc = SRC.slice(idx, idx + 400)
  assert.match(bloc, /const cible = cibleActiveDuContexte\(contexte\)/,
    'contexteToDevisPayload doit lire cible via cibleActiveDuContexte (plus jamais contexte.cible directement)')
  assert.doesNotMatch(bloc, /const cible = contexte\.cible/,
    'contexteToDevisPayload ne doit plus lire contexte.cible directement (option SANS figée)')
})

test('QJR40 — la garde anti-divergence d\'enregistrerConception compare contre la MÊME cible que le boot (pas contexte.cible seul)', () => {
  const idx = SRC.indexOf('const panneauxPoses = Number(layout?.result?.panels) || 0')
  assert.ok(idx > -1, 'garde anti-divergence introuvable')
  const bloc = SRC.slice(idx, idx + 700)
  assert.match(bloc, /const panneauxDevis = Number\(cibleActiveDuContexte\(contexte\)\.panneaux\) \|\| 0/,
    'panneauxDevis doit être lu via cibleActiveDuContexte, sinon un devis « Les deux » redéclenche le dialogue à tort')
})

test('QJR40 — rejoué : devis « Les deux » divergents → la cible 3D cible AVEC, la MÊME option que le SLD (QJR25)', () => {
  // Reproduit EXACTEMENT la formule verrouillée par le 1er test ci-dessus.
  const cibleActiveDuContexte = (contexte) => contexte?.cible_avec ?? contexte?.cible ?? {}

  // Devis « Les deux » divergents (le cas qui révélait le bug) : l'option
  // SANS (cible) et l'option AVEC (cible_avec) ne portent PAS le même compte
  // de panneaux ni le même scénario — exactement comme un devis réel où les
  // deux options ne couvrent pas la même surface de toit.
  const contexteLesDeux = {
    cible: { panneaux: 12, panel_watt: 550, scenario: 'injection_reseau' },
    cible_avec: { panneaux: 17, panel_watt: 550, scenario: 'avec_batterie', kwc: 9.35, batterie: 15.4 },
  }
  const cibleEcran3D = cibleActiveDuContexte(contexteLesDeux)
  // La MÊME option que celle que le SLD retient pour ce devis (QJR25,
  // `electrical_service._option_choisie` : AVEC servable l'emporte toujours).
  assert.equal(cibleEcran3D.panneaux, 17, 'la cible 3D doit cibler le compte AVEC (17), pas SANS (12)')
  assert.equal(cibleEcran3D.scenario, 'avec_batterie', 'la cible 3D doit cibler le scénario AVEC')

  // Devis mono-option (aucune option AVEC servable) : cible_avec est absente
  // — comportement STRICTEMENT inchangé, la cible reste l'unique option vendue.
  const contexteMonoOption = { cible: { panneaux: 9, panel_watt: 610, scenario: 'injection_reseau' } }
  const cibleMonoOption = cibleActiveDuContexte(contexteMonoOption)
  assert.equal(cibleMonoOption.panneaux, 9, 'un devis mono-option garde sa cible inchangée')
  assert.equal(cibleMonoOption.scenario, 'injection_reseau')

  // Contexte absent (garde `?.`) : jamais un crash, jamais une valeur inventée.
  assert.deepEqual(cibleActiveDuContexte(null), {})
  assert.deepEqual(cibleActiveDuContexte(undefined), {})
})
