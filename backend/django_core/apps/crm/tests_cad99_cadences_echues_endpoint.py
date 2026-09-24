"""CAD99 — les cadences échues EXPOSÉES au cockpit (moitié écran de CAD75).

La route ``GET relance-etapes/cadences-echues/?jours=`` sert la liste du
sélecteur ``cadences_echues_a_clore`` au widget « Relances du jour ». Garanties
verrouillées ici :

  * le seuil ``jours`` est OBLIGATOIRE et renvoyé tel qu'appliqué (le serveur
    n'invente aucun nombre) — sans lui, 400 qui NOMME le champ ;
  * la réponse a EXACTEMENT la forme de ``cadences_echues.json`` ;
  * LECTURE PURE : aucune touche n'est close, aucune cadence arrêtée ;
  * multi-tenant : un lead d'une autre société n'apparaît jamais.

Le temps est GELÉ (« échu depuis plus de N jours » dépend de l'horloge).
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 23, 12, 0, tzinfo=horaires.CASABLANCA)
AUJOURDHUI = MAINTENANT.date()

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'
URL = '/api/django/crm/relance-etapes/cadences-echues/'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class CadencesEchuesEndpointTests(TestCase):

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD99 Solaire',
                                              slug='cad99')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad99-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, company, nom, *, retard_jours):
        owner = self.acteur if company == self.company else None
        lead = Lead.objects.create(
            company=company, nom=nom, prenom='Karim', ville='Marrakech',
            stage=stages.CONTACTED, owner=owner)
        due = AUJOURDHUI - datetime.timedelta(days=retard_jours)
        quand = datetime.datetime.combine(
            due, datetime.time(10, 0), tzinfo=horaires.CASABLANCA)
        etape = RelanceEtape.objects.create(
            company=company, lead=lead, cadence='contact', ordre=6,
            due_at=quand, due_date=due, canal=RelanceEtape.Canal.APPEL,
            libelle='Appel 4')
        return lead, etape

    def test_le_seuil_est_obligatoire_et_nomme(self):
        for params in ({}, {'jours': ''}, {'jours': '-3'}, {'jours': 'sept'}):
            resp = self.api.get(URL, params)
            self.assertEqual(resp.status_code, 400, params)
            self.assertIn('jours', resp.data)

    def test_la_liste_a_la_forme_du_contrat_et_renvoie_le_seuil(self):
        lead, _ = self._touche(self.company, 'Tazi', retard_jours=13)
        resp = self.api.get(URL, {'jours': 7})
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat = _contrat('cadences_echues')
        self.assertEqual(set(resp.data), set(contrat['exemple']))
        self.assertEqual(resp.data['jours'], 7)
        self.assertEqual(resp.data['count'], 1)
        ligne = resp.data['results'][0]
        self.assertEqual(set(ligne), set(contrat['exemple']['results'][0]))
        self.assertEqual(ligne['lead_id'], lead.id)
        self.assertEqual(ligne['jours_de_retard'], 13)

    def test_sous_le_seuil_rien_n_apparait(self):
        self._touche(self.company, 'Recent', retard_jours=3)
        resp = self.api.get(URL, {'jours': 7})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['results'], [])

    def test_lecture_pure_rien_n_est_clos(self):
        lead, etape = self._touche(self.company, 'Abandonne', retard_jours=20)
        self.api.get(URL, {'jours': 7})
        etape.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertEqual(lead.relance_etapes.count(), 1)

    def test_un_lead_d_une_autre_societe_n_apparait_jamais(self):
        autre = Company.objects.create(nom='CAD99 Autre', slug='cad99-autre')
        self._touche(autre, 'Ailleurs', retard_jours=30)
        resp = self.api.get(URL, {'jours': 7})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['results'], [])
