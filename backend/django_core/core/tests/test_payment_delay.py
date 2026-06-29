"""Tests FG365 — prédiction de retard de paiement (fondation pure).

Couvre la fonction pure :func:`core.payment_delay.payment_delay_risk` :
  * monotonicité : plus de jours de retard / retard moyen client plus élevé /
    plus d'impayés passés / plus de relances vaines → score PLUS élevé ;
  * bandes : seuils faible / moyen / élevé bien appliqués ;
  * repli propre : sans feature exploitable, score = ``DEFAULT_RISK`` ;
  * bornage strict à ``[0, 1]`` et robustesse aux entrées invalides ;
  * dérivation des jours de retard depuis échéance + ``today`` (entrées) ;
  * le montant dû est informatif et n'altère PAS le score.

Aucune dépendance à Django/DB — fonction pure (``SimpleTestCase``).
"""
from datetime import date

from django.test import SimpleTestCase

from core.payment_delay import (
    BAND_ELEVE,
    BAND_FAIBLE,
    BAND_MOYEN,
    BAND_THRESHOLD_ELEVE,
    BAND_THRESHOLD_MOYEN,
    DEFAULT_RISK,
    PaymentDelayResult,
    band_for_score,
    days_overdue_from_dates,
    payment_delay_risk,
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
        res = payment_delay_risk({})
        self.assertIsInstance(res, PaymentDelayResult)
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_none_features_does_not_crash(self):
        res = payment_delay_risk(None)
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_non_dict_features_treated_as_empty(self):
        res = payment_delay_risk(['not', 'a', 'dict'])
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_only_unreadable_features_falls_back(self):
        res = payment_delay_risk({
            'days_overdue': 'pas-un-nombre',
            'client_prior_late_count': None,
        })
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_any_usable_feature_clears_fallback(self):
        res = payment_delay_risk({'days_overdue': 10})
        self.assertFalse(res.used_fallback)
        self.assertIn('overdue', res.factors)

    def test_amount_only_still_falls_back_but_carries_amount(self):
        # Le montant est informatif : seul, il ne crée PAS de composante de
        # score → repli, mais le montant est repris dans le résultat.
        res = payment_delay_risk({'montant_du': 5000})
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.amount, 5000.0, places=2)


class MonotonicityTests(SimpleTestCase):
    def test_more_overdue_raises_risk(self):
        low = payment_delay_risk({'days_overdue': 5}).score
        high = payment_delay_risk({'days_overdue': 80}).score
        self.assertGreater(high, low)

    def test_higher_client_avg_delay_raises_risk(self):
        low = payment_delay_risk({'client_avg_delay_days': 5}).score
        high = payment_delay_risk({'client_avg_delay_days': 55}).score
        self.assertGreater(high, low)

    def test_more_prior_late_raises_risk(self):
        low = payment_delay_risk({'client_prior_late_count': 1}).score
        high = payment_delay_risk({'client_prior_late_count': 5}).score
        self.assertGreater(high, low)

    def test_more_relances_raises_risk(self):
        low = payment_delay_risk({'relance_count': 1}).score
        high = payment_delay_risk({'relance_count': 4}).score
        self.assertGreater(high, low)

    def test_overdue_dominates_overall_score(self):
        # Une facture très en retard avec mauvais historique doit dépasser une
        # facture à peine échue avec bon historique.
        bad = payment_delay_risk({
            'days_overdue': 90,
            'client_avg_delay_days': 60,
            'client_prior_late_count': 5,
            'relance_count': 4,
        }).score
        good = payment_delay_risk({
            'days_overdue': 0,
            'client_avg_delay_days': 0,
            'client_prior_late_count': 0,
            'relance_count': 0,
        }).score
        self.assertGreater(bad, good)


class PrioritizationTests(SimpleTestCase):
    def test_classic_at_risk_invoice_is_eleve(self):
        # Facture typiquement à prioriser : très en retard, client mauvais
        # payeur historique, déjà plusieurs relances sans effet.
        res = payment_delay_risk({
            'days_overdue': 120,
            'client_avg_delay_days': 50,
            'client_prior_late_count': 4,
            'relance_count': 3,
            'montant_du': 25000,
        })
        self.assertEqual(res.band, BAND_ELEVE)
        self.assertGreaterEqual(res.score, BAND_THRESHOLD_ELEVE)
        self.assertAlmostEqual(res.amount, 25000.0, places=2)

    def test_fresh_good_payer_is_faible(self):
        # Facture à peine échue, bon payeur, aucune relance → faible priorité.
        res = payment_delay_risk({
            'days_overdue': 2,
            'client_avg_delay_days': 1,
            'client_prior_late_count': 0,
            'relance_count': 0,
        })
        self.assertEqual(res.band, BAND_FAIBLE)
        self.assertLess(res.score, BAND_THRESHOLD_MOYEN)


class DerivedOverdueTests(SimpleTestCase):
    def test_days_overdue_from_dates_positive(self):
        self.assertEqual(
            days_overdue_from_dates(date(2026, 6, 1), date(2026, 6, 16)), 15.0,
        )

    def test_days_overdue_from_dates_not_yet_due_is_zero(self):
        # Échéance future → pas de retard (0), jamais négatif.
        self.assertEqual(
            days_overdue_from_dates(date(2026, 7, 1), date(2026, 6, 16)), 0.0,
        )

    def test_days_overdue_from_dates_missing_returns_none(self):
        self.assertIsNone(days_overdue_from_dates(None, date(2026, 6, 16)))
        self.assertIsNone(days_overdue_from_dates(date(2026, 6, 1), None))

    def test_due_date_and_today_derive_overdue_component(self):
        # Sans days_overdue explicite, échéance + today doivent piloter le score.
        res = payment_delay_risk({
            'due_date': date(2026, 3, 1),
            'today': date(2026, 6, 1),  # ~92 j de retard → composante saturée
        })
        self.assertFalse(res.used_fallback)
        self.assertIn('overdue', res.factors)
        self.assertAlmostEqual(res.factors['overdue'], 1.0, places=4)

    def test_explicit_days_overdue_wins_over_dates(self):
        # days_overdue fourni → les dates ne sont pas utilisées.
        res = payment_delay_risk({
            'days_overdue': 0,
            'due_date': date(2026, 1, 1),
            'today': date(2026, 6, 1),
        })
        self.assertAlmostEqual(res.factors['overdue'], 0.0, places=4)


class AmountIsInformativeTests(SimpleTestCase):
    def test_amount_does_not_change_score(self):
        small = payment_delay_risk({'days_overdue': 30, 'montant_du': 100})
        large = payment_delay_risk({'days_overdue': 30, 'montant_du': 1000000})
        self.assertAlmostEqual(small.score, large.score, places=6)
        self.assertNotAlmostEqual(small.amount, large.amount, places=2)

    def test_amount_alias_accepted(self):
        res = payment_delay_risk({'days_overdue': 10, 'amount': 4200})
        self.assertAlmostEqual(res.amount, 4200.0, places=2)

    def test_negative_amount_clamped_to_zero(self):
        res = payment_delay_risk({'days_overdue': 10, 'montant_du': -50})
        self.assertEqual(res.amount, 0.0)


class ClampAndRobustnessTests(SimpleTestCase):
    def test_score_never_exceeds_one(self):
        res = payment_delay_risk({
            'days_overdue': 100000,
            'client_avg_delay_days': 100000,
            'client_prior_late_count': 999,
            'relance_count': 999,
        })
        self.assertLessEqual(res.score, 1.0)
        self.assertEqual(res.band, BAND_ELEVE)

    def test_score_never_below_zero(self):
        res = payment_delay_risk({
            'days_overdue': 0,
            'client_avg_delay_days': 0,
            'client_prior_late_count': 0,
            'relance_count': 0,
        })
        self.assertGreaterEqual(res.score, 0.0)

    def test_negative_values_ignored(self):
        # Valeurs négatives = composantes ignorées (None via la rampe) → repli.
        res = payment_delay_risk({'days_overdue': -10})
        self.assertTrue(res.used_fallback)
        self.assertAlmostEqual(res.score, DEFAULT_RISK, places=4)

    def test_factors_exposed_for_explainability(self):
        res = payment_delay_risk({
            'days_overdue': 60,
            'client_prior_late_count': 3,
        })
        self.assertIn('overdue', res.factors)
        self.assertIn('prior_late', res.factors)

    def test_partial_features_weighted_average_only_present(self):
        # Une seule composante présente, saturée → score = poids/poids = 1.0,
        # pas dilué vers 0 par les composantes absentes.
        res = payment_delay_risk({'days_overdue': 90})
        self.assertFalse(res.used_fallback)
        self.assertAlmostEqual(res.score, 1.0, places=4)
        self.assertEqual(res.band, BAND_ELEVE)
