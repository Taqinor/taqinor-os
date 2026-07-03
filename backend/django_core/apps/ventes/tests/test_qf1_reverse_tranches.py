"""QF1 — Reverse-tranche bill↔kWh helpers (quote_engine/pricing.py).

Pure-function tests (no DB): ``kwh_from_bill`` inverts the progressive
ONEE/Lydec/Redal tranche schedule and ``annual_bill_from_kwh`` values a
consumption per tranche. Both round-trip within tolerance on all three
utilities; the private-distributor tables (Lydec/Redal) carry the
« approximatif » flag; no-utility / zero-bill degrades to a labelled estimate.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qf1_reverse_tranches -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.pricing import (
    ESTIMATION_LABEL,
    LYDEC_TRANCHES,
    ONEE_TRANCHES,
    REDAL_TRANCHES,
    _FALLBACK_KWH_PRICE,
    _weighted_kwh_price,
    annual_bill_from_kwh,
    kwh_from_bill,
)


class TestKwhFromBill(SimpleTestCase):
    """kwh_from_bill inverts the progressive tranche model."""

    def test_inversion_exact_within_first_tranche_onee(self):
        # 50 kWh × 0.9010 = 45.05 MAD — inversion must return 50 kWh.
        bill = 50 * ONEE_TRANCHES[0][1]
        out = kwh_from_bill(bill, utility="onee")
        self.assertAlmostEqual(out["kwh_mensuel"], 50.0, delta=0.2)
        self.assertFalse(out["estimation"])
        self.assertFalse(out["approximatif"])

    def test_inversion_crossing_tranches_onee(self):
        # Cost of exactly 300 kWh under the progressive ONEE schedule.
        cost_300 = _weighted_kwh_price(300, ONEE_TRANCHES) * 300
        out = kwh_from_bill(cost_300, utility="onee")
        self.assertAlmostEqual(out["kwh_mensuel"], 300.0, delta=0.2)

    def test_inversion_top_open_tranche_onee(self):
        cost_800 = _weighted_kwh_price(800, ONEE_TRANCHES) * 800
        out = kwh_from_bill(cost_800, utility="onee")
        self.assertAlmostEqual(out["kwh_mensuel"], 800.0, delta=0.2)

    def test_round_trip_all_three_utilities(self):
        """bill(kwh) → kwh_from_bill(bill) round-trips within tolerance on
        ONEE, Lydec and Redal, across all tranche regimes."""
        for utility in ("onee", "lydec", "redal"):
            for kwh in (30, 100, 180, 350, 700):
                bill = annual_bill_from_kwh(kwh, utility=utility)
                back = kwh_from_bill(bill["bill_mensuel"], utility=utility)
                self.assertAlmostEqual(
                    back["kwh_mensuel"], kwh, delta=0.5,
                    msg=f"round-trip failed for {utility} @ {kwh} kWh")

    def test_lydec_and_redal_flagged_approximatif(self):
        for utility, table in (("lydec", LYDEC_TRANCHES),
                               ("redal", REDAL_TRANCHES)):
            bill = _weighted_kwh_price(200, table) * 200
            out = kwh_from_bill(bill, utility=utility)
            self.assertTrue(out["approximatif"],
                            f"{utility} table is estimated → approximatif")
            self.assertFalse(out["estimation"])
            self.assertEqual(out["label"], "approximatif")

    def test_onee_not_flagged_approximatif(self):
        out = kwh_from_bill(200, utility="onee")
        self.assertFalse(out["approximatif"])
        self.assertEqual(out["label"], "")

    def test_no_utility_returns_labelled_estimate(self):
        out = kwh_from_bill(240)
        self.assertTrue(out["estimation"])
        self.assertEqual(out["label"], ESTIMATION_LABEL)
        # Honest flat fallback, never zero.
        self.assertAlmostEqual(
            out["kwh_mensuel"], round(240 / _FALLBACK_KWH_PRICE, 1), places=1)

    def test_zero_bill_returns_labelled_estimate(self):
        out = kwh_from_bill(0, utility="onee")
        self.assertEqual(out["kwh_mensuel"], 0.0)
        self.assertTrue(out["estimation"])
        self.assertEqual(out["label"], ESTIMATION_LABEL)

    def test_garbage_bill_returns_labelled_estimate(self):
        out = kwh_from_bill("abc", utility="onee")
        self.assertTrue(out["estimation"])
        self.assertEqual(out["kwh_mensuel"], 0.0)

    def test_tranches_override_used_and_not_approximatif(self):
        custom = [(100, 2.0), (None, 3.0)]
        # 150 kWh → 100×2 + 50×3 = 350 MAD
        out = kwh_from_bill(350, tranches_override=custom)
        self.assertAlmostEqual(out["kwh_mensuel"], 150.0, delta=0.2)
        self.assertFalse(out["approximatif"])
        self.assertFalse(out["estimation"])


class TestAnnualBillFromKwh(SimpleTestCase):
    """annual_bill_from_kwh values consumption per progressive tranche."""

    def test_matches_weighted_price_model(self):
        for utility, table in (("onee", ONEE_TRANCHES),
                               ("lydec", LYDEC_TRANCHES),
                               ("redal", REDAL_TRANCHES)):
            out = annual_bill_from_kwh(250, utility=utility)
            expected = _weighted_kwh_price(250, table) * 250
            self.assertAlmostEqual(out["bill_mensuel"], round(expected, 2),
                                   places=2)
            self.assertAlmostEqual(out["bill_annuel"],
                                   round(expected * 12, 2), places=2)

    def test_progressive_higher_consumption_higher_marginal_price(self):
        """The per-kWh average grows with consumption (progressive schedule)."""
        low = annual_bill_from_kwh(80, utility="onee")
        high = annual_bill_from_kwh(600, utility="onee")
        self.assertGreater(high["bill_mensuel"] / 600,
                           low["bill_mensuel"] / 80)

    def test_lydec_redal_flagged_approximatif(self):
        for utility in ("lydec", "redal"):
            out = annual_bill_from_kwh(300, utility=utility)
            self.assertTrue(out["approximatif"])
            self.assertFalse(out["estimation"])

    def test_no_utility_labelled_estimate_flat_fallback(self):
        out = annual_bill_from_kwh(200)
        self.assertTrue(out["estimation"])
        self.assertEqual(out["label"], ESTIMATION_LABEL)
        self.assertAlmostEqual(out["bill_mensuel"],
                               round(200 * _FALLBACK_KWH_PRICE, 2), places=2)

    def test_zero_kwh_labelled_estimate_zero_bill(self):
        out = annual_bill_from_kwh(0, utility="onee")
        self.assertEqual(out["bill_annuel"], 0.0)
        self.assertTrue(out["estimation"])
        self.assertEqual(out["label"], ESTIMATION_LABEL)
