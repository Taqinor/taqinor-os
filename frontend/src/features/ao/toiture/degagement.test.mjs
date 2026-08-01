import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  repereDepuisIndex,
  indexDepuisRepere,
  prochainRepere,
  renumeroter,
  reperesEnDouble,
  NATURES_OBSTACLE,
  natureParCle,
  estLineaire,
  degagementParProvenance,
  degagementEffectif,
  DEGAGEMENT_MESURE_M,
  DEGAGEMENT_INCERTAIN_M,
} from './repereLettre.js'

/* AOF88 — le dégagement est DÉRIVÉ de la provenance (0,30 / 0,50), la surcharge
   est signalée, et les repères lettrés ne se dupliquent JAMAIS — y compris après
   une suppression au milieu de la liste. */

test('les repères suivent la numérotation de tableur (A… Z, AA, AB…)', () => {
  assert.equal(repereDepuisIndex(0), 'A')
  assert.equal(repereDepuisIndex(25), 'Z')
  assert.equal(repereDepuisIndex(26), 'AA')
  assert.equal(repereDepuisIndex(27), 'AB')
  assert.equal(indexDepuisRepere('A'), 0)
  assert.equal(indexDepuisRepere('Z'), 25)
  assert.equal(indexDepuisRepere('AA'), 26)
  assert.equal(indexDepuisRepere('12'), null)
})

test('28 obstacles reçoivent 28 repères DISTINCTS, sans outil externe', () => {
  const obstacles = []
  for (let i = 0; i < 28; i += 1) {
    obstacles.push({ repere: prochainRepere(obstacles) })
  }
  assert.equal(obstacles.length, 28)
  assert.deepEqual(reperesEnDouble(obstacles), [])
  assert.equal(obstacles[0].repere, 'A')
  assert.equal(obstacles[25].repere, 'Z')
  assert.equal(obstacles[26].repere, 'AA')
  assert.equal(obstacles[27].repere, 'AB')
  assert.equal(new Set(obstacles.map((o) => o.repere)).size, 28)
})

test('après suppression, la lettre libérée est REPRISE — jamais dupliquée', () => {
  let obstacles = [{ repere: 'A' }, { repere: 'B' }, { repere: 'C' }]
  obstacles = obstacles.filter((o) => o.repere !== 'B')
  assert.equal(prochainRepere(obstacles), 'B')
  obstacles.push({ repere: prochainRepere(obstacles) })
  assert.deepEqual(reperesEnDouble(obstacles), [])
  assert.deepEqual(obstacles.map((o) => o.repere).sort(), ['A', 'B', 'C'])
  // Et un quatrième prend bien D.
  assert.equal(prochainRepere(obstacles), 'D')
})

test('la renumérotation séquentielle compacte les repères sans en dupliquer', () => {
  const apres = renumeroter([{ repere: 'A' }, { repere: 'C' }, { repere: 'Z' }])
  assert.deepEqual(apres.map((o) => o.repere), ['A', 'B', 'C'])
  assert.deepEqual(reperesEnDouble(apres), [])
})

test('reperesEnDouble détecte réellement un doublon', () => {
  assert.deepEqual(reperesEnDouble([{ repere: 'A' }, { repere: 'a' }]), ['A'])
})

test('les treize natures sont nommées, dont les linéaires (muret, joint, acrotère)', () => {
  assert.equal(NATURES_OBSTACLE.length, 13)
  assert.equal(new Set(NATURES_OBSTACLE.map((n) => n.cle)).size, 13)
  assert.equal(estLineaire('muret'), true)
  assert.equal(estLineaire('joint_dilatation'), true)
  assert.equal(estLineaire('acrotere'), true)
  assert.equal(estLineaire('edicule'), false)
  assert.equal(natureParCle('cheminee').libelle, 'Cheminée')
  assert.equal(natureParCle('inconnue'), null)
})

test('le dégagement est DÉRIVÉ de la provenance : 0,30 mesuré / 0,50 sinon', () => {
  assert.equal(degagementParProvenance('mesure'), DEGAGEMENT_MESURE_M)
  assert.equal(degagementParProvenance('confirmer'), DEGAGEMENT_INCERTAIN_M)
  assert.equal(degagementParProvenance('deduit'), DEGAGEMENT_INCERTAIN_M)
  assert.equal(degagementParProvenance('devine'), DEGAGEMENT_INCERTAIN_M)
  assert.equal(degagementParProvenance(undefined), DEGAGEMENT_INCERTAIN_M)
})

test('changer la provenance change le dégagement effectif — sans surcharge', () => {
  const mesure = degagementEffectif({ provenance: 'mesure' })
  assert.equal(mesure.valeur, 0.3)
  assert.equal(mesure.surcharge, false)

  const devine = degagementEffectif({ provenance: 'devine' })
  assert.equal(devine.valeur, 0.5)
  assert.equal(devine.surcharge, false)
})

test('une valeur saisie différente de la dérivée est SIGNALÉE « surchargé »', () => {
  const sur = degagementEffectif({ provenance: 'mesure', degagementM: 0.8 })
  assert.equal(sur.valeur, 0.8)
  assert.equal(sur.derive, 0.3)
  assert.equal(sur.surcharge, true)

  // Saisir exactement la valeur dérivée n'est PAS une surcharge.
  const egale = degagementEffectif({ provenance: 'mesure', degagementM: '0,30' })
  assert.equal(egale.valeur, 0.3)
  assert.equal(egale.surcharge, false)

  // Une saisie vide ou aberrante retombe sur la dérivée, sans jamais rendre NaN.
  assert.equal(degagementEffectif({ provenance: 'devine', degagementM: '' }).valeur, 0.5)
  assert.equal(degagementEffectif({ provenance: 'devine', degagementM: 'abc' }).valeur, 0.5)
  assert.equal(degagementEffectif({ provenance: 'mesure', degagementM: -1 }).valeur, 0.3)
})
