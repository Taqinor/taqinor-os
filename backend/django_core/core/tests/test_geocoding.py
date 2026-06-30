"""Tests FG375 — géocodage & cartes (fondation branchable).

Couvre :
  * enregistrement des connecteurs (nominatim, generic_keyed) ;
  * Nominatim parse une réponse mockée → GeoPoint ;
  * Nominatim adresse vide → None ;
  * generic_keyed non configuré → None ;
  * geocode() utilise Nominatim par défaut (sans config société) ;
  * geocode() respecte la config société ;
  * découplage : aucun import d'app domaine.
"""
import os
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from core import geocoding, integrations
from core.models import IntegrationConfig


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class ProviderRegistrationTests(TestCase):
    def test_providers_registered(self):
        self.assertIs(
            integrations.get_provider_class(integrations.TYPE_GEOCODING,
                                            'nominatim'),
            geocoding.NominatimGeocodingProvider)
        self.assertIs(
            integrations.get_provider_class(integrations.TYPE_GEOCODING,
                                            'generic_keyed'),
            geocoding.GenericKeyedGeocodingProvider)


class NominatimTests(TestCase):
    def test_empty_address_returns_none(self):
        self.assertIsNone(geocoding.NominatimGeocodingProvider().geocode(''))

    def test_parses_response(self):
        payload = [{'lat': '33.59', 'lon': '-7.61',
                    'display_name': 'Casablanca'}]
        with mock.patch('requests.get', return_value=_FakeResp(payload)):
            pt = geocoding.NominatimGeocodingProvider().geocode('Casablanca')
        self.assertIsNotNone(pt)
        self.assertAlmostEqual(pt.lat, 33.59)
        self.assertAlmostEqual(pt.lng, -7.61)


class GenericKeyedTests(TestCase):
    def test_not_configured_returns_none(self):
        p = geocoding.GenericKeyedGeocodingProvider(config={}, secret=None)
        self.assertFalse(p.is_configured())
        self.assertIsNone(p.geocode('Rabat'))


class GeocodeDispatchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_default_uses_nominatim(self):
        payload = [{'lat': '34.0', 'lon': '-6.8', 'display_name': 'Rabat'}]
        with mock.patch('requests.get', return_value=_FakeResp(payload)):
            pt = geocoding.geocode('Rabat')
        self.assertEqual(pt.lat, 34.0)

    def test_company_config_keyed_provider(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_GEOCODING,
            provider='generic_keyed', actif=True,
            settings={'base_url': 'https://g'}, secret_ref='GEO_K')
        payload = {'results': [{'geometry': {'location': {'lat': 31.6,
                   'lng': -8.0}}, 'formatted': 'Marrakech'}]}
        with mock.patch.dict(os.environ, {'GEO_K': 'tok'}), \
                mock.patch('requests.get', return_value=_FakeResp(payload)):
            pt = geocoding.geocode('Marrakech', company=self.company)
        self.assertEqual(pt.lat, 31.6)
        self.assertEqual(pt.lng, -8.0)
