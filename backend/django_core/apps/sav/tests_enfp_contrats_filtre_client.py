"""ENFP (D1) — ``?client=`` est déclaré ET honoré sur la liste des contrats."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance

User = get_user_model()


class ContratsFiltreClientTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-enfp-client', defaults={'nom': 'Sav Co ENFP'})
        self.admin = User.objects.create_user(
            username='enfp_sav_admin', password='x', role_legacy='admin',
            company=self.company)
        self.c1 = Client.objects.create(
            company=self.company, nom='Un', prenom='ENFP',
            email='enfp-un@example.invalid')
        self.c2 = Client.objects.create(
            company=self.company, nom='Deux', prenom='ENFP',
            email='enfp-deux@example.invalid')
        for c in (self.c1, self.c2):
            ContratMaintenance.objects.create(
                company=self.company, client=c, date_debut=date(2026, 1, 1),
                actif=True)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _ids(self, resp):
        data = resp.json()
        rows = data.get('results', data) if isinstance(data, dict) else data
        return sorted(r['client'] for r in rows)

    def test_filtre_client(self):
        r = self.api.get('/api/django/sav/contrats-maintenance/',
                         {'client': self.c1.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._ids(r), [self.c1.id])

    def test_client_invalide_ignore(self):
        r = self.api.get('/api/django/sav/contrats-maintenance/',
                         {'client': 'abc'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self._ids(r)), 2)
