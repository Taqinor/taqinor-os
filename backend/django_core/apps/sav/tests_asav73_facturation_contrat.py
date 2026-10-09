"""ASAV73 (D-ASAV-3 a) — la fiche d'un contrat de maintenance ne sert plus
d'échéance de facturation récurrente (aucun écrivain ne facture) ; le prix du
contrat reste affiché.

Run :
    python manage.py test apps.sav.tests_asav73_facturation_contrat -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance

User = get_user_model()


class FacturationContratTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav73-co', defaults={'nom': 'ASAV73 Co'})
        user = User.objects.create_user(
            username='asav73_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV73')
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=client, actif=True,
            facturation_active=True, prix=Decimal('1200'),
            date_debut=timezone.localdate() - timedelta(days=400))

    def test_echeances_non_servies_prix_conserve(self):
        for url in (
                f'/api/django/sav/contrats-maintenance/{self.contrat.pk}/',
                '/api/django/sav/contrats-maintenance/'):
            r = self.api.get(url)
            self.assertEqual(r.status_code, 200, r.content)
            ligne = r.data
            if isinstance(ligne, dict) and 'results' in ligne:
                ligne = ligne['results'][0]
            self.assertNotIn('facturation_due', ligne)
            self.assertNotIn('prochaine_facturation', ligne)
            self.assertEqual(Decimal(str(ligne['prix'])), Decimal('1200'))
