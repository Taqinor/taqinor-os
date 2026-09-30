// ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — le payback affiché quand l'étude horaire
// serveur a répondu est celui du MOTEUR (cashflow 25 ans QX39), plus
// `coût ÷ économie`. Valeurs attendues calculées par
// `pricing.compute_cashflow_payback` (Python) sur les mêmes entrées.
// Run : node --test src/features/ventes/solar.paybackMoteurHoraire.test.mjs
// L'affichage dans l'écran est EXÉCUTÉ (QJR239, aucune lecture de source)
// par `pages/ventes/DevisGeneratorPaybackMoteur.test.jsx`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { paybackMoteurHoraire } from './solar.js'

test("cas e2e : 36 873,11 MAD / 4 580 MAD/an ⇒ 8,2 ans (document), pas 8,05", () => {
  const r = paybackMoteurHoraire(36873.11, 4580, { inverterReplaceCost: 12000 })
  assert.deepEqual(r, { paybackYears: 8.2, jamaisRembourse: false })
})

test('option avec : part batterie dérivée des taux du bloc, comme pricing', () => {
  const annuel = {
    production_kwh: 6813, consommation_kwh: 9000,
    taux_autoconso_sans: 0.5, taux_autoconso_avec: 0.8,
  }
  const r = paybackMoteurHoraire(53149.26, 7822, {
    annuel, stockage: true, inverterReplaceCost: 17000,
  })
  assert.deepEqual(r, { paybackYears: 7.2, jamaisRembourse: false })
})

test('jamais remboursé sur 25 ans : drapeau, jamais un nombre à afficher', () => {
  const r = paybackMoteurHoraire(269065, 5000, {})
  assert.equal(r.jamaisRembourse, true)
})

test('sans coût ou sans économie : rien', () => {
  assert.equal(paybackMoteurHoraire(0, 4580), null)
  assert.equal(paybackMoteurHoraire(36873, 0), null)
})
