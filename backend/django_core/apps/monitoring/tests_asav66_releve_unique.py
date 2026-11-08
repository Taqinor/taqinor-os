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

    def test_double_post_409(self):
        # ERR-ENF11-FUZZ-MONITORING — relevé déjà saisi = ÉTAT des données : 409.
        self.assertEqual(self._post().status_code, 201)
        r = self._post()
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('date', r.data)
        self.assertEqual(self._nb(), 1)

    def test_periode_zero_400(self):
        r = self._post(period_days=0)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('period_days', r.data)

    def test_date_future_409(self):
        # La date dépend de l'horloge : le schéma ne peut la dire -> 409.
        r = self._post(date=(self.today + timedelta(days=400)).isoformat())
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('date', r.data)
        self.assertEqual(self._nb(), 0)

    def test_manuel_apres_csv_409(self):
        # AMON1 — réaligné sur la période de l'écran (30 j) : un journalier
        # importé à J−35 est recouvert par une saisie J−40 sur 30 jours.
        jour = self.today - timedelta(days=35)
        csv = f'date;periode_jours;energie_kwh\n{jour.isoformat()};1;30\n'
        r = self.api.post(
            f'/api/django/monitoring/configs/{self.config.pk}/import-releves/',
            {'csv': csv}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = self._post(date=(self.today - timedelta(days=40)).isoformat(),
                       period_days=30)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(self._nb(), 1)

    def test_releve_chevauchant_409(self):
        """AMON1 — recouvrement refusé à la saisie, au PATCH et au CSV ;
        contigu accepté ; doublon exact compté en `doublons`."""
        from datetime import date

        from apps.monitoring.selectors import co2_for_installation
        r = self._post(date='2026-09-01', period_days=30, energy_kwh='450')
        self.assertEqual(r.status_code, 201, r.content)
        r = self._post(date='2026-09-15', period_days=30, energy_kwh='450')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data['date'],
                         ['Ce relevé recouvre celui du 01/09/2026 (30 j).'])
        octobre = self._post(date='2026-10-01', period_days=30,
                             energy_kwh='450')
        self.assertEqual(octobre.status_code, 201, octobre.content)
        r = self.api.patch(
            f'/api/django/monitoring/readings/{octobre.data["id"]}/',
            {'date': '2026-09-20'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        lignes = ['date;periode_jours;energie_kwh', '2026-09-01;30;450']
        lignes += [f'2026-09-{j:02d};1;15' for j in range(2, 4)]
        r = self.api.post(
            f'/api/django/monitoring/configs/{self.config.pk}/import-releves/',
            {'csv': '\n'.join(lignes)}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data['crees'], r.data['doublons']), (0, 1))
        self.assertEqual(len(r.data['erreurs']), 2)
        self.assertEqual(self._nb(), 2)
        co2 = co2_for_installation(
            self.inst, since=date(2026, 9, 1), until=date(2026, 9, 30))
        self.assertEqual(Decimal(str(co2['production_kwh'])), Decimal('450'))

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
