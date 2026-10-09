"""ASAV67 — les paramètres de requête du monitoring sont validés par UN
helper : toute saisie invalide donne 400 sous le nom du paramètre, jamais 500.

Run :
    python manage.py test apps.monitoring.tests_asav67_parametres -v2
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import (
    MonitoringConfig, ProductionReading, ProductionWarranty,
)
from apps.monitoring.report_carbon import (
    build_carbon_report_data_client, build_carbon_report_data_site,
)
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/monitoring'


class ParametresRequeteTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav67-co', defaults={'nom': 'ASAV67 Co'})
        user = User.objects.create_user(
            username='asav67_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient(raise_request_exception=False)
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV67')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV67',
            client=self.client_obj, puissance_installee_kwc=Decimal('5.00'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst,
            expected_annual_kwh=Decimal('6000'))
        self.garantie = ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('6000'),
            degradation_pct_per_year=Decimal('0.5'), start_year=2024)
        self.today = timezone.localdate()
        for jour, kwh in ((date(2026, 1, 15), 100), (date(2026, 6, 15), 100),
                          (date(2026, 11, 15), 100)):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                energy_kwh=Decimal(kwh), period_days=1)

    def _get(self, url):
        return self.api.get(f'{BASE}/{url}')

    def _400(self, url, parametre):
        r = self._get(url)
        self.assertEqual(r.status_code, 400, (url, r.content[:200]))
        self.assertIn(parametre, r.data, (url, r.data))

    def test_history_months(self):
        cid = self.config.pk
        self._400(f'configs/{cid}/history/?months=abc', 'months')

    def test_fenetres(self):
        cid = self.config.pk
        for action in (f'configs/{cid}/om-metrics/', f'configs/{cid}/soiling/',
                       'configs/fleet/', 'configs/benchmark/'):
            self._400(f'{action}?window_days=x', 'window_days')
            self._400(f'{action}?window_days=', 'window_days')

    def test_client(self):
        self._400('configs/client-portal/?client=abc', 'client')

    def test_dates(self):
        cid = self.config.pk
        for action in (f'configs/{cid}/co2/', 'configs/co2-fleet/',
                       f'configs/{cid}/attestation-carbone-pdf/'):
            self._400(f'{action}?since=pas-une-date', 'since')
            self._400(f'{action}?since=2026-13-45', 'since')

    def test_garantie(self):
        gid = self.garantie.pk
        self._400(f'warranties/{gid}/status/?year=abc', 'year')
        self._400(f'warranties/{gid}/curve/?years=abc', 'years')
        self._400(f'warranties/{gid}/curve/?drift_threshold_pct=abc',
                  'drift_threshold_pct')

    def test_filtres_installation(self):
        self._400('readings/?installation=abc', 'installation')
        self._400('cleanings/?installation=abc', 'installation')

    def test_valeurs_valides_200(self):
        cid = self.config.pk
        for url in (f'configs/{cid}/history/?months=6',
                    f'configs/{cid}/om-metrics/?window_days=90',
                    'configs/fleet/', f'configs/{cid}/co2/?since=2026-01-01',
                    f'warranties/{self.garantie.pk}/status/?year=2026'):
            self.assertEqual(self._get(url).status_code, 200, url)

    def test_attestation_bornee(self):
        data = build_carbon_report_data_site(
            self.inst, since=date(2026, 6, 1), until=date(2026, 6, 30))
        self.assertEqual(data['production_kwh'], Decimal('100.00'))
        with mock.patch('apps.monitoring.report_carbon.render_pdf',
                        return_value=b'%PDF-1.4'):
            r = self._get(
                f'configs/{self.config.pk}/attestation-carbone-pdf/'
                '?since=2026-06-01&until=2026-06-30')
        self.assertEqual(r.status_code, 200)

    def test_attestation_client_bornee(self):
        total = build_carbon_report_data_client(
            self.company, self.client_obj.pk)
        borne = build_carbon_report_data_client(
            self.company, self.client_obj.pk, since=date(2026, 6, 1),
            until=date(2026, 6, 30))
        self.assertEqual(total['production_kwh'], Decimal('300.00'))
        self.assertEqual(borne['production_kwh'], Decimal('100.00'))
        with mock.patch('apps.monitoring.report_carbon.render_pdf',
                        return_value=b'%PDF-1.4'):
            r = self._get(
                'configs/attestation-carbone-client-pdf/'
                f'?client={self.client_obj.pk}&since=2026-06-01'
                '&until=2026-06-30')
        self.assertEqual(r.status_code, 200)
