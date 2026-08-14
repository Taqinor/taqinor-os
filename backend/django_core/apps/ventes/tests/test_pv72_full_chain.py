"""PV72 — chaîne complète : autoconsommation → net-metering → puissance
souscrite (C&I) → dégradation → projection 25 ans (VAN/TRI).

Vérifie le schéma COMPLET (golden) contre le contrat PACT10
(`apps/ventes/contract_samples/simulation.json`), le gating C&I-only de
`subscribed_power`, le repli honnête (jamais un chiffre inventé) quand la
conso du lead est absente, la synthèse de charge 288 points vs un
`load_curve` explicite, et le câblage du toggle société
`surplus_injecte_compense` (loi 13-09) vers `net_metering_savings`.

Les deux fetchers réseau restent monkeypatchés (offline-safe, hérité de PV69).
"""
import json
import os
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.crm.models import Lead
from apps.parametres.models_tariff import TariffSettings
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


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)
class TestPV72FullChain(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference='DEV-PV72-0001', **fields):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '20', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference=reference)
        for k, v in fields.items():
            setattr(devis, k, v)
        if fields:
            devis.save()
        return devis

    def _zone(self, **overrides):
        zone = {'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
                'tilt': 30, 'azimuth': 0, 'kwc': 10.0}
        zone.update(overrides)
        return zone

    def test_full_schema_matches_contract_golden(self, mock_prod, mock_tmy):
        lead = Lead.objects.create(
            company=self.company, nom='Lead PV72',
            conso_mensuelle_kwh=Decimal('600'))
        devis = self._devis(lead=lead, mode_installation='residentiel')

        result = run_bankable_study(devis, zones=[self._zone()])
        contract = _load_contract()

        self.assertEqual(set(result.keys()), set(contract.keys()))
        for block_name in ('self_consumption', 'net_metering',
                           'subscribed_power', 'degradation', 'projection_25y'):
            self.assertEqual(
                set(result[block_name].keys()), set(contract[block_name].keys()),
                f"{block_name} : clés divergentes du contrat")

    def test_ci_mode_subscribed_power_has_computed_values(self, mock_prod, mock_tmy):
        devis = self._devis(
            mode_installation='commercial',
            etude_params={'puissance_souscrite_kva': 80})
        result = run_bankable_study(devis, zones=[self._zone()])
        sp = result['subscribed_power']
        self.assertIsNotNone(sp['peak_reduction_pct'])
        self.assertIsNotNone(sp['recommended_subscribed'])
        self.assertIsNotNone(sp['annual_saving'])

    def test_non_ci_mode_subscribed_power_is_minimal_honest_block(self, mock_prod, mock_tmy):
        devis = self._devis(mode_installation='residentiel')
        result = run_bankable_study(devis, zones=[self._zone()])
        sp = result['subscribed_power']
        self.assertIsNone(sp['peak_reduction_pct'])
        self.assertIsNone(sp['recommended_subscribed'])
        self.assertIsNone(sp['annual_saving'])

    def test_missing_lead_conso_yields_zero_self_consumption_and_warning(self, mock_prod, mock_tmy):
        devis = self._devis()  # aucun lead
        result = run_bankable_study(devis, zones=[self._zone()])
        self.assertEqual(result['self_consumption']['self_consumed_kwh'], 0.0)
        self.assertTrue(any(
            'consommation du lead non renseignée' in w
            for w in result['warnings']))

    def test_explicit_load_curve_skips_lead_synthesis(self, mock_prod, mock_tmy):
        devis = self._devis()  # aucun lead — mais load_curve fourni explicitement
        result = run_bankable_study(
            devis, zones=[self._zone()], load_curve=[5.0] * 24)
        self.assertFalse(any(
            'consommation du lead non renseignée' in w
            for w in result['warnings']))
        self.assertGreater(result['self_consumption']['hours'], 0)

    def test_surplus_compensation_toggle_wires_through_to_net_metering(self, mock_prod, mock_tmy):
        devis = self._devis()
        # OFF par défaut (TariffSettings.surplus_injecte_compense=False, 13-09).
        result_off = run_bankable_study(devis, zones=[self._zone()])
        self.assertTrue(any(
            "compensation de l'injection désactivée" in w
            for w in result_off['warnings']))
        self.assertEqual(result_off['net_metering']['annual_savings_mad'], 0.0)

        ts = TariffSettings.get(company=self.company)
        ts.surplus_injecte_compense = True
        ts.save()

        result_on = run_bankable_study(devis, zones=[self._zone()])
        self.assertFalse(any(
            "compensation de l'injection désactivée" in w
            for w in result_on['warnings']))

    def test_projection_uses_devis_total_ht_as_upfront_cost(self, mock_prod, mock_tmy):
        devis = self._devis()
        self.assertGreater(devis.total_ht, 0)
        result = run_bankable_study(devis, zones=[self._zone()])
        # Coût initial > 0 et aucune économie (pas de lead) → pas de retour sur
        # investissement atteint sur l'horizon (avertissement dédié).
        self.assertTrue(any(
            'retour sur investissement non atteint' in w
            for w in result['warnings']))
        self.assertIsNone(result['projection_25y']['payback_year'])
