"""PV69 — `run_bankable_study` v1 : productible PVGIS par zone → PR → P50/P90/P75.

Les deux fetchers réseau (`apps.parametres.pvgis.fetch_productible` et
`apps.ventes.weather_feed.fetch_irradiance_tmy`) sont monkeypatchés : ces
tests ne touchent JAMAIS le réseau (règle offline-safe héritée des deux
modules sources). On vérifie la conformité au sous-ensemble PV69 du contrat
PACT10 (`apps/ventes/contract_samples/simulation.json`) — clés `pr.*` — et
que les clés historiques d'`etude_params` (QX38) ne sont jamais touchées.
"""
import json
import os
from unittest import mock

from django.test import TestCase

from apps.ventes.etude import run_bankable_study
from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)

_CONTRACT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'contract_samples', 'simulation.json')


def _load_contract():
    with open(_CONTRACT_PATH, encoding='utf-8') as fh:
        return json.load(fh)['exemple']['simulation']


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


def _fake_productible_manual(settings, lat, lon, *, peakpower_kwc=1.0, tilt=None, azimuth=None):
    return {
        'source': 'manual',
        'productible_kwh_kwc': 1500.0,
        'production_mensuelle_kwh_kwc': None,
        'reason': 'PVGIS indisponible (URLError)',
    }


class TestPV69RunBankableStudy(TestCase):
    def setUp(self):
        # PV73 a mis un cache SYSTÈME devant les deux fetchers : il vit dans le
        # PROCESSUS, pas dans la transaction de test. Sans ce vidage, le premier
        # test remplit le cache avec un productible « pvgis » et le suivant —
        # qui monkeypatche pourtant le fetcher en repli « manual » — reçoit
        # l'entrée en cache : le mock n'est jamais appelé et le repli n'est
        # jamais testé. C'est l'isolation du fixture, pas une garde affaiblie.
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '20', '1500'),
        ], reference='DEV-PV69-0001')

    def _zones(self):
        return [
            {'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
             'tilt': 30, 'azimuth': 0, 'kwc': 10.0},
        ]

    @mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
    @mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
    def test_schema_matches_contract_pr_subset(self, mock_prod, mock_tmy):
        result = run_bankable_study(self.devis, zones=self._zones())
        contract = _load_contract()

        # PACT10/PACT13 — les clés de premier niveau sont comparées AU FICHIER
        # de contrat, jamais à une liste retapée : la liste retapée ici tenait
        # encore la v1 à six clés et ignorait les blocs ajoutés depuis
        # (autoconsommation, injection, puissance souscrite, dégradation,
        # projection 25 ans), c'est-à-dire une deuxième source de vérité.
        self.assertEqual(set(result.keys()), set(contract.keys()))
        self.assertEqual(result['version'], 1)
        self.assertEqual(result['source'], 'pvgis')
        self.assertEqual(set(result['pr'].keys()), set(contract['pr'].keys()))
        self.assertEqual(
            set(result['pr']['loss_breakdown'].keys()),
            set(contract['pr']['loss_breakdown'].keys()))
        zone_out = result['zones'][0]
        self.assertEqual(set(zone_out.keys()), set(contract['zones'][0].keys()))
        # 10 kWc x 1700 kWh/kWc = 17000 kWh de base.
        self.assertEqual(zone_out['base_production_kwh'], 17000.0)
        self.assertGreater(result['pr']['p50_kwh'], 0)
        self.assertGreaterEqual(result['pr']['p90_kwh'], 0)
        self.assertLessEqual(result['pr']['p90_kwh'], result['pr']['p50_kwh'])
        mock_prod.assert_called()
        mock_tmy.assert_called()

    @mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
    @mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible_manual)
    def test_manual_fallback_propagates_source_and_warning(self, mock_prod, mock_tmy):
        result = run_bankable_study(self.devis, zones=self._zones())
        self.assertEqual(result['source'], 'manual')
        self.assertTrue(any('dégradée' in w for w in result['warnings']))

    @mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
    @mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
    def test_historic_etude_params_keys_untouched(self, mock_prod, mock_tmy):
        # Le devis porte déjà les clés historiques QX38 — l'étude ne les lit
        # ni ne les écrit (pure orchestration, aucun devis.save()).
        self.devis.etude_params = {
            'production_annuelle': 12345, 'economies_annuelles': 6789,
            'payback': 7,
        }
        self.devis.save(update_fields=['etude_params'])
        before = dict(self.devis.etude_params)

        run_bankable_study(self.devis, zones=self._zones())

        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params, before)

    @mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
    @mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
    def test_empty_zones_never_raises(self, mock_prod, mock_tmy):
        result = run_bankable_study(self.devis, zones=[])
        self.assertEqual(result['zones'], [])
        self.assertEqual(result['pr']['p50_kwh'], 0.0)
        self.assertTrue(any('aucune zone' in w for w in result['warnings']))

    @mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
    @mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
    def test_computed_at_is_deterministic_when_passed(self, mock_prod, mock_tmy):
        import datetime
        fixed = datetime.datetime(2026, 8, 14, 10, 0, 0, tzinfo=datetime.timezone.utc)
        result = run_bankable_study(
            self.devis, zones=self._zones(), computed_at=fixed)
        self.assertEqual(result['computed_at'], '2026-08-14T10:00:00Z')
