// Rejeu live AGQ41 (24/10) — le débit du forage du lead alimente le générateur
// agricole (aucun test n'existait pour entreesPompageLead.js : nouveau fichier).
// Run : node --test src/features/ventes/quote/entreesPompageLead.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  entreesPompageDuLead, appliquerSaisiePompageLead,
} from './entreesPompageLead.js'
import { POMPAGE_SAISIE_VIDE, poserSaisie } from '../etudePompagePreviewPur.js'

const lead = (entrees) => ({ entrees_pompage: { entrees, manquants: [] } })
const forage = (extra = {}) => ({
  colonne: 'debit_forage_m3h', valeur: 36, provenance: 'client', date: '2026-10-20',
  cle_etude: 'source', chemin: 'source.debit_exploitation_m3h', ...extra,
})

test('debit_forage::test_debit_et_origine_du_lead_vont_au_point_d_eau', () => {
  const res = entreesPompageDuLead(lead([forage({ origine: 'client' })]))
  assert.equal(res.saisie['source.debit_exploitation_m3h'], '36')
  assert.equal(res.saisie['source.debit_exploitation_origine'], 'client')
  assert.equal(res.provenances[0].colonne, 'debit_forage_m3h')
  assert.match(res.provenances[0].libelle, /forage/)
  // Appliqué sur l'état du générateur : les champs de l'écran sont remplis.
  const poses = {}
  const suivant = appliquerSaisiePompageLead(
    res.saisie, () => true, poses, poserSaisie)(POMPAGE_SAISIE_VIDE)
  assert.equal(suivant.source.debit_exploitation_m3h, '36')
  assert.equal(suivant.source.debit_exploitation_origine, 'client')
  assert.equal(POMPAGE_SAISIE_VIDE.source.debit_exploitation_m3h, '')
})

test('debit_forage::test_les_4_origines_du_selecteur_passent_telles_quelles', () => {
  for (const origine of ['essai', 'foreur', 'client', 'mesure_visite']) {
    const res = entreesPompageDuLead(lead([forage({ origine })]))
    assert.equal(res.saisie['source.debit_exploitation_origine'], origine)
  }
})

test('debit_forage::test_origine_jamais_inventee', () => {
  // Sans `origine` servie (colonne source vide), la `provenance` de l'entrée
  // (repli « client » / « site_web ») n'est PAS une origine de débit.
  const sans = entreesPompageDuLead(lead([forage()]))
  assert.equal(sans.saisie['source.debit_exploitation_m3h'], '36')
  assert.equal('source.debit_exploitation_origine' in sans.saisie, false)
  // Une origine hors des 4 valeurs du sélecteur n'est pas recopiée.
  const inconnue = entreesPompageDuLead(lead([forage({ origine: 'voisin' })]))
  assert.equal('source.debit_exploitation_origine' in inconnue.saisie, false)
  // Colonne vide : rien n'est écrit.
  assert.equal(entreesPompageDuLead(lead([forage({ valeur: null })])), null)
})
