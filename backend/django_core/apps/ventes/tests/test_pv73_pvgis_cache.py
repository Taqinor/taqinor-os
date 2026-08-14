"""PV73 — cache PVGIS SYSTÈME (core/cache, company=None) : productible 6 h, TMY 7 j.

Vérifie : un 2e appel sur le MÊME plan (mêmes coordonnées/tilt/azimut) ne
retouche JAMAIS les fetchers réseau (compte d'appels mock à zéro) ;
`force_refresh=True` bypasse la lecture et refetch ; le cache est bien
SYSTÈME (partagé entre sociétés, jamais scopé par tenant) — la physique d'un
point GPS ne dépend pas de qui consulte.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.test import TestCase

from apps.ventes.etude import (
    _company_settings,
    _fetch_productible,
    _fetch_tmy,
    run_bankable_study,
)
from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)

User = get_user_model()


def _fake_productible(settings, lat, lon, *, peakpower_kwc=1.0, tilt=None, azimuth=None):
    return {
        'source': 'pvgis',
        'productible_kwh_kwc': 1700.0,
        'production_mensuelle_kwh_kwc': None,
        'reason': None,
    }


def _fake_tmy(lat, lon):
    return {
        'source': 'pvgis',
        'irradiance_annuelle_kwh_m2': 2000.0,
        'irradiance_mensuelle_kwh_m2': [120.0] * 12,
        'temperature_moyenne_c': 19.0,
        'reason': None,
    }


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
class TestPV73PvgisCache(TestCase):
    def setUp(self):
        # LocMemCache sous les tests (isolé par process) — mais PERSISTE entre
        # méthodes de test : on repart d'un cache vide à chaque fois.
        django_cache.clear()
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '20', '1500'),
        ], reference='DEV-PV73-0001')

    def _zone(self):
        return {'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
                'tilt': 30, 'azimuth': 0, 'kwc': 10.0}

    def test_second_call_same_plan_hits_cache(self, mock_prod, mock_tmy):
        run_bankable_study(self.devis, zones=[self._zone()])
        self.assertEqual(mock_prod.call_count, 1)
        self.assertEqual(mock_tmy.call_count, 1)

        run_bankable_study(self.devis, zones=[self._zone()])
        # Zéro appel fetcher supplémentaire — servi par le cache système.
        self.assertEqual(mock_prod.call_count, 1)
        self.assertEqual(mock_tmy.call_count, 1)

    def test_force_refresh_bypasses_cache_and_refetches(self, mock_prod, mock_tmy):
        run_bankable_study(self.devis, zones=[self._zone()])
        self.assertEqual(mock_prod.call_count, 1)
        self.assertEqual(mock_tmy.call_count, 1)

        run_bankable_study(
            self.devis, zones=[self._zone()], force_refresh=True)
        self.assertEqual(mock_prod.call_count, 2)
        self.assertEqual(mock_tmy.call_count, 2)

        # Le cache est réécrit malgré force_refresh : l'appel SUIVANT normal
        # retombe sur l'entrée fraîche, pas de nouveau fetch.
        run_bankable_study(self.devis, zones=[self._zone()])
        self.assertEqual(mock_prod.call_count, 2)
        self.assertEqual(mock_tmy.call_count, 2)

    def test_cache_is_system_scoped_shared_across_companies(self, mock_prod, mock_tmy):
        other_company = make_company()
        other_user = User.objects.create_user(
            username='test_pv73_user2', password='x', role_legacy='responsable',
            company=other_company,
        )
        other_client = make_client(other_company)
        other_devis = make_devis(other_company, other_user, other_client, [
            ('Panneau mono 450W', '20', '1500'),
        ], reference='DEV-PV73-OTHER')

        run_bankable_study(self.devis, zones=[self._zone()])
        self.assertEqual(mock_prod.call_count, 1)
        self.assertEqual(mock_tmy.call_count, 1)

        # Autre société, MÊME plan GPS/tilt/azimut : le cache SYSTÈME (jamais
        # scopé par tenant) sert la réponse — zéro nouveau fetch.
        run_bankable_study(other_devis, zones=[self._zone()])
        self.assertEqual(mock_prod.call_count, 1)
        self.assertEqual(mock_tmy.call_count, 1)

    def test_direct_fetch_helpers_write_system_scope_key(self, mock_prod, mock_tmy):
        from core import cache as tenant_cache

        settings = _company_settings(self.devis)
        _fetch_productible(settings, 33.57, -7.59, tilt=30, azimuth=0)
        key = 'pvgis:prod:33.570:-7.590:30:0'
        self.assertIsNotNone(tenant_cache.get(None, key))
        # Jamais peuplée sous la clé scopée société (le point GPS n'appartient
        # à aucun tenant en particulier).
        self.assertIsNone(tenant_cache.get(self.company.id, key))

        _fetch_tmy(33.57, -7.59)
        tmy_key = 'pvgis:tmy:33.570:-7.590'
        self.assertIsNotNone(tenant_cache.get(None, tmy_key))
