"""FG265 — tests du flux d'irradiance/météo TMY (PVGIS, repli climatique).

Aucun accès réseau : on teste le parsing (``parse_tmy``) sur une charge utile
fabriquée et le REPLI hors-ligne (``fetch_irradiance_tmy`` avec urlopen patché
pour lever) — comme le client PVGIS existant, les tests ne dépendent jamais du
réseau.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_weather_feed -v 2
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.ventes import weather_feed as wf


def _fake_tmy_payload():
    """Charge utile PVGIS-TMY minimale : 1 point par mois, G(h) constant 500 W/m²."""
    hourly = []
    for month in range(1, 13):
        # Plusieurs heures par mois pour vérifier le cumul mensuel.
        for hour in range(3):
            hourly.append({
                'time(UTC)': f'2020{month:02d}15:{hour:02d}00',
                'G(h)': 500.0,
                'T2m': 20.0 + month,
            })
    return {'outputs': {'tmy_hourly': hourly}}


class ParseTmyTest(SimpleTestCase):
    def test_aggregates_hourly_into_monthly(self):
        res = wf.parse_tmy(_fake_tmy_payload())
        self.assertEqual(res['source'], 'pvgis')
        monthly = res['irradiance_mensuelle_kwh_m2']
        self.assertEqual(len(monthly), 12)
        # 3 h × 500 W/m² = 1500 Wh/m² = 1.5 kWh/m² par mois.
        for value in monthly:
            self.assertAlmostEqual(value, 1.5, places=2)
        self.assertAlmostEqual(res['irradiance_annuelle_kwh_m2'],
                               round(sum(monthly), 1), places=2)
        # Température moyenne renseignée et plausible.
        self.assertIsNotNone(res['temperature_moyenne_c'])
        self.assertTrue(20 < res['temperature_moyenne_c'] < 35)

    def test_unexpected_payload_raises(self):
        with self.assertRaises(ValueError):
            wf.parse_tmy({'outputs': {}})
        with self.assertRaises(ValueError):
            wf.parse_tmy({})

    def test_zero_irradiance_raises(self):
        payload = {'outputs': {'tmy_hourly': [
            {'time(UTC)': '20200115:0000', 'G(h)': 0.0, 'T2m': 18.0}]}}
        with self.assertRaises(ValueError):
            wf.parse_tmy(payload)


class FetchTmyFallbackTest(SimpleTestCase):
    def test_invalid_coords_falls_back_without_network(self):
        res = wf.fetch_irradiance_tmy('abc', None)
        self.assertEqual(res['source'], 'manual')
        self.assertEqual(len(res['irradiance_mensuelle_kwh_m2']), 12)
        self.assertGreater(res['irradiance_annuelle_kwh_m2'], 0)
        self.assertIn('coordonnées', res['reason'])

    def test_network_error_falls_back(self):
        with patch('apps.ventes.weather_feed.urllib.request.urlopen',
                   side_effect=OSError('réseau bloqué')):
            res = wf.fetch_irradiance_tmy(33.57, -7.59,
                                          annual_fallback_kwh_m2=2000.0)
        self.assertEqual(res['source'], 'manual')
        self.assertEqual(len(res['irradiance_mensuelle_kwh_m2']), 12)
        # Le repli ventile ~l'irradiation annuelle fournie.
        self.assertTrue(1800 < res['irradiance_annuelle_kwh_m2'] < 2200)
        self.assertIn('indisponible', res['reason'])

    def test_fallback_monthly_share_sums_to_annual(self):
        res = wf._manual_result(1900.0, 'test')
        self.assertAlmostEqual(
            sum(res['irradiance_mensuelle_kwh_m2']),
            res['irradiance_annuelle_kwh_m2'], places=1)
