// AGNR35 — l'écran calcule avec le barème EFFECTIF de la société servi par le
// profil (`bareme_effectif`, contrat AGNR3) au lieu des constantes nationales.
// Valeurs serveur figées (sonde V_VA p5 de l'audit C-AGNR-006) : 12 × 1 500
// MAD ⇒ 10 189 kWh/an pour l'exemple « société » (dernier palier 1,5958,
// redevance 45 MAD/mois) ; l'exemple « national » garde les chiffres
// d'aujourd'hui (10 057 kWh/an).
//
// Run : node --test src/features/ventes/solar.agnrBaremeSociete.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  baremeDepuisProfil, consoAnnuelleDepuisFactures, controlerFacturesSaisies, controlerKwhDeclare,
  consoDescendDesFactures, computeROI, chargesFixesTtc,
} from './solar.js'
import { exempleContrat } from '../../test/fixtures/contractSamples.js'

const SOCIETE = exempleContrat('parametres', 'bareme_effectif').bareme_effectif
const NATIONAL = exempleContrat('parametres', 'bareme_effectif', 'exemple_national').bareme_effectif
const FACTURES = Array(12).fill(1500)

test('AGNR35 — société : 12 × 1 500 MAD ⇒ 10 189 kWh/an (comme le serveur)', () => {
  const b = baremeDepuisProfil(SOCIETE)
  assert.equal(b.chargesFixes, 45)
  assert.equal(consoAnnuelleDepuisFactures(FACTURES, 'onee', b.tranches, b.chargesFixes), 10189)
})

test('AGNR35 — national : barème nul ⇒ chiffres d’aujourd’hui (10 057 kWh/an)', () => {
  assert.equal(baremeDepuisProfil(NATIONAL), null)
  assert.equal(consoAnnuelleDepuisFactures(FACTURES, 'onee'), 10057)
})

test('AGNR35 — contrôles de saisie au barème société (plancher = redevance)', () => {
  const b = baremeDepuisProfil(SOCIETE)
  const serie = Array(12).fill(42)
  // 42 MAD : au-dessus des lignes fixes nationales (39,94) mais sous la redevance 45.
  assert.ok(42 > chargesFixesTtc())
  assert.deepEqual(controlerFacturesSaisies(serie).sousPlancher, [])
  assert.equal(controlerFacturesSaisies(serie, { chargesFixes: b.chargesFixes }).sousPlancher.length, 12)
  const national = controlerKwhDeclare(800, { factureHiver: 1500 })
  const societe = controlerKwhDeclare(800, { factureHiver: 1500 }, b.tranches, b.chargesFixes)
  assert.notEqual(societe.factureBareme, national.factureBareme)
})

test('AGNR35 — une conso dérivée au barème société reste « descendue des factures »', () => {
  const b = baremeDepuisProfil(SOCIETE)
  assert.equal(consoDescendDesFactures(10189, FACTURES, 'onee'), false)
  assert.equal(consoDescendDesFactures(10189, FACTURES, 'onee', b), true)
})

test('AGNR35 — computeROI au modèle « factures » lit la grille et la redevance société', () => {
  const base = {
    kwp: 6, factures: FACTURES, dayUsagePct: 60, totalSans: 60000, totalAvec: 90000,
    batteryKwh: 0, consoAnnuelleKwh: 10189, utility: 'onee', productible: 1651,
  }
  const national = computeROI(base)
  const societe = computeROI({ ...base, bareme: baremeDepuisProfil(SOCIETE) })
  assert.equal(societe.savings_model, 'factures')
  assert.notEqual(societe.eco_annuelle_sans, national.eco_annuelle_sans)
})

test('AGNR35 — rouvrir puis ré-enregistrer sans toucher ne change jamais la conso stockée', async () => {
  const { devisVersEtat, entreesDeEtat } = await import('./quote/etatDevis.js')
  const b = baremeDepuisProfil(SOCIETE)
  const devis = (conso) => ({
    id: 5, mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0', lignes: [],
    etude_params: { factures_mensuelles_reelles: FACTURES, conso_annuelle: conso, distributeur: 'onee' },
  })
  // Stockée au barème NATIONAL (avant AGNR35) : identique à la réécriture.
  const ancien = devisVersEtat(devis(10057), { bareme: b })
  assert.equal(entreesDeEtat({ ...ancien, bareme: b }).conso_annuelle, 10057)
  // Stockée au barème SOCIÉTÉ : identique aussi.
  const recent = devisVersEtat(devis(10189), { bareme: b })
  assert.equal(entreesDeEtat({ ...recent, bareme: b }).conso_annuelle, 10189)
  // Des factures RETOUCHÉES se re-dérivent au barème société.
  const retouche = { ...ancien, bareme: b, monthly: Array(12).fill(1600) }
  assert.equal(entreesDeEtat(retouche).conso_annuelle,
    consoAnnuelleDepuisFactures(Array(12).fill(1600), 'onee', b.tranches, b.chargesFixes))
})
