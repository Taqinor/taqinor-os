// ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — le payback affiché quand l'étude horaire
// serveur a répondu est celui du MOTEUR (cashflow 25 ans QX39), plus
// `coût ÷ économie`. Valeurs attendues calculées par
// `pricing.compute_cashflow_payback` (Python) sur les mêmes entrées.
// Run : node --test src/features/ventes/solar.paybackMoteurHoraire.test.mjs
// L'affichage dans l'écran est EXÉCUTÉ (QJR239, aucune lecture de source)
// par `pages/ventes/DevisGeneratorPaybackMoteur.test.jsx`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { paybackMoteurHoraire, provisionOnduleurPayee, reglesAuMoins } from './calc/roi.js'

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

// AMOT106 — provision onduleur au prix PAYÉ (remise globale déduite) au niveau 3+,
// comme `_cout_onduleur_paye` du PDF (sonde C-AMOT-VER-005 : 16,1 ans / gain 58 003).
test('AMOT106 : provision payée niveau 3 avec remise 10 % = PDF (16,1 ans, 58 003)', () => {
  const prov = provisionOnduleurPayee(24000, 10, 3)
  assert.equal(prov, 21600)
  const r = paybackMoteurHoraire(90000, 7200, {
    stockage: true, rendementBatterie: 0.9, inverterReplaceCost: prov,
  })
  assert.equal(r.paybackYears, 16.1)
  assert.equal(r.netGain, 58003)
})

test('AMOT106 : niveau 2 ou sans remise, provision inchangée (24 000)', () => {
  assert.equal(provisionOnduleurPayee(24000, 10, 2), 24000)
  assert.equal(provisionOnduleurPayee(24000, 0, 3), 24000)
  assert.equal(provisionOnduleurPayee(24000, '', 3), 24000)
})

// AMOT125 (C-AMOT-VER4-020) — un devis d'origine (niveau 1) garde la part
// batterie du serveur (`rendement_une_fois=False`). Attendu calculé par
// `pricing.calculate_savings_roi(6.0, 60000, 90000, battery_kwh=10,
// stockage_present=True, etude_horaire=<cas VB AMOT72>, rendement_une_fois=False)`
// (exécuté le 04/11/2026) : roi_a 13,4, net_gain_avec 72 819 ; corrigé : 12,9 / 79 603.
test("regles d'origine : part batterie du serveur", () => {
  const annuel = {
    production_kwh: 9000, consommation_kwh: 8000,
    taux_autoconso_sans: 0.45, taux_autoconso_avec: 0.75,
  }
  const base = { annuel, rendementBatterie: 0.9, stockage: true }
  const origine = paybackMoteurHoraire(90000, 7200, { ...base, reglesCalcul: 1 })
  assert.equal(origine.paybackYears, 13.4)
  assert.equal(origine.netGain, 72819)
  for (const reglesCalcul of [2, 12, null]) {
    const r = paybackMoteurHoraire(90000, 7200, { ...base, reglesCalcul })
    assert.deepEqual([r.paybackYears, r.netGain], [12.9, 79603])
  }
  assert.equal(reglesAuMoins(undefined, 3), true)
  assert.equal(reglesAuMoins(1, 2), false)
})
