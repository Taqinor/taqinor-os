"""Tests FG361 — prévision de ventes / demande (séries temporelles).

Couvre la fonction pure :func:`core.forecast.forecast_series` :
  * normalisation de la série (dicts, tuples, ``date``, dédoublonnage/somme,
    valeurs/périodes invalides ignorées, tri croissant) ;
  * prévision avec tendance haussière / baissière / plate ;
  * horizon, passage d'année, bornage à >= 0 ;
  * chemin de REPLI pur Python forcé (statsmodels absent) — garantit que les
    tests ne dépendent pas de l'installation de statsmodels.
"""
from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from core import forecast as fc
from core.forecast import ForecastResult, forecast_series


class NormalizeSeriesTests(SimpleTestCase):
    def test_accepts_dicts_and_sorts(self):
        points = [
            {'period': '2026-03', 'value': 30},
            {'period': '2026-01', 'value': 10},
            {'period': '2026-02', 'value': 20},
        ]
        res = forecast_series(points, horizon=1)
        self.assertEqual([p for p, _ in res.history],
                         ['2026-01', '2026-02', '2026-03'])

    def test_accepts_tuples_and_date_objects(self):
        points = [
            (date(2026, 1, 15), 100),
            ('2026-02', 200),
        ]
        res = forecast_series(points, horizon=1)
        self.assertEqual(res.history,
                         [('2026-01', 100.0), ('2026-02', 200.0)])

    def test_sums_duplicate_months(self):
        points = [
            {'period': '2026-01', 'value': 10},
            {'period': '2026-01', 'value': 5},
        ]
        res = forecast_series(points, horizon=1)
        self.assertEqual(res.history, [('2026-01', 15.0)])

    def test_ignores_invalid_rows(self):
        points = [
            {'period': 'bad', 'value': 10},
            {'period': '2026-01', 'value': 'NaN-ish'},
            {'period': '2026-02', 'value': 50},
            {'period': '2026-03', 'value': 60},
        ]
        res = forecast_series(points, horizon=1)
        self.assertEqual([p for p, _ in res.history], ['2026-02', '2026-03'])


class ForecastMathTests(SimpleTestCase):
    """Force le repli pur Python (statsmodels indisponible) pour un résultat
    déterministe, indépendant de l'installation de statsmodels."""

    def setUp(self):
        patcher = mock.patch.object(fc, '_HAS_STATSMODELS', False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_empty_series(self):
        res = forecast_series([], horizon=6)
        self.assertIsInstance(res, ForecastResult)
        self.assertEqual(res.forecast, [])
        self.assertEqual(res.method, 'flat')

    def test_zero_horizon(self):
        res = forecast_series([{'period': '2026-01', 'value': 10}], horizon=0)
        self.assertEqual(res.forecast, [])

    def test_linear_upward_trend(self):
        points = [{'period': f'2026-{m:02d}', 'value': m * 10}
                  for m in range(1, 7)]  # 10,20,...,60
        res = forecast_series(points, horizon=3)
        self.assertEqual(res.method, 'linear-trend')
        self.assertGreater(res.trend_per_month, 0)
        vals = [p.value for p in res.forecast]
        # Tendance +10/mois → 70, 80, 90.
        self.assertEqual(vals, [70.0, 80.0, 90.0])

    def test_downward_trend_clamped_at_zero(self):
        points = [{'period': f'2026-{m:02d}', 'value': max(0, 50 - m * 10)}
                  for m in range(1, 6)]  # 40,30,20,10,0
        res = forecast_series(points, horizon=4)
        self.assertLess(res.trend_per_month, 0)
        # Aucune valeur prévue négative.
        self.assertTrue(all(p.value >= 0 for p in res.forecast))

    def test_flat_series_uses_moving_average(self):
        points = [{'period': f'2026-{m:02d}', 'value': 100}
                  for m in range(1, 6)]
        res = forecast_series(points, horizon=2)
        self.assertEqual(res.method, 'moving-average')
        self.assertEqual([p.value for p in res.forecast], [100.0, 100.0])

    def test_single_point_is_flat(self):
        res = forecast_series([{'period': '2026-01', 'value': 42}], horizon=2)
        self.assertEqual(res.method, 'flat')
        self.assertEqual([p.value for p in res.forecast], [42.0, 42.0])

    def test_periods_advance_across_year_boundary(self):
        points = [{'period': '2026-11', 'value': 10},
                  {'period': '2026-12', 'value': 20}]
        res = forecast_series(points, horizon=3)
        self.assertEqual([p.period for p in res.forecast],
                         ['2027-01', '2027-02', '2027-03'])


class StatsmodelsPathTests(SimpleTestCase):
    """Vérifie que le chemin statsmodels est emprunté quand disponible, et
    qu'un échec/absence retombe proprement sur le repli."""

    def test_falls_back_when_statsmodels_missing(self):
        points = [{'period': f'2026-{m:02d}', 'value': m * 10}
                  for m in range(1, 7)]
        with mock.patch.object(fc, '_HAS_STATSMODELS', False):
            res = forecast_series(points, horizon=2)
        self.assertIn(res.method, ('linear-trend', 'moving-average', 'flat'))

    def test_uses_holt_winters_when_available(self):
        points = [{'period': f'2026-{m:02d}', 'value': m * 10}
                  for m in range(1, 7)]
        fake_fit = mock.Mock()
        fake_fit.forecast.return_value = [70.0, 80.0]
        fake_model = mock.Mock()
        fake_model.fit.return_value = fake_fit
        with mock.patch.object(fc, '_HAS_STATSMODELS', True), \
                mock.patch.object(fc, '_ExpSmoothing',
                                  return_value=fake_model) as smoothing:
            res = forecast_series(points, horizon=2)
        self.assertTrue(smoothing.called)
        self.assertEqual(res.method, 'holt-winters')
        self.assertEqual([p.value for p in res.forecast], [70.0, 80.0])

    def test_holt_winters_nan_result_falls_back(self):
        points = [{'period': f'2026-{m:02d}', 'value': m * 10}
                  for m in range(1, 7)]
        fake_fit = mock.Mock()
        fake_fit.forecast.return_value = [float('nan'), float('nan')]
        fake_model = mock.Mock()
        fake_model.fit.return_value = fake_fit
        with mock.patch.object(fc, '_HAS_STATSMODELS', True), \
                mock.patch.object(fc, '_ExpSmoothing', return_value=fake_model):
            res = forecast_series(points, horizon=2)
        self.assertNotEqual(res.method, 'holt-winters')
