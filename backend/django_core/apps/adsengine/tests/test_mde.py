"""ADSENG13 — Tests MDE / puissance (purs : SimpleTestCase).

Le test DORÉ reproduit la table de réalité du dossier (dd-science-core §1.3 /
appendice) À LA DÉCIMALE PRÈS, plus la CI de Poisson du rung signature
``[0.62, 8.77]``. Vérifie aussi l'exemple travaillé (§1.2), l'horizon 7/14/28 j,
la durée pour un effet cible, et les gardes d'entrée.
"""
from django.test import SimpleTestCase

from apps.adsengine import mde


class GoldenReferenceTableTests(SimpleTestCase):
    """dd-science-core §1.3 — reproduit EXACTEMENT les MDE relatifs du dossier."""

    def test_reference_table_exact(self):
        expected = {
            'ctr': {7: 34.9, 14: 24.7, 28: 17.5},
            'click_to_conversation': {7: 25.9, 14: 18.3, 28: 13.0},
            'conversation_to_qualified': {7: 157.6, 14: 111.4, 28: 78.8},
            'qualified_to_signature': {7: 656.9, 14: 462.4, 28: 327.0},
        }
        self.assertEqual(mde.reference_relative_mde_pct(), expected)

    def test_z_constants(self):
        self.assertEqual(mde.Z_SUM, 2.8016)
        self.assertAlmostEqual(mde.Z_SUM_SQ, 7.849, places=3)


class WorkedExampleTests(SimpleTestCase):
    def test_ctr_14day_example(self):
        # §1.2 : n = 12 600, δ = 0.49 pp, relatif = 24.7 %.
        self.assertAlmostEqual(mde.mde_absolute(0.02, 12600) * 100, 0.49,
                               places=2)
        self.assertAlmostEqual(mde.mde_relative(0.02, 12600) * 100, 24.7,
                               places=1)

    def test_smaller_effect_needs_more_sample(self):
        self.assertGreater(mde.sample_size_per_arm(0.02, 0.021),
                           mde.sample_size_per_arm(0.02, 0.03))

    def test_sample_size_positive(self):
        self.assertGreater(mde.sample_size_per_arm(0.02, 0.025), 0)


class HorizonTests(SimpleTestCase):
    def test_mde_shrinks_with_time(self):
        h = mde.mde_by_horizon(0.02, 900)
        self.assertGreater(h[7], h[14])
        self.assertGreater(h[14], h[28])
        self.assertAlmostEqual(h[14] * 100, 24.7, places=1)

    def test_days_to_detect_ctr_effect(self):
        # Détecter ~25 % relatif au rung CTR à ~900 impressions/bras/jour ≈ 2 sem.
        days = mde.days_to_detect(0.02, 0.247, 900)
        self.assertGreaterEqual(days, 13)
        self.assertLessEqual(days, 16)

    def test_days_to_detect_smaller_effect_takes_longer(self):
        self.assertGreater(mde.days_to_detect(0.02, 0.10, 900),
                           mde.days_to_detect(0.02, 0.30, 900))


class PoissonCITests(SimpleTestCase):
    def test_three_signatures_exact_ci(self):
        # dd-science-core §1.3 : CI 95 % exacte pour 3 signatures/mois.
        low, high = mde.poisson_ci(3)
        self.assertAlmostEqual(low, 0.62, places=2)
        self.assertAlmostEqual(high, 8.77, places=2)

    def test_zero_count_lower_bound_is_zero(self):
        low, high = mde.poisson_ci(0)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.0)

    def test_ci_widens_below_and_above_point(self):
        low, high = mde.poisson_ci(3)
        self.assertLess(low, 3)
        self.assertGreater(high, 3)

    def test_chi2_quantile_spot_checks(self):
        self.assertAlmostEqual(mde._chi2_ppf(0.025, 6), 1.2373, places=2)
        self.assertAlmostEqual(mde._chi2_ppf(0.975, 8), 17.5345, places=2)


class GuardTests(SimpleTestCase):
    def test_invalid_inputs_raise(self):
        with self.assertRaises(ValueError):
            mde.mde_absolute(0.02, 0)
        with self.assertRaises(ValueError):
            mde.mde_relative(0.0, 100)
        with self.assertRaises(ValueError):
            mde.sample_size_per_arm(0.02, 0.02)
        with self.assertRaises(ValueError):
            mde.days_to_detect(0.02, 0.0, 900)
