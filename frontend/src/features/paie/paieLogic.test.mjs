import test from 'node:test'
import assert from 'node:assert/strict'

import {
  runStepState, peutAvancerPeriode, statutSuivant, anomaliesBulletin,
  runAAnomalies, PERIODE_STATUTS, BULLETIN_STATUTS,
} from './paieLogic.js'

test('peutAvancerPeriode — avance stricte seulement', () => {
  assert.equal(peutAvancerPeriode('brouillon', 'calculee'), true)
  assert.equal(peutAvancerPeriode('brouillon', 'cloturee'), true)
  // Reculer / rester interdit.
  assert.equal(peutAvancerPeriode('validee', 'calculee'), false)
  assert.equal(peutAvancerPeriode('validee', 'validee'), false)
  assert.equal(peutAvancerPeriode('???', 'validee'), false)
})

test('statutSuivant — statut immédiatement suivant du cycle', () => {
  assert.equal(statutSuivant('brouillon'), 'calculee')
  assert.equal(statutSuivant('validee'), 'cloturee')
  assert.equal(statutSuivant('cloturee'), null)
  assert.equal(statutSuivant('inconnu'), null)
})

test('runStepState — sans période, seule l’étape période est ouverte', () => {
  const s = runStepState({ periode: null, bulletins: [] })
  assert.equal(s.periode.unlocked, true)
  assert.equal(s.periode.done, false)
  assert.equal(s.generer.unlocked, false)
  assert.equal(s.revue.unlocked, false)
  assert.equal(s.valider.unlocked, false)
  assert.equal(s.cloturer.unlocked, false)
})

test('runStepState — période ouverte sans bulletins : génération ouverte', () => {
  const s = runStepState({
    periode: { id: 1, statut: PERIODE_STATUTS.BROUILLON }, bulletins: [],
  })
  assert.equal(s.periode.done, true)
  assert.equal(s.generer.unlocked, true)
  assert.equal(s.generer.done, false)
  assert.equal(s.revue.unlocked, false)
  assert.equal(s.cloturer.unlocked, false)
})

test('runStepState — bulletins présents : revue ouverte, clôture verrouillée', () => {
  const s = runStepState({
    periode: { id: 1, statut: PERIODE_STATUTS.CALCULEE },
    bulletins: [
      { id: 9, statut: BULLETIN_STATUTS.BROUILLON, brut: 5000, net_a_payer: 4000 },
    ],
  })
  assert.equal(s.generer.done, true)
  assert.equal(s.revue.unlocked, true)
  assert.equal(s.revue.done, true)
  assert.equal(s.valider.unlocked, true)
  assert.equal(s.cloturer.unlocked, false)
})

test('runStepState — validée : clôture ouverte ; clôturée : figée', () => {
  const valide = runStepState({
    periode: { id: 1, statut: PERIODE_STATUTS.VALIDEE },
    bulletins: [
      { id: 9, statut: BULLETIN_STATUTS.VALIDE, brut: 5000, net_a_payer: 4000 },
    ],
  })
  assert.equal(valide.valider.done, true)
  assert.equal(valide.cloturer.unlocked, true)
  assert.equal(valide.cloturer.done, false)

  const cloturee = runStepState({
    periode: { id: 1, statut: PERIODE_STATUTS.CLOTUREE },
    bulletins: [
      { id: 9, statut: BULLETIN_STATUTS.VALIDE, brut: 5000, net_a_payer: 4000 },
    ],
  })
  assert.equal(cloturee.cloturer.done, true)
  assert.equal(cloturee.generer.unlocked, false)
})

test('anomaliesBulletin — flag brut/net nuls et net > brut', () => {
  assert.deepEqual(anomaliesBulletin({ brut: 5000, net_a_payer: 4000 }), [])
  assert.ok(
    anomaliesBulletin({ brut: 0, net_a_payer: 0 })
      .includes('Brut nul ou négatif'),
  )
  assert.ok(
    anomaliesBulletin({ brut: 3000, net_a_payer: 3500 })
      .includes('Net supérieur au brut'),
  )
})

test('runAAnomalies — vrai dès qu’un bulletin est douteux', () => {
  assert.equal(runAAnomalies([{ brut: 5000, net_a_payer: 4000 }]), false)
  assert.equal(
    runAAnomalies([
      { brut: 5000, net_a_payer: 4000 },
      { brut: 0, net_a_payer: 0 },
    ]),
    true,
  )
})
