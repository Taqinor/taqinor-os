// N3 (audit apercu-issues) — un nombre de panneaux TAPÉ À LA MAIN était
// RE-FORCÉ par la frappe sur les factures : `syncBillEstimator` (déclenché à
// chaque frappe hiver/été, y compris via le collage nettoyé VX237) rappelait
// `computeAutoSizing` et `setNbPanneaux(...)` SANS jamais consulter le
// garde-fou `nbPanneauxTouched` déjà posé par `onNbPanneauxChange`/
// `onKwcCibleChange` — alors que `applyLead`/`applySiteProfile`, EUX,
// respectent déjà ce même garde-fou (« intact » : dès que l'utilisateur a
// touché le champ, aucun pré-remplissage ne l'écrase plus). Correctif : même
// patron dans `syncBillEstimator` — la resynchro automatique du nombre de
// panneaux (et son justificatif `sizingInfo`) est sautée si
// `nbPanneauxTouched.current`, tandis que `monthly` (les factures) continue de
// se mettre à jour dans tous les cas.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorOrdreLignes.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorNbPanneauxTouched.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('nbPanneauxTouched.current est posé par la frappe directe (onNbPanneauxChange/onKwcCibleChange)', () => {
  assert.match(DG, /const onKwcCibleChange = \(v\) => \{[\s\S]{0,300}nbPanneauxTouched\.current = true/)
  assert.match(DG, /const onNbPanneauxChange = \(v\) => \{\s*\n\s*nbPanneauxTouched\.current = true/)
})

test('applyLead()/applySiteProfile() respectent déjà nbPanneauxTouched (référence du patron à reproduire)', () => {
  assert.match(DG, /!nbPanneauxTouched\.current && tailleKwc > 0/, 'applyLead : garde absente')
  const spStart = DG.indexOf('const applySiteProfile = (p) => {')
  assert.ok(spStart > -1, 'applySiteProfile introuvable')
  assert.match(DG.slice(spStart, spStart + 1600), /if \(!nbPanneauxTouched\.current\) \{/)
})

// Extrait le contenu d'un bloc `{ ... }` en comptant les accolades (fiable
// même avec des accolades imbriquées, contrairement à un simple indexOf).
function extractBracedBlock(src, openBraceIdx) {
  assert.equal(src[openBraceIdx], '{', 'index ne pointe pas sur une accolade ouvrante')
  let depth = 0
  for (let i = openBraceIdx; i < src.length; i++) {
    if (src[i] === '{') depth++
    else if (src[i] === '}') {
      depth--
      if (depth === 0) return { body: src.slice(openBraceIdx + 1, i), endIdx: i }
    }
  }
  throw new Error('accolade fermante introuvable')
}

test('syncBillEstimator() ne resynchronise plus nbPanneaux/sizingInfo quand nbPanneauxTouched.current est vrai', () => {
  const fnNeedle = 'const syncBillEstimator = (hiverVal, eteVal) => {'
  const start = DG.indexOf(fnNeedle)
  assert.ok(start > -1, 'syncBillEstimator introuvable')
  const { body } = extractBracedBlock(DG, start + fnNeedle.length - 1)

  // La garde existe : extrait précisément SON bloc (comptage d'accolades).
  const guardNeedle = 'if (!nbPanneauxTouched.current) {'
  const guardIdx = body.indexOf(guardNeedle)
  assert.ok(guardIdx > -1, 'garde nbPanneauxTouched absente de syncBillEstimator — régression N3')
  const openBraceIdx = guardIdx + guardNeedle.length - 1
  const { body: guardedBlock, endIdx: guardEndIdx } = extractBracedBlock(body, openBraceIdx)

  // Le redimensionnement automatique (nbPanneaux + son justificatif) est
  // ENTIÈREMENT contenu dans le bloc protégé.
  assert.match(guardedBlock, /setNbPanneaux\(String\(sizing\.nbPanneaux\)\)/)
  assert.match(guardedBlock, /setSizingInfo\(sizing\)/)
  assert.match(guardedBlock, /setNbPanneaux\(String\(suggested\)\)/)

  // setMonthly, lui, reste appelé INCONDITIONNELLEMENT, APRÈS le bloc protégé
  // (donc jamais sauté) — les factures continuent de se mettre à jour même
  // quand le nombre de panneaux ne bouge plus.
  const afterGuard = body.slice(guardEndIdx + 1)
  assert.match(afterGuard, /setMonthly\(estimerMois\(hiver, ete > 0 \? ete : hiver\)\)/)
  assert.doesNotMatch(guardedBlock, /setMonthly/, 'setMonthly ne doit PAS être à l\'intérieur du bloc protégé')
})

test('handleEstimerMois() (bouton "Estimer 12 mois") ne touche jamais nbPanneaux — inchangé, hors scope N3', () => {
  const needle = 'const handleEstimerMois = () => {'
  const start = DG.indexOf(needle)
  assert.ok(start > -1, 'handleEstimerMois introuvable')
  const openBraceIdx = start + needle.length - 1
  const { body } = extractBracedBlock(DG, openBraceIdx)
  assert.doesNotMatch(body, /setNbPanneaux/)
  assert.match(body, /setMonthly\(estimerMois\(hiver, ete\)\)/)
})
