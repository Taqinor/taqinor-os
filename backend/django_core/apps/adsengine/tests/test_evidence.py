"""PUB18 — Writer d'évidence : les résultats RÉELS nourrissent l'Arbre.

Prouve que le decay n'est plus le SEUL writer de α/β : une expérience close
(preuve) déplace le posterior du nœud lié, et une signature Odoo attribuée
l'incrémente aussi ; le tout tracé dans un DecisionLog et IDEMPOTENT (une même
preuve ne compte qu'une fois).
"""
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import evidence
from apps.adsengine.models import (
    AssumptionNode, DecisionLog, Experiment,
)


class EvidenceBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ev Co', slug='ev-co')
        self.exp = Experiment.objects.create(
            company=self.company, name='Test hook',
            status=Experiment.Statut.EN_COURS)

    def _node(self, **kw):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.CREATIF,
            enonce_fr='Le hook prix marche mieux.', enjeux_s=0.5,
            pertinence_r=0.5, alpha=2.0, beta=2.0, alpha0=1.0, beta0=1.0)
        defaults.update(kw)
        return AssumptionNode.objects.create(**defaults)

    def _scheduled_log(self, node):
        """Simule la trace de voi.schedule_next reliant l'exp au nœud testé."""
        return DecisionLog.objects.create(
            company=self.company, experiment=self.exp,
            allocations={'winner_node_id': node.pk},
            summary_fr='Slot ouvert (VoI).')


class RecordNodeEvidenceTests(EvidenceBase):
    def test_success_moves_alpha_and_traces(self):
        node = self._node(alpha=2.0, beta=2.0)
        node, log = evidence.record_node_evidence(
            node, self.exp, successes=3, failures=1, source='experiment')
        node.refresh_from_db()
        self.assertEqual(node.alpha, 5.0)   # 2 + 3
        self.assertEqual(node.beta, 3.0)    # 2 + 1
        self.assertIsNotNone(node.last_tested_at)
        self.assertIsNotNone(log)
        self.assertEqual(log.experiment_id, self.exp.pk)

    def test_zero_evidence_is_noop(self):
        node = self._node()
        _, log = evidence.record_node_evidence(node, self.exp)
        self.assertIsNone(log)
        node.refresh_from_db()
        self.assertEqual(node.alpha, 2.0)

    def test_idempotent_by_key(self):
        node = self._node(alpha=2.0, beta=2.0)
        evidence.record_node_evidence(
            node, self.exp, successes=1, idempotency_key='k1')
        # Deuxième application de la MÊME preuve → ignorée.
        evidence.record_node_evidence(
            node, self.exp, successes=1, idempotency_key='k1')
        node.refresh_from_db()
        self.assertEqual(node.alpha, 3.0)  # +1 une seule fois
        self.assertEqual(
            DecisionLog.objects.filter(
                inputs__evidence_key='k1').count(), 1)

    def test_cross_company_rejected(self):
        other = Company.objects.create(nom='Other', slug='other')
        foreign_exp = Experiment.objects.create(company=other, name='X')
        node = self._node()
        with self.assertRaises(ValueError):
            evidence.record_node_evidence(
                node, foreign_exp, successes=1)


class ExperimentOutcomeTests(EvidenceBase):
    def test_closed_experiment_moves_linked_node_posterior(self):
        # Le decay N'A PAS touché ce nœud : seule la preuve le déplace.
        node = self._node(alpha=2.0, beta=2.0)
        self._scheduled_log(node)
        resolved, log = evidence.record_experiment_outcome(
            self.exp, validated=True)
        self.assertEqual(resolved.pk, node.pk)
        node.refresh_from_db()
        self.assertEqual(node.alpha, 3.0)  # hypothèse confirmée → +1 succès
        self.assertEqual(node.beta, 2.0)
        self.assertIsNotNone(log)

    def test_refuted_experiment_moves_beta(self):
        node = self._node(alpha=2.0, beta=2.0)
        self._scheduled_log(node)
        evidence.record_experiment_outcome(self.exp, validated=False)
        node.refresh_from_db()
        self.assertEqual(node.alpha, 2.0)
        self.assertEqual(node.beta, 3.0)  # infirmée → +1 échec

    def test_outcome_idempotent_per_experiment(self):
        node = self._node(alpha=2.0, beta=2.0)
        self._scheduled_log(node)
        evidence.record_experiment_outcome(self.exp, validated=True)
        evidence.record_experiment_outcome(self.exp, validated=True)
        node.refresh_from_db()
        self.assertEqual(node.alpha, 3.0)  # une seule fois

    def test_noop_without_linked_node(self):
        # Aucune trace VoI → aucun nœud rattaché → NO-OP propre.
        resolved, log = evidence.record_experiment_outcome(
            self.exp, validated=True)
        self.assertIsNone(resolved)
        self.assertIsNone(log)


class SignatureEvidenceTests(EvidenceBase):
    def test_attributed_signatures_increment_alpha(self):
        node = self._node(alpha=2.0, beta=2.0)
        evidence.record_signature_evidence(
            node, self.exp, signatures=2,
            idempotency_key='exp:1:sig:2026-07-01')
        node.refresh_from_db()
        self.assertEqual(node.alpha, 4.0)  # +2 signatures = +2 succès
        self.assertEqual(node.beta, 2.0)

    def test_signatures_idempotent(self):
        node = self._node(alpha=2.0, beta=2.0)
        for _ in range(2):
            evidence.record_signature_evidence(
                node, self.exp, signatures=2, idempotency_key='sig-k')
        node.refresh_from_db()
        self.assertEqual(node.alpha, 4.0)  # appliqué une seule fois
