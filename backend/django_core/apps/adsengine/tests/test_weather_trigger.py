"""PUB79 — Tests du déclencheur météo (canicule ⇒ angle pompage/climatisation).

Mocke ``apps.installations.weather.fetch_temperature_forecast`` (jamais un
vrai appel réseau) — prouve : chantier au-dessus du seuil → suggestion avec
la donnée météo citée (backlog, JAMAIS une action) ; sous le seuil → aucune
suggestion ; panne API → no-op silencieux ; chantier sans GPS/clôturé
ignoré (jamais un appel réseau inutile) ; endpoint gaté ``adsengine_view``.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.installations.models import Installation
from apps.roles.models import Role

from apps.adsengine import weather_trigger

User = get_user_model()
TRIGGER_URL = '/api/django/adsengine/reporting/creatifs/declencheur-meteo/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CaniculeBacklogSuggestionsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Weather Co', slug='weather-co')

    def _installation(self, *, ville='Marrakech', gps=True, statut=None):
        inst = Installation.objects.create(
            company=self.company, reference='CHT-WX-1', site_ville=ville,
            statut=statut or Installation.Statut.EN_COURS)
        if gps:
            inst.gps_lat = Decimal('31.629472')
            inst.gps_lng = Decimal('-7.981084')
            inst.save(update_fields=['gps_lat', 'gps_lng'])
        return inst

    def test_canicule_above_threshold_suggests_angle(self):
        self._installation()
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   return_value={'temperature_max_c': 42.0}):
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company)
        self.assertEqual(len(suggestions), 1)
        s = suggestions[0]
        self.assertEqual(
            s['angle'], weather_trigger.ANGLE_POMPAGE_CLIMATISATION)
        self.assertIn('Marrakech', s['suggestion_fr'])
        self.assertIn('42', s['suggestion_fr'])

    def test_below_threshold_no_suggestion(self):
        self._installation()
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   return_value={'temperature_max_c': 25.0}):
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company)
        self.assertEqual(suggestions, [])

    def test_api_failure_is_silent_noop(self):
        self._installation()
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   side_effect=Exception('API down')):
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company)
        self.assertEqual(suggestions, [])

    def test_installation_without_gps_ignored(self):
        self._installation(gps=False)
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   return_value={'temperature_max_c': 42.0}) as mocked:
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company)
        mocked.assert_not_called()
        self.assertEqual(suggestions, [])

    def test_closed_installation_excluded(self):
        self._installation(statut=Installation.Statut.CLOTURE)
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   return_value={'temperature_max_c': 42.0}) as mocked:
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company)
        mocked.assert_not_called()
        self.assertEqual(suggestions, [])

    def test_custom_threshold(self):
        self._installation()
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   return_value={'temperature_max_c': 33.0}):
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company, seuil_temp_c=30)
        self.assertEqual(len(suggestions), 1)

    def test_scoped_to_company(self):
        other = Company.objects.create(nom='Other Weather', slug='other-weather')
        Installation.objects.create(
            company=other, reference='CHT-OTHER',
            statut=Installation.Statut.EN_COURS,
            gps_lat=Decimal('1.0'), gps_lng=Decimal('1.0'))
        with patch('apps.installations.weather.fetch_temperature_forecast',
                   return_value={'temperature_max_c': 42.0}):
            suggestions = weather_trigger.canicule_backlog_suggestions(
                self.company)
        self.assertEqual(suggestions, [])


class WeatherTriggerEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='WxEp Co', slug='wxep-co')
        self.viewer = make_user(self.company, 'wx-viewer', ['adsengine_view'])

    def test_endpoint_returns_shape(self):
        resp = auth(self.viewer).get(TRIGGER_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('suggestions', resp.data)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'wx-nobody', [])
        self.assertEqual(auth(nobody).get(TRIGGER_URL).status_code, 403)
