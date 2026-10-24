// AGR127 — fonctions pures de l'aperçu pompage serveur. Run :
//   node --test src/features/ventes/etudePompagePreview.test.mjs
// L'échantillon du contrat est LU dans le fichier partagé, jamais recopié.
import test from 'node:test'
import assert from 'node:assert/strict'
import { documentContrat, enTexte } from '../../test/fixtures/contractSamples.js'
import {
  construireCorpsPompage, manquantsPompage, alertesAffichables,
  libelleProvenance, nombreOuNull,
} from './etudePompagePreviewPur.js'

const CONTRAT = documentContrat('ventes', 'etude_pompage_preview')

test('corps conforme à l’échantillon du contrat (nombres tapés en texte)', () => {
  const etat = enTexte(CONTRAT.corps)
  assert.deepEqual(construireCorpsPompage(etat), CONTRAT.corps)
})

test('corps : aucune valeur arrondie ni rejetée', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.source.niveau_dynamique_m = '40,37'
  etat.distance_champ_m = '25.125'
  const corps = construireCorpsPompage(etat)
  assert.equal(corps.source.niveau_dynamique_m, 40.37)
  assert.equal(corps.distance_champ_m, 25.125)
})

test('état incomplet → null (aucun appel)', () => {
  assert.equal(construireCorpsPompage(null), null)
  assert.equal(construireCorpsPompage({}), null)
  const sansBesoin = enTexte(CONTRAT.corps)
  sansBesoin.besoin.volume_m3_jour = ''
  assert.equal(construireCorpsPompage(sansBesoin), null)
  const sansHauteur = enTexte(CONTRAT.corps)
  sansHauteur.source.niveau_dynamique_m = ''
  sansHauteur.source.niveau_statique_m = ''
  sansHauteur.hmt.saisie_m = ''
  assert.equal(construireCorpsPompage(sansHauteur), null)
  assert.deepEqual(manquantsPompage(sansHauteur),
    ['la hauteur (HMT ou niveau d\'eau)'])
})

test('champ vide → null, jamais un défaut', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.distance_champ_m = ''
  etat.besoin.region = ''
  const corps = construireCorpsPompage(etat)
  assert.equal(corps.distance_champ_m, null)
  assert.equal(corps.besoin.region, null)
  assert.equal(nombreOuNull(''), null)
  assert.equal(nombreOuNull('abc'), null)
})

// AGQ27 (C-AGQ-026) — corps::test_mode_volume_n_envoie_pas_la_pompe_actuelle :
// seuls les champs du mode de besoin choisi partent ; une valeur tapée sous
// un autre mode part `null` (mutant : spread inconditionnel ⇒ rouge).
test('corps::test_mode_volume_n_envoie_pas_la_pompe_actuelle', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.besoin.debit_actuel_m3h = '10'
  etat.besoin.heures_actuelles_jour = '6'
  const volume = construireCorpsPompage(etat).besoin
  assert.equal(volume.mode, 'volume_declare')
  assert.equal(volume.volume_m3_jour, 135)
  assert.equal(volume.debit_actuel_m3h, null)
  assert.equal(volume.heures_actuelles_jour, null)
  etat.besoin.mode = 'pompe_actuelle'
  const actuelle = construireCorpsPompage(etat).besoin
  assert.equal(actuelle.debit_actuel_m3h, 10)
  assert.equal(actuelle.heures_actuelles_jour, 6)
  assert.equal(actuelle.volume_m3_jour, null)
  // Débit souhaité, mois de pointe, région : servis quel que soit le mode.
  assert.equal(actuelle.mois_pointe, 7)
  assert.equal(actuelle.region, 'souss-massa')
})

test('mode neuve → plaque nulle ; mode existante → plaque transmise', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.plaque = { kw: '5.5', tension_v: '380', phases: 'tri', cv: '', courant_a: '' }
  assert.equal(construireCorpsPompage(etat).plaque, null)
  etat.mode_pompe = 'existante'
  assert.deepEqual(construireCorpsPompage(etat).plaque,
    { kw: 5.5, tension_v: 380, phases: 'tri', cv: null, courant_a: null })
})

test('aucune alerte perdue', () => {
  const reponse = {
    alertes: [
      { code: 'couverture_insuffisante', champ: 'besoin', message: 'A' },
      { code: 'surdimensionnement', champ: 'champ', message: 'B' },
      { code: 'kw_plaque_a_relever', champ: 'plaque.kw', message: '' },
    ],
  }
  const vues = alertesAffichables(reponse)
  assert.equal(vues.length, 3)
  assert.deepEqual(vues.map((a) => a.code),
    ['couverture_insuffisante', 'surdimensionnement', 'kw_plaque_a_relever'])
  assert.equal(vues[2].message, 'kw_plaque_a_relever')
  assert.deepEqual(alertesAffichables(CONTRAT.exemple).length,
    CONTRAT.exemple.alertes.length)
  assert.deepEqual(alertesAffichables(null), [])
})

test('libellés de provenance', () => {
  assert.equal(libelleProvenance({ origine: 'saisie', detail: null, date: null }), 'saisi')
  assert.equal(libelleProvenance({ origine: 'lead', detail: 'mesure_visite', date: '2026-09-15' }),
    'fiche lead — mesuré en visite (2026-09-15)')
  assert.equal(libelleProvenance(null), 'origine inconnue')
})
