"""AANA28 (C-AANA-022) — le tableau de bord SERT
``conversion.taux_acceptation_pct`` (contrat AANA1, PACT10).

Given 10 devis dont 3 acceptés et 15 factures émises, When GET dashboard,
Then ``taux_acceptation_pct = 30.0`` — jamais 150 % (l'ancienne formule
nb_factures ÷ nb_devis de l'écran). La forme servie est confrontée au
contrat partagé ``contract_samples/dashboard.json`` (chargé, pas recopié).

Données RÉELLES en base (aucun mock). Retirer la clé rougit ce test.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis, Facture
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/dashboard/'
CONTRAT = Path(__file__).resolve().parent / 'contract_samples' / 'dashboard.json'


class TestTauxAcceptationServi(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana28-co', defaults={'nom': 'AANA28 Co'})[0]
        self.user = User.objects.create_user(
            username='aana28_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli AANA28')

    def test_taux_servi(self):
        for i in range(10):
            Devis.objects.create(
                company=self.company, reference=f'DEV-AANA28-{i}',
                client=self.client_obj,
                statut=(Devis.Statut.ACCEPTE if i < 3
                        else Devis.Statut.ENVOYE))
        for i in range(15):
            Facture.objects.create(
                company=self.company, reference=f'FAC-AANA28-{i}',
                client=self.client_obj, statut=Facture.Statut.EMISE)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        conversion = resp.data['conversion']
        self.assertEqual(conversion['nb_devis'], 10)
        self.assertEqual(conversion['nb_acceptes'], 3)
        self.assertEqual(conversion['nb_factures'], 15)
        self.assertEqual(conversion['taux_acceptation_pct'], 30.0)

        # Forme servie == contrat partagé (AANA1), clés du bloc et de la racine.
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))['exemple']
        self.assertEqual(set(conversion), set(contrat['conversion']))
        self.assertEqual(set(resp.data), set(contrat))

    def test_taux_null_sans_devis(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['conversion']['taux_acceptation_pct'])
