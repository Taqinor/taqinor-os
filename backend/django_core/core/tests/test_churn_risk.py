"""Tests FG363 — score de churn / risque client (fondation pure).

Couvre la fonction pure :func:`core.churn_risk.churn_risk` :
  * monotonicité : plus d'inactivité / contrat lapsé depuis plus longtemps /
    plus de tickets SAV → score PLUS élevé ;
  * effet du contrat : actif réduit le risque, lapsé l'augmente ;
  * bandes : seuils faible / moyen / élevé bien appliqués ;
  * repli propre : sans feature exploitable, score = ``DEFAULT_RISK`` ;
  * bornage strict à ``[0, 1]`` et robustesse aux entrées invalides.

Aucune dépendance à Django/DB — fonction pure (``SimpleTestCase``).
"""
from django.test import SimpleTestCase

from core.churn_risk import (
    BAND_ELEVE,
    BAND_FAIBLE,
    BAND_MOYEN,
    BAND_THRESHOLD_ELEVE,
    BAND_THRESHOLD_MOYEN,
    DEFAULT_RISK,
    ChurnRiskResult,
    band_for_score,
    churn_risk,
)


class BandThresholdTests(SimpleTestCase):
    def test_band_below_moyen_is_faible(self):
        self.assertEqual(band_for_score(0.0), BAND_FAIBLE)
        self.assertEqual(band_for_score(BAND_THRESHOLD_MOYEN - 0.01), BAND_FAIBLE)

    def test_band_between_thresholds_is_moyen(self):
        self.assertEqual(band_for_score(BAND_THRESHOLD_MOYEN), BAND_MOYEN)
        self.assertEqual(band_for_score(BAND_THRESHOLD_ELEVE - 0.01), BAND_MOYEN)

    def test_band_at_or_above_eleve_is_eleve(self):
        self.assertEqual(band_for_score(BAND_THRESHOLD_ELEVE), BAND_ELEVE)
        self.assertEqual(band_for_score(1.0), BAND_ELEVE)

    def test_band_order_is_monotonic_through_score(self):
        order = [band_for_score(s) for s in (0.0, 0.5, 1.0)]
        self.assertEqual(order, [BAND_FAIBLE, BAND_MOYEN, BAND_ELEVE])


class FallbackTests(SimpleTestCase):
    def test_empty_features_uses_default_risk(self):
        res = churn_risk({})
        self.assertIsInstance(res, ChurnRiskResult)
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_none_features_does_not_crash(self):
        res = churn_risk(None)
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_non_dict_features_treated_as_empty(self):
        res = churn_risk(['not', 'a', 'dict'])
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_only_unreadable_features_falls_back(self):
        res = churn_risk({
            'days_since_last_activity': 'pas-un-nombre',
            'open_sav_tickets': None,
        })
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_any_usable_feature_clears_fallback(self):
        res = churn_risk({'open_sav_tickets': 1})
        self.assertFalse(res.used_fallback)
        self.assertIn('sav', res.factors)


class MonotonicityTests(SimpleTestCase):
    def test_more_inactivity_raises_risk(self):
        low = churn_risk({'days_since_last_activity': 10}).score
        high = churn_risk({'days_since_last_activity': 300}).score
        self.assertGreater(high, low)

    def test_longer_contract_lapse_raises_risk(self):
        recent = churn_risk({'days_since_contract_end': 10}).score
        old = churn_risk({'days_since_contract_end': 200}).score
        self.assertGreater(old, recent)

    def test_more_sav_tickets_raises_risk(self):
        one = churn_risk({'open_sav_tickets': 1}).score
        many = churn_risk({'open_sav_tickets': 5}).score
        self.assertGreater(many, one)

    def test_older_intervention_raises_risk(self):
        recent = churn_risk({'last_intervention_age': 30}).score
        old = churn_risk({'last_intervention_age': 600}).score
        self.assertGreater(old, recent)


class ContractTests(SimpleTestCase):
    def test_active_contract_lowers_risk_vs_lapsed(self):
        active = churn_risk({
            'days_since_last_activity': 100,
            'contract_active': True,
        }).score
        lapsed = churn_risk({
            'days_since_last_activity': 100,
            'days_since_contract_end': 200,
        }).score
        self.assertLess(active, lapsed)

    def test_active_contract_relief_reduces_score(self):
        # Même inactivité, un contrat actif doit donner un risque plus bas
        # qu'aucune information de contrat.
        with_contract = churn_risk({
            'days_since_last_activity': 50,
            'contract_active': True,
        }).score
        no_contract_info = churn_risk({
            'days_since_last_activity': 50,
        }).score
        self.assertLess(with_contract, no_contract_info)

    def test_lapsed_contract_dominates_active_flag(self):
        # Si days_since_contract_end est fourni et > 0, le contrat est traité
        # comme lapsé même si contract_active est True (donnée explicite gagne).
        res = churn_risk({
            'contract_active': True,
            'days_since_contract_end': 365,
        })
        self.assertGreater(res.score, 0.0)
        self.assertNotIn('active_relief', res.factors)


class AtRiskClientTests(SimpleTestCase):
    def test_classic_at_risk_client_is_eleve(self):
        # Client maintenance/SAV typiquement à risque : longtemps sans activité,
        # contrat lapsé depuis longtemps, tickets SAV ouverts, pas d'intervention.
        res = churn_risk({
            'days_since_last_activity': 400,
            'days_since_contract_end': 300,
            'open_sav_tickets': 4,
            'last_intervention_age': 600,
        })
        self.assertEqual(res.band, BAND_ELEVE)
        self.assertGreaterEqual(res.score, BAND_THRESHOLD_ELEVE)

    def test_loyal_client_is_faible(self):
        # Client fidèle : actif récemment, contrat actif, aucun ticket.
        res = churn_risk({
            'days_since_last_activity': 5,
            'contract_active': True,
            'open_sav_tickets': 0,
            'last_intervention_age': 20,
        })
        self.assertEqual(res.band, BAND_FAIBLE)
        self.assertLess(res.score, BAND_THRESHOLD_MOYEN)


class ClampAndRobustnessTests(SimpleTestCase):
    def test_score_never_exceeds_one(self):
        res = churn_risk({
            'days_since_last_activity': 100000,
            'days_since_contract_end': 100000,
            'open_sav_tickets': 999,
            'last_intervention_age': 100000,
        })
        self.assertLessEqual(res.score, 1.0)
        self.assertEqual(res.band, BAND_ELEVE)

    def test_score_never_below_zero(self):
        # Tout au plus rassurant : contrat actif, zéro inactivité.
        res = churn_risk({
            'days_since_last_activity': 0,
            'contract_active': True,
            'open_sav_tickets': 0,
            'last_intervention_age': 0,
        })
        self.assertGreaterEqual(res.score, 0.0)

    def test_negative_values_ignored(self):
        # Valeurs négatives = composantes ignorées (None via la rampe).
        res = churn_risk({'days_since_last_activity': -10})
        # Inactivité ignorée → aucune feature exploitable → repli.
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_factors_exposed_for_explainability(self):
        res = churn_risk({
            'days_since_last_activity': 200,
            'open_sav_tickets': 3,
        })
        self.assertIn('inactivity', res.factors)
        self.assertIn('sav', res.factors)
