"""ASAV66 — saisie manuelle d'un relevé : un seul relevé par (système, date,
période) toutes sources, période ≥ 1 jour, pas de date future ; l'import CSV
ré-évalue la sous-performance.

Run :
    python manage.py test apps.monitoring.tests_asav66_releve_unique -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import (
    MonitoringConfig, MonitoringSettings, ProductionReading,
    UnderperformanceFlag,
)
from authentication.models import Company

User = get_user_model()


class ReleveUniqueTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav66-co', defaults={'nom': 'ASAV66 Co'})
        user = User.objects.create_user(
            username='asav66_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV66')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV66', client=client,
            puissance_installee_kwc=Decimal('5.00'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        self.today = timezone.localdate()

    def _post(self, **corps):
        base = {'installation': self.inst.pk,
                'date': self.today.isoformat(), 'period_days': 1,
                'energy_kwh': '30'}
        base.update(corps)
        return self.api.post('/api/django/monitoring/readings/', base,
                             format='json')

    def _nb(self):
        return ProductionReading.objects.filter(installation=self.inst).count()

    def test_double_post_400(self):
        self.assertEqual(self._post().status_code, 201)
        r = self._post()
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('date', r.data)
        self.assertEqual(self._nb(), 1)

    def test_periode_zero_400(self):
        r = self._post(period_days=0)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('period_days', r.data)

    def test_date_future_400(self):
        r = self._post(date=(self.today + timedelta(days=400)).isoformat())
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('date', r.data)
        self.assertEqual(self._nb(), 0)

    def test_manuel_apres_csv_400(self):
        jour = self.today - timedelta(days=5)
        csv = f'date;periode_jours;energie_kwh\n{jour.isoformat()};1;30\n'
        r = self.api.post(
            f'/api/django/monitoring/configs/{self.config.pk}/import-releves/',
            {'csv': csv}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = self._post(date=jour.isoformat())
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self._nb(), 1)

    def test_import_reevalue(self):
        reglages = MonitoringSettings.get(self.company)
        reglages.save()
        lignes = ['date;periode_jours;energie_kwh']
        for i in range(10):
            jour = self.today - timedelta(days=i)
            lignes.append(f'{jour.isoformat()};1;5')
        r = self.api.post(
            f'/api/django/monitoring/configs/{self.config.pk}/import-releves/',
            {'csv': '\n'.join(lignes)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            UnderperformanceFlag.objects.filter(
                installation=self.inst, is_open=True).count(), 1)
