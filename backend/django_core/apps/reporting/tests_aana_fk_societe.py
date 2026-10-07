"""AANA17 (C-AANA-007, volet pilotage) — un responsable de A ne peut pas
ajouter un utilisateur de B aux destinataires d'une alerte KPI, ni créer une
config de tableau de bord pour un utilisateur de B.

Scénario R5. Avant le correctif : ``is_valid=True`` (l'alerte aurait envoyé
le chiffre de A à un utilisateur de B).

Données RÉELLES en base, vraie API (aucun mock). Retirer
``same_company_fields`` rougit ce test.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.reporting.models import DashboardConfig, KpiAlerte
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'


class TestFkSociete(TestCase):
    def setUp(self):
        self.co_a = Company.objects.get_or_create(
            slug='aana17r-a', defaults={'nom': 'AANA17R A'})[0]
        self.co_b = Company.objects.get_or_create(
            slug='aana17r-b', defaults={'nom': 'AANA17R B'})[0]
        self.responsable = User.objects.create_user(
            username='aana17r_resp', password='x', company=self.co_a,
            role_legacy='responsable')
        self.collegue = User.objects.create_user(
            username='aana17r_collegue', password='x', company=self.co_a,
            role_legacy='normal')
        self.etranger = User.objects.create_user(
            username='aana17r_etranger', password='x', company=self.co_b,
            role_legacy='normal')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.responsable)}'))

    def _alerte(self, destinataires):
        return self.api.post(f'{BASE}/kpi-alertes/', {
            'nom': 'Stock élevé', 'kpi': KpiAlerte.Kpi.VALEUR_STOCK_TOTALE,
            'operateur': KpiAlerte.Operateur.SUP, 'seuil': '60',
            'destinataires_utilisateurs': destinataires,
        }, format='json')

    def test_destinataire_autre_societe_refuse(self):
        resp = self._alerte([self.etranger.pk])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('destinataires_utilisateurs', resp.data)
        self.assertFalse(KpiAlerte.objects.filter(company=self.co_a).exists())

        resp = self._alerte([self.collegue.pk])
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_config_user_autre_societe_refuse(self):
        resp = self.api.post(f'{BASE}/dashboard-config/', {
            'user': self.etranger.pk, 'cards': [],
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('user', resp.data)
        self.assertFalse(DashboardConfig.objects.filter(
            user=self.etranger).exists())

        resp = self.api.post(f'{BASE}/dashboard-config/', {
            'user': self.collegue.pk, 'cards': [],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
