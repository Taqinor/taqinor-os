"""Tests FG364 — prévision de réappro stock (fondation pure).

Couvre les fonctions pures de :mod:`core.stock_reorder` :
  * date de rupture = ``today + stock / conso journalière`` ;
  * quantité suggérée couvre ``lead_time + cycle`` au-delà du stock de sécurité ;
  * drapeau ``reorder_now`` quand le stock <= point de commande ;
  * garde-fou conso nulle/négative ⇒ pas de rupture, pas de suggestion ;
  * repli sans historique exploitable ;
  * estimation de la conso journalière depuis un historique de mouvements.

Aucune dépendance à Django/DB — fonctions pures (``SimpleTestCase``). ``today``
est passé en paramètre, donc les tests sont déterministes.
"""
from datetime import date

from django.test import SimpleTestCase

from core.stock_reorder import (
    DEFAULT_REVIEW_PERIOD_DAYS,
    ReorderResult,
    average_daily_consumption,
    predict_reorder,
)

TODAY = date(2026, 6, 1)


class RuptureDateTests(SimpleTestCase):
    def test_rupture_date_from_consumption_and_stock(self):
        # 100 en stock, 5/jour ⇒ rupture dans 20 jours.
        res = predict_reorder(
            current_stock=100,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=7,
            safety_stock=0,
        )
        self.assertIsInstance(res, ReorderResult)
        self.assertEqual(res.days_until_rupture, 20.0)
        self.assertEqual(res.rupture_date, date(2026, 6, 21))
        self.assertFalse(res.used_fallback)

    def test_more_stock_pushes_rupture_later(self):
        low = predict_reorder(
            current_stock=50, today=TODAY, avg_daily_consumption=5.0,
        ).days_until_rupture
        high = predict_reorder(
            current_stock=150, today=TODAY, avg_daily_consumption=5.0,
        ).days_until_rupture
        self.assertGreater(high, low)

    def test_higher_consumption_brings_rupture_sooner(self):
        slow = predict_reorder(
            current_stock=100, today=TODAY, avg_daily_consumption=2.0,
        ).days_until_rupture
        fast = predict_reorder(
            current_stock=100, today=TODAY, avg_daily_consumption=10.0,
        ).days_until_rupture
        self.assertLess(fast, slow)

    def test_zero_or_negative_stock_ruptures_today(self):
        res = predict_reorder(
            current_stock=0, today=TODAY, avg_daily_consumption=5.0,
        )
        self.assertEqual(res.days_until_rupture, 0.0)
        self.assertEqual(res.rupture_date, TODAY)


class SuggestedQuantityTests(SimpleTestCase):
    def test_suggested_qty_covers_lead_time_and_safety(self):
        # conso 5/j, lead 10j, review 30j (défaut), safety 20, stock 0 :
        # cible = 5*(10+30) + 20 = 220 ; suggestion = 220 - 0 = 220.
        res = predict_reorder(
            current_stock=0,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertEqual(res.suggested_quantity, 220)

    def test_suggested_qty_subtracts_on_hand(self):
        # Même cible 220 mais 50 déjà en stock ⇒ suggestion = 170.
        res = predict_reorder(
            current_stock=50,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertEqual(res.suggested_quantity, 170)

    def test_longer_lead_time_raises_suggested_qty(self):
        short = predict_reorder(
            current_stock=0, today=TODAY, avg_daily_consumption=5.0,
            lead_time_days=5, safety_stock=0,
        ).suggested_quantity
        long = predict_reorder(
            current_stock=0, today=TODAY, avg_daily_consumption=5.0,
            lead_time_days=30, safety_stock=0,
        ).suggested_quantity
        self.assertGreater(long, short)

    def test_higher_safety_stock_raises_suggested_qty(self):
        low = predict_reorder(
            current_stock=0, today=TODAY, avg_daily_consumption=5.0,
            lead_time_days=10, safety_stock=0,
        ).suggested_quantity
        high = predict_reorder(
            current_stock=0, today=TODAY, avg_daily_consumption=5.0,
            lead_time_days=10, safety_stock=100,
        ).suggested_quantity
        self.assertGreater(high, low)

    def test_no_suggestion_when_stock_well_above_target(self):
        res = predict_reorder(
            current_stock=10000,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertEqual(res.suggested_quantity, 0)

    def test_suggested_qty_rounds_up_fractions(self):
        # conso 1/j, lead 0, review 0, safety 0.5, stock 0 ⇒ cible 0.5 ⇒ ceil 1.
        res = predict_reorder(
            current_stock=0,
            today=TODAY,
            avg_daily_consumption=1.0,
            lead_time_days=0,
            safety_stock=0.5,
            review_period_days=0,
        )
        self.assertEqual(res.suggested_quantity, 1)


class ReorderNowFlagTests(SimpleTestCase):
    def test_reorder_now_when_stock_at_or_below_rop(self):
        # ROP = 5*10 + 20 = 70 ; stock 70 ⇒ reorder_now True.
        res = predict_reorder(
            current_stock=70,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertEqual(res.reorder_point, 70.0)
        self.assertTrue(res.reorder_now)

    def test_no_reorder_when_stock_above_rop(self):
        # ROP = 70 ; stock 200 ⇒ reorder_now False.
        res = predict_reorder(
            current_stock=200,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertFalse(res.reorder_now)

    def test_reorder_now_when_below_rop(self):
        res = predict_reorder(
            current_stock=30,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertTrue(res.reorder_now)


class ZeroConsumptionGuardTests(SimpleTestCase):
    def test_zero_consumption_no_rupture(self):
        res = predict_reorder(
            current_stock=100,
            today=TODAY,
            avg_daily_consumption=0.0,
            lead_time_days=10,
            safety_stock=5,
        )
        self.assertIsNone(res.rupture_date)
        self.assertIsNone(res.days_until_rupture)
        self.assertEqual(res.suggested_quantity, 0)
        self.assertFalse(res.reorder_now)
        self.assertTrue(res.used_fallback)
        self.assertEqual(res.avg_daily_consumption, 0.0)

    def test_negative_consumption_guarded_as_zero(self):
        res = predict_reorder(
            current_stock=100, today=TODAY, avg_daily_consumption=-3.0,
        )
        self.assertIsNone(res.rupture_date)
        self.assertTrue(res.used_fallback)

    def test_zero_consumption_does_not_divide_by_zero(self):
        # Ne doit pas lever ZeroDivisionError.
        res = predict_reorder(
            current_stock=42, today=TODAY, avg_daily_consumption=0,
        )
        self.assertTrue(res.used_fallback)


class NoHistoryFallbackTests(SimpleTestCase):
    def test_no_movements_and_no_consumption_falls_back(self):
        res = predict_reorder(
            current_stock=100,
            today=TODAY,
            movements=[],
            lead_time_days=10,
        )
        self.assertTrue(res.used_fallback)
        self.assertIsNone(res.rupture_date)
        self.assertEqual(res.suggested_quantity, 0)

    def test_none_movements_and_no_consumption_falls_back(self):
        res = predict_reorder(current_stock=100, today=TODAY)
        self.assertTrue(res.used_fallback)
        self.assertEqual(res.avg_daily_consumption, 0.0)

    def test_unreadable_movements_fall_back(self):
        res = predict_reorder(
            current_stock=100,
            today=TODAY,
            movements=[{'date': 'pas-une-date', 'qty_out': 'x'}],
        )
        self.assertTrue(res.used_fallback)


class ConsumptionEstimationTests(SimpleTestCase):
    def test_average_from_movement_history(self):
        # 20 sorties au total sur une fenêtre de 10 jours ⇒ 2/jour.
        movements = [
            {'date': date(2026, 5, 22), 'qty_out': 10},
            {'date': date(2026, 5, 27), 'qty_out': 5},
            {'date': date(2026, 6, 1), 'qty_out': 5},
        ]
        avg = average_daily_consumption(movements, today=TODAY)
        self.assertAlmostEqual(avg, 2.0, places=4)

    def test_predict_uses_movements_when_no_consumption_given(self):
        movements = [
            {'date': date(2026, 5, 22), 'qty_out': 10},
            {'date': date(2026, 6, 1), 'qty_out': 10},
        ]
        res = predict_reorder(
            current_stock=40,
            today=TODAY,
            movements=movements,
            lead_time_days=5,
        )
        # 20 sur 10 jours ⇒ 2/j ; rupture dans 40/2 = 20 jours.
        self.assertAlmostEqual(res.avg_daily_consumption, 2.0, places=4)
        self.assertEqual(res.days_until_rupture, 20.0)
        self.assertFalse(res.used_fallback)

    def test_explicit_consumption_overrides_movements(self):
        movements = [{'date': date(2026, 6, 1), 'qty_out': 100}]
        res = predict_reorder(
            current_stock=50,
            today=TODAY,
            avg_daily_consumption=5.0,
            movements=movements,
        )
        self.assertEqual(res.avg_daily_consumption, 5.0)

    def test_string_dates_parsed(self):
        movements = [
            {'date': '2026-05-22', 'qty_out': 10},
            {'date': '2026-06-01', 'qty_out': 10},
        ]
        avg = average_daily_consumption(movements, today=TODAY)
        self.assertAlmostEqual(avg, 2.0, places=4)

    def test_tuple_movements_supported(self):
        movements = [
            (date(2026, 5, 22), 10),
            (date(2026, 6, 1), 10),
        ]
        avg = average_daily_consumption(movements, today=TODAY)
        self.assertAlmostEqual(avg, 2.0, places=4)

    def test_lookback_excludes_old_movements(self):
        movements = [
            {'date': date(2025, 1, 1), 'qty_out': 1000},  # hors fenêtre 90j
            {'date': date(2026, 5, 22), 'qty_out': 10},
            {'date': date(2026, 6, 1), 'qty_out': 10},
        ]
        avg = average_daily_consumption(
            movements, today=TODAY, lookback_days=90,
        )
        # Les 1000 anciens sont exclus : 20 / 10 jours = 2/j.
        self.assertAlmostEqual(avg, 2.0, places=4)

    def test_inbound_movements_ignored(self):
        # Une entrée (qty_out <= 0) n'est pas une consommation.
        movements = [
            {'date': date(2026, 5, 22), 'qty_out': 10},
            {'date': date(2026, 5, 25), 'qty_out': 0},
            {'date': date(2026, 5, 28), 'qty_out': -50},
        ]
        avg = average_daily_consumption(movements, today=TODAY)
        # Seuls les 10 comptent, sur 10 jours ⇒ 1/jour.
        self.assertAlmostEqual(avg, 1.0, places=4)

    def test_future_movements_ignored(self):
        movements = [
            {'date': date(2026, 5, 22), 'qty_out': 10},
            {'date': date(2026, 7, 1), 'qty_out': 999},  # après today
        ]
        avg = average_daily_consumption(movements, today=TODAY)
        # 10 sur 10 jours ⇒ 1/jour.
        self.assertAlmostEqual(avg, 1.0, places=4)

    def test_empty_history_returns_zero(self):
        self.assertEqual(average_daily_consumption([], today=TODAY), 0.0)
        self.assertEqual(average_daily_consumption(None, today=TODAY), 0.0)


class DefaultsAndFactorsTests(SimpleTestCase):
    def test_default_review_period_used(self):
        # Sans review_period_days, la valeur par défaut s'applique.
        res = predict_reorder(
            current_stock=0,
            today=TODAY,
            avg_daily_consumption=1.0,
            lead_time_days=0,
            safety_stock=0,
        )
        # cible = 1 * (0 + DEFAULT_REVIEW_PERIOD_DAYS) = 30.
        self.assertEqual(res.suggested_quantity, int(DEFAULT_REVIEW_PERIOD_DAYS))

    def test_factors_exposed_for_explainability(self):
        res = predict_reorder(
            current_stock=50,
            today=TODAY,
            avg_daily_consumption=5.0,
            lead_time_days=10,
            safety_stock=20,
        )
        self.assertIn('avg_daily_consumption', res.factors)
        self.assertIn('reorder_point', res.factors)
        self.assertIn('cover_target', res.factors)

    def test_invalid_current_stock_treated_as_zero(self):
        res = predict_reorder(
            current_stock='not-a-number',
            today=TODAY,
            avg_daily_consumption=5.0,
        )
        self.assertEqual(res.days_until_rupture, 0.0)
        self.assertEqual(res.rupture_date, TODAY)
