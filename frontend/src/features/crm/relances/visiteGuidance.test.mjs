import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  phaseVisite, PHASE_GUIDANCE, SIGNAUX_ACHAT, REGLE_OBJECTION, visitePassee,
} from './visiteGuidance.js'

// VISCAD — table ordre -> jour du gabarit apres_devis par défaut
// (`apps/parametres/models_relance.py CADENCE_APRES_DEVIS_DEFAUT`) :
// ordre 1 -> J1, ordre 2-5 -> J2/J3/J4/J6, ordre 6-10 -> J7/J9/J11/J13/J14.

test('phaseVisite : ordre 1 (J1) -> phase 1 (pas encore)', () => {
  assert.equal(phaseVisite({ ordre: 1 }), 1)
})

test('phaseVisite : ordre 2 à 5 (J2-J6) -> phase 2 (semez la visite)', () => {
  assert.equal(phaseVisite({ ordre: 2 }), 2)
  assert.equal(phaseVisite({ ordre: 3 }), 2)
  assert.equal(phaseVisite({ ordre: 4 }), 2)
  assert.equal(phaseVisite({ ordre: 5 }), 2)
})

test('phaseVisite : ordre 6 et au-delà (J7+) -> phase 3 (choix alternatif)', () => {
  assert.equal(phaseVisite({ ordre: 6 }), 3)
  assert.equal(phaseVisite({ ordre: 7 }), 3)
  assert.equal(phaseVisite({ ordre: 10 }), 3)
})

test('phaseVisite : ordre hors gabarit par défaut (cadence personnalisée) -> repli ordinal', () => {
  // 11e barreau : au-delà de la table par défaut (max ordre 10) — reste
  // phase 3 (repli ordinal, jamais un jour halluciné).
  assert.equal(phaseVisite({ ordre: 11 }), 3)
})

test('phaseVisite : étape absente/ordre absent -> phase 1 (jamais une erreur)', () => {
  assert.equal(phaseVisite(null), 1)
  assert.equal(phaseVisite({}), 1)
})

test('PHASE_GUIDANCE : les trois phases portent les textes fondateur exacts', () => {
  assert.equal(PHASE_GUIDANCE[1].texte, 'Pas encore — laissez le devis vivre. Répondez, écoutez.')
  assert.match(PHASE_GUIDANCE[2].script, /orientation du toit et la charpente/)
  assert.match(PHASE_GUIDANCE[3].script, /créneau mardi matin ou jeudi après-midi/)
})

test('SIGNAUX_ACHAT : la checklist porte les 6 signaux', () => {
  assert.equal(SIGNAUX_ACHAT.length, 6)
})

test('REGLE_OBJECTION : la règle « jamais un débat au téléphone » est présente', () => {
  assert.match(REGLE_OBJECTION, /jamais par un débat au téléphone/)
})

test('visitePassee : terminee/validee sont passées, le reste ne l\'est pas', () => {
  assert.equal(visitePassee({ statut: 'terminee' }), true)
  assert.equal(visitePassee({ statut: 'validee' }), true)
  assert.equal(visitePassee({ statut: 'brouillon' }), false)
  assert.equal(visitePassee({ statut: 'en_cours' }), false)
  assert.equal(visitePassee({ statut: 'a_refaire' }), false)
  assert.equal(visitePassee(null), false)
})
