"""AANA24 (C-AANA-025, D-AANA-2) — un ticket SAV annulé est exclu de tout
taux : scorecard technicien et rapport terrain donnent le MÊME taux de
récidive ; le rapport service ne le compte ni ouvert ni résolu.

Scénario R11 : un technicien, 1 ticket normal + 1 ticket récidive ANNULÉ.
Avant le correctif : scorecard 50,0 contre 0,0 au rapport terrain.

Données RÉELLES en base (aucun mock). Retirer ``annule=False`` rougit.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'


class TestTicketsAnnules(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana24-co', defaults={'nom': 'AANA24 Co'})[0]
        self.user = User.objects.create_user(
            username='aana24_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.tech = User.objects.create_user(
            username='aana24_tech', password='x', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(company=self.company, nom='Cli R11')
        Ticket.objects.create(
            company=self.company, reference='T-AANA24-1', client=client,
            technicien_responsable=self.tech)
        Ticket.objects.create(
            company=self.company, reference='T-AANA24-2', client=client,
            technicien_responsable=self.tech, est_recidive=True, annule=True)

    def test_meme_taux_recidive(self):
        resp = self.api.get(
            f'{BASE}/insights/technicien-scorecard/?technicien={self.tech.id}')
        self.assertEqual(resp.status_code, 200)
        scorecard = resp.data['scorecard']

        resp = self.api.get(f'{BASE}/reports/field/?technicien={self.tech.id}')
        self.assertEqual(resp.status_code, 200)
        terrain = resp.data['recidive']['taux_pct']

        self.assertEqual(scorecard['nb_recidives'], 0)
        self.assertEqual(scorecard['taux_recidive_pct'], 0.0)
        self.assertEqual(scorecard['taux_recidive_pct'], terrain)

    def test_rapport_service_exclut_annules(self):
        resp = self.api.get(f'{BASE}/reports/service/')
        self.assertEqual(resp.status_code, 200)
        # Une seule base : le ticket annulé n'est ni ouvert ni « résolu ».
        self.assertEqual(
            resp.data['tickets_ouverts'] + resp.data['tickets_resolus'], 1)
        self.assertEqual(
            sum(t['count'] for t in resp.data['tickets_par_statut']), 1)
