// CIQ124 — fonctions pures de l'aperçu C&I serveur. Run :
//   node --test src/features/ventes/etudeCiPreview.test.mjs
// L'échantillon du contrat est LU dans le fichier partagé, jamais recopié.
import test from 'node:test'
import assert from 'node:assert/strict'
import { documentContrat, enTexte } from '../../test/fixtures/contractSamples.js'
import {
  construireCorpsCi, alertesAffichables, libelleProvenance, reponseAJour,
} from './etudeCiPreviewPur.js'

const CONTRAT = documentContrat('ventes', 'etude_ci_preview')

test('corps conforme à l’échantillon du contrat (nombres tapés en texte)', () => {
  assert.deepEqual(construireCorpsCi(enTexte(CONTRAT.corps)), CONTRAT.corps)
})

test('corps : aucune valeur arrondie ni rejetée', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.contraintes.longueur_dc_m = '40,37'
  etat.puissance_souscrite_kva = '72.125'
  const corps = construireCorpsCi(etat)
  assert.equal(corps.contraintes.longueur_dc_m, 40.37)
  assert.equal(corps.puissance_souscrite_kva, 72.125)
})

test('état incomplet → null (aucun appel)', () => {
  assert.equal(construireCorpsCi(null), null)
  assert.equal(construireCorpsCi({ ...enTexte(CONTRAT.corps), mode: 'residentiel' }), null)
  const sansConso = enTexte(CONTRAT.corps)
  sansConso.consommation = { kwh_mensuels: Array(12).fill(''), kwh_annuel: '', factures_mad: [] }
  assert.equal(construireCorpsCi(sansConso), null)
})

test('une taille explicite suffit à ancrer le calcul', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.consommation = { kwh_mensuels: [], factures_mad: [] }
  etat.taille_explicite_kwc = '55'
  assert.equal(construireCorpsCi(etat).taille_explicite_kwc, 55)
})

test('aucune alerte perdue ; les internes sont marquées', () => {
  const reponse = {
    alertes: [
      ...CONTRAT.exemple.alertes,
      { code: 'sans_message', champ: 'x', niveau: 'info', interne: false },
    ],
  }
  const rendues = alertesAffichables(reponse)
  assert.equal(rendues.length, reponse.alertes.length)
  assert.equal(rendues[0].interne, true)
  assert.equal(rendues.at(-1).message, 'sans_message')
  assert.equal(rendues.at(-1).interne, false)
})

test('libellés de provenance', () => {
  assert.equal(libelleProvenance({ origine: 'lead', detail: 'facture', date: '2026-09-10' }),
    'fiche lead — lu sur facture (2026-09-10)')
  assert.equal(libelleProvenance({ origine: 'mesure_visite', detail: 'visite 7' }),
    'mesuré en visite')
  assert.equal(libelleProvenance(null), 'origine inconnue')
})

test('une réponse arrivée après une nouvelle saisie est ignorée', () => {
  const ancien = construireCorpsCi(enTexte(CONTRAT.corps))
  const nouveau = { ...ancien, puissance_souscrite_kva: 80 }
  const donnees = CONTRAT.exemple
  assert.equal(reponseAJour(donnees, JSON.stringify(ancien), nouveau), null)
  assert.equal(reponseAJour(donnees, JSON.stringify(nouveau), nouveau), donnees)
  assert.equal(reponseAJour(donnees, JSON.stringify(nouveau), null), null)
})
