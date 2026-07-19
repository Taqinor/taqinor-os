"""PUB79 — Tests de l'extension météo (température / canicule) +
sélecteur de localisation des chantiers actifs.

Couvre :
  * ``weather.fetch_temperature_forecast`` (HTTP mocké via ``sys.modules``,
    jamais un vrai appel réseau) + panne API/daily vide → ``None`` ;
  * ``weather.evaluate_canicule`` (fonction PURE) ;
  * ``selectors.active_installation_locations`` : chantiers ACTIFS (hors
    ``CLOTURE``) avec GPS, ``site_ville`` reprise, chantier sans GPS absent.
"""
import datetime
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.installations import selectors, weather
from apps.installations.models import Installation


def _fake_requests_success(response_json):
    fake = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = response_json
    fake.get.return_value = mock_resp
    return fake


class FetchTemperatureForecastTests(TestCase):
    def test_missing_gps_returns_none(self):
        self.assertIsNone(weather.fetch_temperature_forecast(
            None, None, datetime.date.today()))

    def test_success_returns_temperature(self):
        fake_requests = _fake_requests_success(
            {'daily': {'temperature_2m_max': [41.5]}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = weather.fetch_temperature_forecast(
                33.57, -7.58, datetime.date(2026, 7, 20))
        self.assertEqual(result['temperature_max_c'], 41.5)

    def test_network_error_returns_none(self):
        fake_requests = MagicMock()
        fake_requests.get.side_effect = Exception('timeout')
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = weather.fetch_temperature_forecast(
                33.57, -7.58, datetime.date(2026, 7, 20))
        self.assertIsNone(result)

    def test_empty_daily_returns_none(self):
        fake_requests = _fake_requests_success({'daily': {}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = weather.fetch_temperature_forecast(
                33.57, -7.58, datetime.date(2026, 7, 20))
        self.assertIsNone(result)


class EvaluateCaniculeTests(SimpleTestCase):
    def test_none_forecast_returns_none(self):
        self.assertIsNone(weather.evaluate_canicule(None))

    def test_over_threshold_is_canicule(self):
        self.assertTrue(weather.evaluate_canicule({'temperature_max_c': 40}))

    def test_below_threshold_not_canicule(self):
        self.assertFalse(weather.evaluate_canicule({'temperature_max_c': 30}))

    def test_custom_threshold(self):
        self.assertTrue(weather.evaluate_canicule(
            {'temperature_max_c': 33}, seuil_temp_c=32))

    def test_missing_temperature_key_returns_none(self):
        self.assertIsNone(weather.evaluate_canicule({}))


class ActiveInstallationLocationsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Wx Sel Co', slug='wx-sel-co')

    def _installation(self, ref, *, ville='Casablanca', gps=True, statut=None):
        inst = Installation.objects.create(
            company=self.company, reference=ref, site_ville=ville,
            statut=statut or Installation.Statut.EN_COURS)
        if gps:
            inst.gps_lat = Decimal('33.573110')
            inst.gps_lng = Decimal('-7.589843')
            inst.save(update_fields=['gps_lat', 'gps_lng'])
        return inst

    def test_active_with_gps_included(self):
        self._installation('CHT-1', ville='Marrakech')
        rows = selectors.active_installation_locations(self.company)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ville'], 'Marrakech')
        self.assertIsNotNone(rows[0]['gps_lat'])

    def test_without_gps_excluded(self):
        self._installation('CHT-2', gps=False)
        rows = selectors.active_installation_locations(self.company)
        self.assertEqual(rows, [])

    def test_cloture_excluded(self):
        self._installation('CHT-3', statut=Installation.Statut.CLOTURE)
        rows = selectors.active_installation_locations(self.company)
        self.assertEqual(rows, [])

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Wx', slug='other-wx')
        Installation.objects.create(
            company=other, reference='CHT-OTHER',
            statut=Installation.Statut.EN_COURS,
            gps_lat=Decimal('1.0'), gps_lng=Decimal('1.0'))
        rows = selectors.active_installation_locations(self.company)
        self.assertEqual(rows, [])
