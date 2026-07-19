"""PUB94 — Tests dérive des postérieurs + branches mortes (observabilité Arbre).

Prouve : (1) le cœur pur (distance au prior, oscillation) ; (2) un nœud figé sur
son prior depuis N semaines est flaggé « branche morte » — EXPOSÉ SUR L'ARBRE
(serializer) — tandis qu'un nœud jeune, testé, déplacé ou retiré ne l'est pas ;
(3) le beat hebdo lève une alerte INFO brake-only par branche morte (idempotent).
"""
import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company

from apps.adsengine import posterior_drift
from apps.adsengine.models import AssumptionNode, EngineAlert
from apps.adsengine.serializers import AssumptionNodeSerializer


class DriftPureTests(SimpleTestCase):
    def test_distance_to_prior_zero_at_prior(self):
        self.assertEqual(
            posterior_drift.distance_to_prior(1.0, 1.0, 1.0, 1.0), 0.0)

    def test_distance_to_prior_l1(self):
        self.assertEqual(
            posterior_drift.distance_to_prior(5.0, 3.0, 1.0, 1.0), 6.0)

    def test_immobile_within_epsilon(self):
        self.assertTrue(posterior_drift.is_immobile(1.005, 1.0, 1.0, 1.0))
        self.assertFalse(posterior_drift.is_immobile(2.0, 1.0, 1.0, 1.0))

    def test_oscillation_score_monotone_is_zero(self):
        self.assertEqual(
            posterior_drift.oscillation_score([0.1, 0.2, 0.3, 0.4]), 0.0)

    def test_oscillation_score_zigzag_is_high(self):
        score = posterior_drift.oscillation_score([0.1, 0.9, 0.1, 0.9, 0.1])
        self.assertGreaterEqual(score, 0.9)
        self.assertTrue(posterior_drift.is_oscillating([0.1, 0.9, 0.1, 0.9]))


class DeadBranchModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Tree Co', slug='tree-co')

    def _node(self, *, alpha=1.0, beta=1.0, last_tested_at=None,
              statut=AssumptionNode.Statut.ASSUMED, created_weeks_ago=6):
        node = AssumptionNode.objects.create(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Hypothèse test', enjeux_s=0.5, pertinence_r=0.5,
            alpha=alpha, beta=beta, alpha0=1.0, beta0=1.0,
            last_tested_at=last_tested_at, statut=statut)
        created = timezone.now() - datetime.timedelta(weeks=created_weeks_ago)
        AssumptionNode.objects.filter(pk=node.pk).update(created_at=created)
        node.refresh_from_db()
        return node

    def test_immobile_untested_aged_node_is_dead_branch(self):
        node = self._node(created_weeks_ago=6)  # au prior, jamais testé, ancien
        self.assertTrue(posterior_drift.is_dead_branch(node, min_weeks=4))

    def test_moved_posterior_is_not_dead(self):
        node = self._node(alpha=5.0, beta=2.0,
                          last_tested_at=timezone.now(), created_weeks_ago=6)
        self.assertFalse(posterior_drift.is_dead_branch(node, min_weeks=4))

    def test_young_node_at_prior_is_not_dead(self):
        node = self._node(created_weeks_ago=1)  # au prior mais trop jeune
        self.assertFalse(posterior_drift.is_dead_branch(node, min_weeks=4))

    def test_recently_tested_node_is_not_dead(self):
        node = self._node(
            last_tested_at=timezone.now() - datetime.timedelta(weeks=1),
            created_weeks_ago=8)
        self.assertFalse(posterior_drift.is_dead_branch(node, min_weeks=4))

    def test_retired_node_is_not_dead(self):
        node = self._node(statut=AssumptionNode.Statut.RETIRED,
                          created_weeks_ago=6)
        self.assertFalse(posterior_drift.is_dead_branch(node, min_weeks=4))

    def test_long_ago_tested_but_decayed_back_is_dead(self):
        node = self._node(
            last_tested_at=timezone.now() - datetime.timedelta(weeks=6),
            created_weeks_ago=8)  # figé au prior, plus testé depuis 6 sem
        self.assertTrue(posterior_drift.is_dead_branch(node, min_weeks=4))

    def test_dead_branch_flag_on_tree_serializer(self):
        node = self._node(created_weeks_ago=6)
        data = AssumptionNodeSerializer(node).data
        self.assertIn('dead_branch', data)
        self.assertTrue(data['dead_branch'])

    def test_dead_branches_lists_only_dead(self):
        self._node(created_weeks_ago=6)                       # morte
        self._node(alpha=4.0, beta=2.0,
                   last_tested_at=timezone.now())              # vivante
        branches = posterior_drift.dead_branches(self.company, min_weeks=4)
        self.assertEqual(len(branches), 1)


class FlagDeadBranchesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Flag Co', slug='flag-co')

    def _dead_node(self):
        node = AssumptionNode.objects.create(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Hypothèse figée', enjeux_s=0.5, pertinence_r=0.5,
            alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)
        AssumptionNode.objects.filter(pk=node.pk).update(
            created_at=timezone.now() - datetime.timedelta(weeks=6))
        return node

    def test_flag_raises_brake_only_info_alert(self):
        self._dead_node()
        before = EngineAlert.objects.count()
        flagged = posterior_drift.flag_dead_branches(self.company, min_weeks=4)
        self.assertEqual(flagged, 1)
        self.assertEqual(EngineAlert.objects.count(), before + 1)
        alert = EngineAlert.objects.latest('id')
        self.assertEqual(alert.severity, EngineAlert.Severity.INFO)
        self.assertIsNone(alert.action)   # brake-only : aucune action liée

    def test_flag_is_idempotent(self):
        self._dead_node()
        posterior_drift.flag_dead_branches(self.company, min_weeks=4)
        again = posterior_drift.flag_dead_branches(self.company, min_weeks=4)
        self.assertEqual(again, 0)   # dédup par entity_key, pas de doublon
