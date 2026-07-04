"""Tests XRH31 — score de risque d'attrition employé (fondation pure).

Couvre la fonction pure :func:`core.attrition_risk.attrition_risk` :
  * monotonicité : plus d'incidents/absences/sanctions, une note d'évaluation
    plus basse, une ancienneté plus faible, un délai plus long depuis la
    dernière augmentation → score PLUS élevé ;
  * bandes : seuils faible / moyen / élevé bien appliqués ;
  * repli propre : sans feature exploitable, score = ``DEFAULT_RISK`` ;
  * bornage strict à ``[0, 100]`` et robustesse aux entrées invalides.

Aucune dépendance à Django/DB — fonction pure (``SimpleTestCase``).
"""
from django.test import SimpleTestCase

from core.attrition_risk import (
    BAND_ELEVE,
    BAND_FAIBLE,
    BAND_MOYEN,
    BAND_THRESHOLD_ELEVE,
    BAND_THRESHOLD_MOYEN,
    DEFAULT_RISK,
    AttritionRiskResult,
    attrition_risk,
    band_for_score,
)


class BandThresholdTests(SimpleTestCase):
    def test_band_below_moyen_is_faible(self):
        self.assertEqual(band_for_score(0.0), BAND_FAIBLE)
        self.assertEqual(
            band_for_score(BAND_THRESHOLD_MOYEN - 1), BAND_FAIBLE)

    def test_band_between_thresholds_is_moyen(self):
        self.assertEqual(band_for_score(BAND_THRESHOLD_MOYEN), BAND_MOYEN)
        self.assertEqual(
            band_for_score(BAND_THRESHOLD_ELEVE - 1), BAND_MOYEN)

    def test_band_at_or_above_eleve_is_eleve(self):
        self.assertEqual(band_for_score(BAND_THRESHOLD_ELEVE), BAND_ELEVE)
        self.assertEqual(band_for_score(100.0), BAND_ELEVE)

    def test_band_order_is_monotonic_through_score(self):
        order = [band_for_score(s) for s in (0.0, 50.0, 100.0)]
        self.assertEqual(order, [BAND_FAIBLE, BAND_MOYEN, BAND_ELEVE])


class FallbackTests(SimpleTestCase):
    def test_empty_features_uses_default_risk(self):
        res = attrition_risk({})
        self.assertIsInstance(res, AttritionRiskResult)
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=2)

    def test_none_features_does_not_crash(self):
        res = attrition_risk(None)
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=2)

    def test_non_dict_features_treated_as_empty(self):
        res = attrition_risk(['not', 'a', 'dict'])
        self.assertTrue(res.used_fallback)


class BoundsTests(SimpleTestCase):
    def test_score_never_below_zero(self):
        res = attrition_risk({
            'seniority_months': 100, 'recent_attendance_incidents': 0,
            'unplanned_absences': 0, 'last_evaluation_score': 5,
            'months_since_last_raise': 0, 'sanctions_count': 0,
        })
        self.assertGreaterEqual(res.score, 0.0)

    def test_score_never_above_hundred(self):
        res = attrition_risk({
            'seniority_months': 0, 'recent_attendance_incidents': 999,
            'unplanned_absences': 999, 'last_evaluation_score': 0,
            'months_since_last_raise': 999, 'sanctions_count': 999,
        })
        self.assertLessEqual(res.score, 100.0)

    def test_negative_values_ignored_not_crashing(self):
        res = attrition_risk({'recent_attendance_incidents': -5})
        self.assertTrue(res.used_fallback)


class MonotonicityTests(SimpleTestCase):
    def test_more_incidents_increases_score(self):
        low = attrition_risk({'recent_attendance_incidents': 0})
        high = attrition_risk({'recent_attendance_incidents': 5})
        self.assertGreater(high.score, low.score)

    def test_more_absences_increases_score(self):
        low = attrition_risk({'unplanned_absences': 0})
        high = attrition_risk({'unplanned_absences': 5})
        self.assertGreater(high.score, low.score)

    def test_lower_evaluation_score_increases_risk(self):
        good = attrition_risk({'last_evaluation_score': 5})
        bad = attrition_risk({'last_evaluation_score': 1})
        self.assertGreater(bad.score, good.score)

    def test_lower_seniority_increases_risk(self):
        junior = attrition_risk({'seniority_months': 1})
        senior = attrition_risk({'seniority_months': 60})
        self.assertGreater(junior.score, senior.score)

    def test_longer_since_raise_increases_risk(self):
        recent = attrition_risk({'months_since_last_raise': 0})
        stale = attrition_risk({'months_since_last_raise': 36})
        self.assertGreater(stale.score, recent.score)

    def test_more_sanctions_increases_risk(self):
        clean = attrition_risk({'sanctions_count': 0})
        sanctioned = attrition_risk({'sanctions_count': 3})
        self.assertGreater(sanctioned.score, clean.score)


class FactorsExplainabilityTests(SimpleTestCase):
    def test_factors_present_for_provided_features(self):
        res = attrition_risk({
            'seniority_months': 3, 'recent_attendance_incidents': 2,
        })
        self.assertIn('seniority', res.factors)
        self.assertIn('incidents', res.factors)
        self.assertNotIn('absences', res.factors)
        self.assertFalse(res.used_fallback)
