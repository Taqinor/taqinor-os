"""PV70 — multi-zones + pont matrice d'ombrage 12×24 (shadingUi.ts, WJ19/WJ21).

Vérifie : (1) la matrice réelle donne une perte PONDÉRÉE PRODUCTION nettement
différente d'une moyenne PLATE sur un fixture ombragé le soir (heures creuses
côté production) ; (2) le repli `shading_analysis` (horizon/obstacles) et le
repli « aucun ombrage » ; (3) la lecture tolérante de la matrice depuis
`Devis.roof_layout` (par zone puis globale) quand l'appelant n'en passe
aucune ; (4) `production_horaire_zone` tuile 288 points et respecte le dérate.

Les deux fetchers réseau restent monkeypatchés (offline-safe, hérité de PV69).
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.etude import (
    _weighted_shading_loss_pct,
    _zone_production_weights,
    production_horaire_zone,
    run_bankable_study,
)
from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)


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


def _evening_shaded_matrix():
    """12×24 : heures 18-23 totalement masquées (0), le reste plein soleil (1)."""
    row = [1.0] * 24
    for h in range(18, 24):
        row[h] = 0.0
    return [list(row) for _ in range(12)]


def _flat_mean_loss_pct(matrix):
    cells = [1.0 - v for row in matrix for v in row]
    return round(sum(cells) / len(cells) * 100.0, 2)


_PATCH_TMY = mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy', side_effect=_fake_tmy)
_PATCH_PROD = mock.patch('apps.parametres.pvgis.fetch_productible', side_effect=_fake_productible)


class TestPV70WeightedShadingVsFlat(TestCase):
    def test_weighted_mean_differs_sharply_from_flat_mean_on_evening_fixture(self):
        matrix = _evening_shaded_matrix()
        flat = _flat_mean_loss_pct(matrix)
        # 6 h/24 masquées chaque mois → moyenne plate = 25 %.
        self.assertAlmostEqual(flat, 25.0, places=1)

        weights = _zone_production_weights([1.0 / 12.0] * 12)
        weighted = _weighted_shading_loss_pct(matrix, weights)
        # Les heures 18-23 pèsent très peu dans la forme ciel clair (aube/soir)
        # → la perte pondérée doit être NETTEMENT sous la moyenne plate.
        self.assertLess(weighted, flat / 3.0)


@_PATCH_TMY
@_PATCH_PROD
class TestPV70RunBankableStudyShading(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '20', '1500'),
        ], reference='DEV-PV70-0001')

    def _zone(self, **overrides):
        zone = {'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59,
                'tilt': 30, 'azimuth': 0, 'kwc': 10.0}
        zone.update(overrides)
        return zone

    def test_inline_matrix_drives_zone_and_aggregate_shading(self, mock_prod, mock_tmy):
        zone = self._zone(shading12x24=_evening_shaded_matrix())
        result = run_bankable_study(self.devis, zones=[zone])
        zone_out = result['zones'][0]
        self.assertGreater(zone_out['shading_annual_loss_pct'], 0.0)
        self.assertLess(zone_out['shading_annual_loss_pct'], 10.0)
        # Le poste agrégé 'shading' du pr.loss_breakdown doit refléter cette perte.
        self.assertGreater(result['pr']['loss_breakdown']['shading'], 0.0)

    def test_no_matrix_no_obstacles_means_zero_shading(self, mock_prod, mock_tmy):
        result = run_bankable_study(self.devis, zones=[self._zone()])
        self.assertEqual(result['zones'][0]['shading_annual_loss_pct'], 0.0)
        self.assertEqual(result['pr']['loss_breakdown']['shading'], 0.0)

    def test_horizon_fallback_used_when_no_matrix(self, mock_prod, mock_tmy):
        zone = self._zone(horizon_profile=[{'azimuth': 180, 'elevation': 30}])
        result = run_bankable_study(self.devis, zones=[zone])
        self.assertGreater(result['zones'][0]['shading_annual_loss_pct'], 0.0)

    def test_matrix_read_from_roof_layout_per_zone(self, mock_prod, mock_tmy):
        self.devis.roof_layout = {
            'zones': [{'label': 'Pan Sud', 'shading12x24': _evening_shaded_matrix()}],
        }
        self.devis.save(update_fields=['roof_layout'])
        result = run_bankable_study(self.devis, zones=[self._zone()])
        self.assertGreater(result['zones'][0]['shading_annual_loss_pct'], 0.0)

    def test_matrix_read_from_roof_layout_global_fallback(self, mock_prod, mock_tmy):
        self.devis.roof_layout = {'shading12x24': _evening_shaded_matrix()}
        self.devis.save(update_fields=['roof_layout'])
        result = run_bankable_study(self.devis, zones=[self._zone()])
        self.assertGreater(result['zones'][0]['shading_annual_loss_pct'], 0.0)

    def test_malformed_matrix_never_raises_and_falls_back(self, mock_prod, mock_tmy):
        zone = self._zone(shading12x24=[[1.0, 2.0]])  # forme invalide (pas 12x24)
        result = run_bankable_study(self.devis, zones=[zone])
        self.assertEqual(result['zones'][0]['shading_annual_loss_pct'], 0.0)

    def test_multi_zone_aggregate_is_production_weighted(self, mock_prod, mock_tmy):
        # Petit pan très ombragé + grand pan sans ombrage : l'agrégat doit
        # rester proche de 0, pas de la moyenne simple des deux zones.
        small_shaded = self._zone(
            label='Petit', kwc=1.0, shading12x24=[[0.0] * 24 for _ in range(12)])
        big_clean = self._zone(label='Grand', kwc=20.0)
        result = run_bankable_study(self.devis, zones=[small_shaded, big_clean])
        self.assertLess(result['pr']['loss_breakdown']['shading'], 10.0)


@_PATCH_TMY
@_PATCH_PROD
class TestPV70ProductionHoraireZone(TestCase):
    def test_zero_base_production_returns_288_zeros(self, mock_prod, mock_tmy):
        curve = production_horaire_zone({'base_production_kwh': 0.0})
        self.assertEqual(len(curve), 288)
        self.assertTrue(all(v == 0.0 for v in curve))

    def test_curve_sums_close_to_base_production_without_matrix(self, mock_prod, mock_tmy):
        curve = production_horaire_zone({'base_production_kwh': 12000.0})
        self.assertEqual(len(curve), 288)
        self.assertAlmostEqual(sum(curve), 12000.0, delta=1.0)

    def test_matrix_derates_masked_hours_to_zero(self, mock_prod, mock_tmy):
        matrix = _evening_shaded_matrix()
        curve = production_horaire_zone({'base_production_kwh': 12000.0}, matrix)
        # Heure 20 (masquée) de chaque mois doit être nulle.
        for m in range(12):
            self.assertEqual(curve[m * 24 + 20], 0.0)
        self.assertLess(sum(curve), 12000.0)
