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

// T4-U3-022 — site qui GARDE sa pompe : le débit et les heures de la pompe
// actuelle sont le besoin déclaré ; « Pompe actuelle » est choisi pour lui.
const entree = (colonne, valeur, extra = {}) => ({
  colonne, valeur, provenance: 'client', date: '2026-11-20', ...extra,
})

test('besoin::test_debit_et_heures_de_la_pompe_actuelle_font_le_besoin', () => {
  const res = entreesPompageDuLead(lead([
    entree('mode_pompe', 'existante'),
    entree('pompe_actuelle_debit_m3h', 12),
    entree('pompage_heures_jour', 8),
    // Le volume DÉDUIT servi à côté (12 × 8) n'est pas une déclaration.
    entree('besoin_eau_m3j', 96, { provenance: 'derive' }),
  ]))
  assert.equal(res.saisie['besoin.mode'], 'pompe_actuelle')
  assert.equal(res.saisie['besoin.debit_actuel_m3h'], '12')
  assert.equal(res.saisie['besoin.heures_actuelles_jour'], '8')
  assert.equal('besoin.volume_m3_jour' in res.saisie, false)
  const suivant = appliquerSaisiePompageLead(
    res.saisie, () => true, {}, poserSaisie)(POMPAGE_SAISIE_VIDE)
  assert.equal(suivant.besoin.mode, 'pompe_actuelle')
  assert.equal(suivant.besoin.debit_actuel_m3h, '12')
  assert.equal(suivant.besoin.heures_actuelles_jour, '8')
  assert.equal(suivant.mode_pompe, 'existante')
})

test('besoin::test_volume_declare_passe_avant_la_pompe_actuelle', () => {
  // Même ordre que le serveur (besoin_retenu) : le volume déclaré d'abord.
  const res = entreesPompageDuLead(lead([
    entree('besoin_eau_m3j', 135),
    entree('pompe_actuelle_debit_m3h', 12),
    entree('pompage_heures_jour', 8),
  ]))
  assert.equal(res.saisie['besoin.mode'], 'volume_declare')
  assert.equal(res.saisie['besoin.volume_m3_jour'], '135')
})

test('besoin::test_heures_seules_ne_choisissent_aucun_mode', () => {
  const res = entreesPompageDuLead(lead([entree('pompage_heures_jour', 8),
    entree('pompe_debit_m3h', 20)]))
  assert.equal('besoin.mode' in res.saisie, false)
  assert.equal(res.ecran.pompeDebit, '20')
})

// ACAL1261 — les VALEURS reprises s'affichent en français ; l'état d'écran
// garde la clé machine ; une valeur inconnue passe telle quelle.
test('libelles::test_valeurs_reprises_en_francais_cle_machine_dans_l_etat', () => {
  const res = entreesPompageDuLead(lead([
    entree('pompe_actuelle_type', 'immergee'), entree('pompe_alim_actuelle', 'diesel'),
    entree('mode_pompe', 'neuve'), entree('irrigation_methode', 'goutte'),
    entree('pompe_actuelle_phases', 3), entree('region_agricole', 'inconnue-x'),
  ]))
  const affiche = Object.fromEntries(res.provenances.map((p) => [p.colonne, p.valeur]))
  assert.deepEqual(affiche, {
    pompe_actuelle_type: 'Immergée', pompe_alim_actuelle: 'Gasoil', mode_pompe: 'Pompe neuve',
    irrigation_methode: 'Goutte-à-goutte', pompe_actuelle_phases: 'Triphasé',
    region_agricole: 'inconnue-x',
  })
  assert.equal(res.ecran.pompeType, 'immergee')
  assert.equal(res.eco.energie, 'diesel')
  assert.equal(res.ecran.farmIrrigation, 'goutte')
  assert.equal(res.saisie.mode_pompe, 'neuve')
  assert.equal(res.saisie['plaque.phases'], 'tri')
  // Un nombre garde sa forme (aucune table pour lui).
  assert.equal(entreesPompageDuLead(lead([entree('pompe_hmt_m', 60)])).provenances[0].valeur, '60')
})

test('besoin::test_une_saisie_du_vendeur_n_est_jamais_ecrasee', () => {
  const res = entreesPompageDuLead(lead([
    entree('pompe_actuelle_debit_m3h', 12), entree('pompage_heures_jour', 8),
  ]))
  const vendeur = poserSaisie(POMPAGE_SAISIE_VIDE, 'besoin.mode', 'volume_declare')
  const libre = (_cle, courant) => courant === '' || courant == null
  const suivant = appliquerSaisiePompageLead(res.saisie, libre, {}, poserSaisie)(vendeur)
  assert.equal(suivant.besoin.mode, 'volume_declare')
})
