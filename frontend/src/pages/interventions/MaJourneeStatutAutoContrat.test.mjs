// EZ6 — contrat de la dérivation de statut, vérifié à la source (node:test).
// Le comportement est testé au rendu dans `MaJourneeStatutAuto.test.jsx` ; ici
// on verrouille ce qu'un rendu ne montre pas : aucun toast rouge sur un refus
// serveur, aucune duplication de `transition_block_reason`, et le fait que le
// dérivateur passe par le PATCH existant.
//
//   node --test src/pages/interventions/MaJourneeStatutAutoContrat.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'MaJourneePage.jsx'), 'utf8')

const bloc = (debut, fin) => SRC.slice(SRC.indexOf(debut), SRC.indexOf(fin))

test('les trois horodatages terrain pilotent les trois statuts', () => {
  const table = bloc('const HORODATAGE_STATUT', 'export function statutDerive')
  assert.match(table, /\['depart_depot_le', 'en_route'\]/)
  assert.match(table, /\['arrivee_site_le', 'sur_site'\]/)
  assert.match(table, /\['retour_depot_le', 'terminee'\]/)
})

test('un refus serveur ne produit JAMAIS un toast rouge', () => {
  const derive = bloc('const onFieldChanged', '// VX226(b) — `load()`')
  assert.equal(derive.includes('toast.error'), false,
    'le chemin automatique alerte en rouge sur un refus')
  assert.match(derive, /setIndiceStatut\(/)
  // …et l'indice affiché est le message DU SERVEUR (aucune règle dupliquée).
  assert.match(derive, /data\?\.transition_block_reason/)
})

test('la transition automatique passe par le PATCH existant + undo 6 s', () => {
  const derive = bloc('const onFieldChanged', '// VX226(b) — `load()`')
  assert.match(derive, /installationsApi\.updateIntervention\(apres\.id, \{ statut: cible \}\)/)
  assert.match(derive, /toastWithUndo\(\{/)
  // Undo = appel INVERSE (le recul est autorisé serveur), pas un commit différé.
  assert.match(derive, /onUndo: \(\) => \{[\s\S]*statut: ancien/)
  assert.equal(derive.includes('onCommit'), false)
})

test('le Select manuel est filtré par ADJACENCE, pas par une règle métier', () => {
  assert.match(SRC, /\{statutsProposables\(interv\.statut\)\.map\(/)
  assert.equal(/\{INTERVENTION_STATUSES\.map\(\(s\) => \(\s*\n\s*<SelectItem/.test(SRC), false,
    'le Select propose encore les 6 statuts sans filtre')
  const helper = bloc('export function statutsProposables', 'function todayISO')
  assert.match(helper, /Math\.abs\(interventionStatusRank\(s\) - r\) <= 1/)
})

test('les panneaux terrain remontent l’intervention AVANT l’action', () => {
  assert.match(SRC, /const panelChanged = \(\) => onChanged\?\.\(interv\)/)
  assert.equal(SRC.includes('onChanged={onChanged}'), false,
    'un panneau appelle encore onChanged sans contexte')
})

test('le dérivateur ne recule JAMAIS tout seul', () => {
  const d = bloc('export function statutDerive', 'export function statutsProposables')
  assert.match(d, /interventionStatusRank\(apres\.statut\) > interventionStatusRank\(cible\)/)
})
