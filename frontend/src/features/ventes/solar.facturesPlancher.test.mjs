// ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — `controlerFacturesSaisies` refuse
// une facture réelle sous les lignes fixes du compteur et signale un écart avec
// la facture d'hiver du lead. Run : node --test src/features/ventes/solar.facturesPlancher.test.mjs
// Le blocage à l'enregistrement est EXÉCUTÉ (QJR239, aucune lecture de
// source) par `pages/ventes/DevisGeneratorEditionLead.test.jsx`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { controlerFacturesSaisies, estimerMois, chargesFixesTtc } from './solar.js'

test('DEV-202609-0108 : estimerMois(1, 1600) a deux mois sous le plancher', () => {
  const ctl = controlerFacturesSaisies(estimerMois(1, 1600), { factureHiverLead: 3000 })
  assert.deepEqual(ctl.sousPlancher, [1, 12])
  assert.ok(Math.abs(ctl.plancher - 39.936) < 1e-9)
  assert.equal(ctl.plancher, chargesFixesTtc())
})

test('zéro (mois inconnu) et une facture plausible passent', () => {
  const ctl = controlerFacturesSaisies([0, ...Array(11).fill(900)], {})
  assert.deepEqual(ctl.sousPlancher, [])
  assert.equal(ctl.ecartLead, null)
})

test("écart avec la facture d'hiver du lead : signalé au-delà de 25 %", () => {
  assert.deepEqual(
    controlerFacturesSaisies(estimerMois(1600, 1600), { factureHiverLead: 3000 }).ecartLead,
    { serie: 1600, lead: 3000 })
  assert.equal(
    controlerFacturesSaisies(estimerMois(900, 900), { factureHiverLead: 900 }).ecartLead, null)
  assert.equal(
    controlerFacturesSaisies(estimerMois(1000, 1000), { factureHiverLead: 900 }).ecartLead, null)
  // Sans facture du lead : rien à comparer.
  assert.equal(controlerFacturesSaisies(estimerMois(1600, 1600), {}).ecartLead, null)
})
