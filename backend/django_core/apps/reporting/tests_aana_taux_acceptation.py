"""AANA28 (C-AANA-022) — le tableau de bord SERT
``conversion.taux_acceptation_pct`` (contrat AANA1, PACT10).

Given 10 devis dont 3 acceptés et 15 factures émises, When GET dashboard,
Then ``taux_acceptation_pct = 30.0`` — jamais 150 % (l'ancienne formule
nb_factures ÷ nb_devis de l'écran). La forme servie est confrontée au
contrat partagé ``contract_samples/dashboard.json`` (chargé, pas recopié).

AANA58 (D-AANA-VER-1) — le taux est acceptés ÷ devis ENVOYÉS dans la période
(même sélecteur que le Quote-to-cash) : un brouillon jamais envoyé n'entre pas
dans la base.

Données RÉELLES en base (aucun mock). Retirer la clé rougit ce test.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
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

    def _devis(self, n, acceptes):
        for i in range(n):
            Devis.objects.create(
                company=self.company, reference=f'DEV-AANA28-{i}',
                client=self.client_obj, date_envoi=timezone.now(),
                statut=(Devis.Statut.ACCEPTE if i < acceptes
                        else Devis.Statut.ENVOYE))

    def test_meme_taux_que_le_quote_to_cash(self):
        # 5 envoyés dont 2 acceptés + un brouillon jamais envoyé : 40.0 des deux côtés.
        self._devis(5, acceptes=2)
        Devis.objects.create(
            company=self.company, reference='DEV-AANA58-BRO',
            client=self.client_obj, statut=Devis.Statut.BROUILLON)
        d = timezone.localdate().isoformat()
        rep = self.api.get(URL, {'from': d, 'to': d})
        q2c = self.api.get('/api/django/ventes/dashboard/', {'start': d, 'end': d})
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(q2c.status_code, 200)
        conv = rep.data['conversion']
        self.assertEqual(conv['taux_acceptation_pct'], 40.0)
        self.assertEqual(conv['taux_acceptation_pct'], q2c.data['devis']['taux_acceptation_pct'])
        self.assertEqual(conv['nb_envoyes_periode'], q2c.data['devis']['envoyes_periode'])
        self.assertEqual(conv['nb_acceptes_periode'], q2c.data['devis']['acceptes_periode'])
        self.assertEqual(conv['nb_devis'], 6)

    def test_taux_servi(self):
        self._devis(10, acceptes=3)
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
        self.assertEqual(conversion['nb_envoyes_periode'], 10)
        self.assertEqual(conversion['nb_acceptes_periode'], 3)

    def test_taux_null_sans_devis(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['conversion']['taux_acceptation_pct'])
