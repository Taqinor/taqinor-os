// AMOT72 (C-AMOT-024, volet miroir écran) — en modèle HORAIRE, le rendement
// aller-retour de la batterie est DÉJÀ dans l'économie servie (`etude_horaire`
// borne le restitué) : le miroir écran `paybackMoteurHoraire` ne le déduit
// plus une seconde fois (part batterie 0), comme le serveur corrigé par AMOT58
// (`calculate_savings_roi(..., rendement_une_fois=True)`). Payback et gain net
// 25 ans de l'écran = ceux du PDF.
//
// La valeur serveur est LUE d'une fixture produite par le serveur corrigé
// (`golden/amot72_payback_serveur.json`, générée par
// `frontend/scripts/amot72_fixture_serveur.py`), jamais recopiée à la main.
// Run : node --test src/features/ventes/solar.amot72.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { paybackMoteurHoraire } from './solar.js'

const ICI = dirname(fileURLToPath(import.meta.url))
const FIXTURE = JSON.parse(readFileSync(join(ICI, 'golden', 'amot72_payback_serveur.json'), 'utf-8'))
const { entree, serveur } = FIXTURE

test('AMOT72 — cas VB (6 kWc, éco avec 7 200, total 90 000) : payback et gain net = serveur', () => {
  const bloc = entree.etude_horaire
  const r = paybackMoteurHoraire(entree.total_avec, bloc.annuel.economie_avec_mad, {
    annuel: bloc.annuel,
    rendementBatterie: bloc.rendement_batterie,
    stockage: true,
  })
  assert.equal(Math.round(r.paybackYears * 10) / 10, serveur.roi_a)
  assert.equal(r.jamaisRembourse, serveur.roi_a_jamais)
  assert.equal(r.netGain, serveur.net_gain_avec)
})

test('AMOT72 — option sans batterie inchangée (aucune part batterie)', () => {
  const bloc = entree.etude_horaire
  const r = paybackMoteurHoraire(entree.total_sans, bloc.annuel.economie_sans_mad, { annuel: bloc.annuel })
  assert.equal(Math.round(r.paybackYears * 10) / 10, serveur.roi_s)
  assert.equal(r.netGain, serveur.net_gain_sans)
})
