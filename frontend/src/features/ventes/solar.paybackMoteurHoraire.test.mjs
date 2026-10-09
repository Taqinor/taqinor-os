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
  // AMOT72 — `netGain` (gain net 25 ans) est désormais rendu aussi.
  assert.equal(r.paybackYears, 8.2)
  assert.equal(r.jamaisRembourse, false)
})

// AMOT72 — miroir du moteur CORRIGÉ (AMOT58, rendement_une_fois) : en modèle
// horaire, aucune seconde déduction du rendement batterie (part batterie 0).
// Attendu recalculé par `pricing.compute_cashflow_payback(53149.26, 7822,
// battery=True, battery_share=0, inverter_replace_cost=17000)` :
// payback 6,9, net_gain 114 105 (avant : 7,2 avec la part 0,375 déduite).
test('option avec : aucune seconde déduction du rendement batterie (AMOT58/AMOT72)', () => {
  const annuel = {
    production_kwh: 6813, consommation_kwh: 9000,
    taux_autoconso_sans: 0.5, taux_autoconso_avec: 0.8,
  }
  const r = paybackMoteurHoraire(53149.26, 7822, {
    annuel, stockage: true, inverterReplaceCost: 17000,
  })
  assert.deepEqual(r, { paybackYears: 6.9, jamaisRembourse: false, netGain: 114105 })
})

test('jamais remboursé sur 25 ans : drapeau, jamais un nombre à afficher', () => {
  const r = paybackMoteurHoraire(269065, 5000, {})
  assert.equal(r.jamaisRembourse, true)
})

test('sans coût ou sans économie : rien', () => {
  assert.equal(paybackMoteurHoraire(0, 4580), null)
  assert.equal(paybackMoteurHoraire(36873, 0), null)
})
