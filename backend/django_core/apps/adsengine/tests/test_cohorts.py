"""SIG3 — Tests du filigrane de cohorte (fa-signals §4.3 / dd §11).

Fixtures multi-cohortes (jeunes vs mûres) + l'INVARIANT DUR : un signal IMMATURE
n'est JAMAIS compté comme mûr — sa valeur est ignorée, son poids renormalisé
hors du score, le score marqué provisoire. Module pur → ``SimpleTestCase``.
"""
import datetime
import inspect

from django.test import SimpleTestCase

from apps.adsengine import bandit, cohorts


# Poids d'exemple couvrant la chaîne de maturation (proxy → CPL → signature).
WEIGHTS = {
    'ctr': 0.30,               # mûr à 1 j
    'ctwa_conversations': 0.25,  # mûr à 7 j
    'cpl': 0.25,               # mûr à 14 j
    'devis_sent': 0.20,        # mûr à 21 j
}


class CohortAgeTests(SimpleTestCase):
    def test_age_from_impression_date(self):
        imp = datetime.date(2026, 7, 1)
        self.assertEqual(cohorts.cohort_age_days(imp, datetime.date(2026, 7, 16)), 15)

    def test_future_impression_clamped_to_zero(self):
        imp = datetime.date(2026, 7, 20)
        self.assertEqual(cohorts.cohort_age_days(imp, datetime.date(2026, 7, 1)), 0)

    def test_accepts_datetime(self):
        imp = datetime.datetime(2026, 7, 1, 10, 0)
        self.assertEqual(cohorts.cohort_age_days(imp, datetime.date(2026, 7, 8)), 7)


class MaturityTests(SimpleTestCase):
    def test_signal_matures_at_its_window(self):
        self.assertFalse(cohorts.is_mature('cpl', 13))
        self.assertTrue(cohorts.is_mature('cpl', 14))
        self.assertTrue(cohorts.is_mature('cpl', 30))

    def test_unknown_signal_is_never_mature(self):
        # Conservateur : on ne devine pas la maturité d'un signal inconnu.
        self.assertFalse(cohorts.is_mature('mystere', 9999))

    def test_fast_signal_mature_almost_immediately(self):
        self.assertTrue(cohorts.is_mature('ctr', 1))
        self.assertFalse(cohorts.is_mature('ctr', 0))


class RenormalizeTests(SimpleTestCase):
    def test_immature_signals_dropped_and_weights_renormalized(self):
        # Cohorte de 8 j : ctr (1) + ctwa (7) mûrs ; cpl (14) + devis (21) non.
        renorm, provisional = cohorts.renormalize_weights(WEIGHTS, 8)
        self.assertEqual(set(renorm.keys()), {'ctr', 'ctwa_conversations'})
        self.assertTrue(provisional)
        self.assertAlmostEqual(sum(renorm.values()), 1.0, places=9)
        # Ratio 0.30:0.25 préservé après renormalisation.
        self.assertAlmostEqual(renorm['ctr'] / renorm['ctwa_conversations'],
                               0.30 / 0.25, places=9)

    def test_fully_mature_cohort_is_not_provisional(self):
        renorm, provisional = cohorts.renormalize_weights(WEIGHTS, 40)
        self.assertEqual(set(renorm.keys()), set(WEIGHTS.keys()))
        self.assertFalse(provisional)
        self.assertAlmostEqual(sum(renorm.values()), 1.0, places=9)

    def test_no_mature_signal_returns_empty_provisional(self):
        renorm, provisional = cohorts.renormalize_weights(WEIGHTS, 0)
        self.assertEqual(renorm, {})
        self.assertTrue(provisional)


class IntegrateCohortInvariantTests(SimpleTestCase):
    """INVARIANT DUR : la valeur d'un signal IMMATURE n'est JAMAIS comptée."""

    def test_immature_signal_value_is_ignored(self):
        # Cohorte jeune (8 j) : un CPL parfait (immature) ne doit PAS gonfler le
        # score — il n'est pas encore mûr.
        young = cohorts.integrate_cohort(
            {'ctr': 0.5, 'ctwa_conversations': 0.5, 'cpl': 1.0,
             'devis_sent': 1.0}, WEIGHTS, 8)
        self.assertNotIn('cpl', young.mature_keys)
        self.assertNotIn('devis_sent', young.mature_keys)
        self.assertIn('cpl', young.dropped_keys)
        self.assertTrue(young.provisional)
        # Score = 0.5 (seuls ctr+ctwa mûrs, tous deux 0.5) — le cpl=1.0 ignoré.
        self.assertAlmostEqual(young.score, 0.5, places=9)

    def test_same_signals_mature_cohort_counts_everything(self):
        mature = cohorts.integrate_cohort(
            {'ctr': 0.5, 'ctwa_conversations': 0.5, 'cpl': 1.0,
             'devis_sent': 1.0}, WEIGHTS, 40)
        self.assertFalse(mature.provisional)
        self.assertEqual(mature.dropped_keys, [])
        # Maintenant le cpl/devis parfaits COMPTENT → score > le cas jeune.
        # 0.30*0.5 + 0.25*0.5 + 0.25*1 + 0.20*1 = 0.725
        self.assertAlmostEqual(mature.score, 0.725, places=9)

    def test_multi_cohort_fixture_young_never_exceeds_via_immature(self):
        # Deux cohortes, mêmes signaux bruts : la jeune ne peut pas « voir » les
        # signaux lents, donc ne les intègre jamais.
        signals = {'ctr': 0.4, 'ctwa_conversations': 0.4, 'cpl': 0.9,
                   'devis_sent': 0.9}
        young = cohorts.integrate_cohort(signals, WEIGHTS, 5)
        mid = cohorts.integrate_cohort(signals, WEIGHTS, 15)
        old = cohorts.integrate_cohort(signals, WEIGHTS, 40)
        self.assertEqual(young.mature_keys, ['ctr'])  # ctwa (7) pas encore à 5 j
        self.assertIn('cpl', mid.mature_keys)
        self.assertNotIn('devis_sent', mid.mature_keys)  # 21 > 15
        self.assertEqual(set(old.mature_keys), set(WEIGHTS.keys()))
        self.assertTrue(young.provisional)
        self.assertTrue(mid.provisional)
        self.assertFalse(old.provisional)


class SlowSignalTests(SimpleTestCase):
    def test_signature_excluded_from_weekly_score(self):
        weights = dict(WEIGHTS, signature=0.30)
        # Même à 90 j, la signature n'entre PAS dans le score hebdo (include_slow
        # False par défaut).
        weekly = cohorts.integrate_cohort(weights, weights, 90)
        self.assertNotIn('signature', weekly.mature_keys)
        self.assertIn('signature', weekly.dropped_keys)

    def test_signature_included_only_for_quarterly(self):
        weights = dict(WEIGHTS, signature=0.30)
        quarterly = cohorts.integrate_cohort(
            weights, weights, 90, include_slow=True)
        self.assertIn('signature', quarterly.mature_keys)

    def test_signature_not_mature_before_60_days_even_quarterly(self):
        weights = dict(WEIGHTS, signature=0.30)
        q = cohorts.integrate_cohort(weights, weights, 45, include_slow=True)
        self.assertNotIn('signature', q.mature_keys)


class ScoreCohortAnchorTests(SimpleTestCase):
    def test_score_cohort_derives_age_from_impression_date(self):
        cohort = cohorts.Cohort(
            impression_date=datetime.date(2026, 7, 1),
            signals={'ctr': 1.0, 'ctwa_conversations': 1.0, 'cpl': 1.0,
                     'devis_sent': 1.0})
        # À J+8, seuls ctr + ctwa sont mûrs.
        result = cohorts.score_cohort(
            cohort, WEIGHTS, as_of=datetime.date(2026, 7, 9))
        self.assertEqual(set(result.mature_keys), {'ctr', 'ctwa_conversations'})
        self.assertTrue(result.provisional)


class CohortsPurityTests(SimpleTestCase):
    """Comme SIG1/SIG2 : module pur, jamais lu par le bandit (qui tourne sur le
    seul proxy 7 j)."""

    def test_bandit_never_imports_cohorts(self):
        self.assertNotIn('cohorts', inspect.getsource(bandit))

    def test_module_is_pure_no_model_io(self):
        source = inspect.getsource(cohorts)
        self.assertNotIn('from .models import', source)
        self.assertNotIn('from django.db import models', source)
