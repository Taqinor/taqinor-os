"""
XFSM21 — Météo sur le planning (travaux toiture).

Couvre :
  * `weather.fetch_forecast` / `evaluate_risk` (unitaire, HTTP mocké via
    `sys.modules` — jamais de vrai appel réseau) ;
  * panne API → None, jamais d'exception ;
  * la tâche Beat `meteo_planning_j3` cible les interventions POSE planifiées
    J+3, pose `meteo_risque`/`meteo_verifie_le`, ignore les interventions sans
    GPS chantier ;
  * isolation : une intervention d'un autre type/jour n'est jamais touchée.

Run :
    python manage.py test apps.installations.tests_xfsm21_meteo_planning -v2
"""
import itertools
import sys
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.installations import weather
from apps.installations.models import Installation, Intervention
from apps.installations.tasks import casablanca_today, meteo_planning_j3

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm21-co-{n}', defaults={'nom': nom or f'XFSM21 Co {n}'})
    return company


def _fake_requests_success(response_json):
    fake = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = response_json
    fake.get.return_value = mock_resp
    return fake


class TestFetchForecast(TestCase):
    def test_missing_gps_returns_none(self):
        self.assertIsNone(weather.fetch_forecast(None, None, casablanca_today()))

    def test_success_returns_values(self):
        fake_requests = _fake_requests_success({
            'daily': {'precipitation_sum': [12.0], 'windgusts_10m_max': [15.0]}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = weather.fetch_forecast(33.57, -7.58, casablanca_today())
        self.assertEqual(result['precipitation_mm'], 12.0)
        self.assertEqual(result['windgusts_kmh'], 15.0)

    def test_network_error_returns_none(self):
        fake_requests = MagicMock()
        fake_requests.get.side_effect = Exception('timeout')
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = weather.fetch_forecast(33.57, -7.58, casablanca_today())
        self.assertIsNone(result)

    def test_empty_daily_returns_none(self):
        fake_requests = _fake_requests_success({'daily': {}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = weather.fetch_forecast(33.57, -7.58, casablanca_today())
        self.assertIsNone(result)


class TestEvaluateRisk(TestCase):
    def test_none_forecast_returns_none(self):
        self.assertIsNone(weather.evaluate_risk(None))

    def test_rain_over_threshold_is_risky(self):
        self.assertTrue(weather.evaluate_risk(
            {'precipitation_mm': 10, 'windgusts_kmh': 5}))

    def test_wind_over_threshold_is_risky(self):
        self.assertTrue(weather.evaluate_risk(
            {'precipitation_mm': 0, 'windgusts_kmh': 60}))

    def test_below_both_thresholds_not_risky(self):
        self.assertFalse(weather.evaluate_risk(
            {'precipitation_mm': 1, 'windgusts_kmh': 10}))


class TestMeteoPlanningJ3Task(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XFSM21',
            email=f'xfsm21-{next(_seq)}@example.invalid')
        self.jour_cible = casablanca_today() + timedelta(days=3)

    def _make_inst(self, with_gps=True):
        n = next(_seq)
        inst = Installation.objects.create(
            company=self.company, reference=f'CHT-XFSM21-{n}',
            client=self.client_obj)
        if with_gps:
            inst.gps_lat = Decimal('33.573110')
            inst.gps_lng = Decimal('-7.589843')
            inst.save(update_fields=['gps_lat', 'gps_lng'])
        return inst

    def test_pose_targeted_and_flagged_risky(self):
        inst = self._make_inst()
        interv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            date_prevue=self.jour_cible)
        fake_requests = _fake_requests_success({
            'daily': {'precipitation_sum': [20.0], 'windgusts_10m_max': [10.0]}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = meteo_planning_j3()
        self.assertEqual(result['cibles'], 1)
        self.assertEqual(result['evaluees'], 1)
        self.assertEqual(result['a_risque'], 1)
        interv.refresh_from_db()
        self.assertTrue(interv.meteo_risque)
        self.assertIsNotNone(interv.meteo_verifie_le)

    def test_non_pose_type_ignored(self):
        inst = self._make_inst()
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.CONTROLE,
            date_prevue=self.jour_cible)
        fake_requests = _fake_requests_success({
            'daily': {'precipitation_sum': [20.0], 'windgusts_10m_max': [10.0]}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = meteo_planning_j3()
        self.assertEqual(result['cibles'], 0)

    def test_wrong_day_ignored(self):
        inst = self._make_inst()
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            date_prevue=self.jour_cible + timedelta(days=1))
        fake_requests = _fake_requests_success({
            'daily': {'precipitation_sum': [20.0], 'windgusts_10m_max': [10.0]}})
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = meteo_planning_j3()
        self.assertEqual(result['cibles'], 0)

    def test_api_failure_is_silent_noop(self):
        inst = self._make_inst()
        interv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            date_prevue=self.jour_cible)
        fake_requests = MagicMock()
        fake_requests.get.side_effect = Exception('API down')
        with patch.dict(sys.modules, {'requests': fake_requests}):
            result = meteo_planning_j3()
        self.assertEqual(result['cibles'], 1)
        self.assertEqual(result['evaluees'], 0)
        interv.refresh_from_db()
        self.assertIsNone(interv.meteo_risque)

    def test_no_gps_no_crash(self):
        inst = self._make_inst(with_gps=False)
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            date_prevue=self.jour_cible)
        result = meteo_planning_j3()
        self.assertEqual(result['cibles'], 1)
        self.assertEqual(result['evaluees'], 0)
