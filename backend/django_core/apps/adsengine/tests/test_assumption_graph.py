"""ASG4 — Tests de la cascade d'invalidation (dd-assumption-engine §3.5).

Prouve sur un arbre à 3 niveaux :
  * la bascule d'un parent périme TOUS ses descendants (children) + les cibles
    d'``invalidation_links`` ;
  * une alerte 🔵 (INFO) est levée par nœud périmé ;
  * AUCUN re-test automatique n'est déclenché (0 Experiment, 0 DecisionLog,
    ``last_tested_at`` intact) ;
  * idempotence (2e passe : rien de neuf) + bornage des cycles.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.adsengine import assumption_graph as graph
from apps.adsengine.models import (
    AssumptionNode, DecisionLog, EngineAlert, Experiment,
)


class InvalidationCascadeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASG Graph', slug='asg-graph')

    def _node(self, enonce, **kw):
        defaults = dict(
            company=self.company, classe=AssumptionNode.Classe.ANGLE,
            enonce_fr=enonce, enjeux_s=0.5, pertinence_r=0.5,
            statut=AssumptionNode.Statut.VALIDATED)
        defaults.update(kw)
        return AssumptionNode.objects.create(**defaults)

    def test_three_level_cascade_marks_all_descendants_stale(self):
        root = self._node('Racine')
        child = self._node('Enfant', parent=root)
        grandchild = self._node('Petit-enfant', parent=child)

        result = graph.invalidate_cascade(root)

        child.refresh_from_db()
        grandchild.refresh_from_db()
        root.refresh_from_db()
        self.assertEqual(child.statut, AssumptionNode.Statut.STALE)
        self.assertEqual(grandchild.statut, AssumptionNode.Statut.STALE)
        # Le nœud d'origine n'est PAS marqué par la cascade (son statut est posé
        # par l'appelant qui l'a fait basculer).
        self.assertEqual(root.statut, AssumptionNode.Statut.VALIDATED)
        self.assertEqual(set(result['invalidated']), {child.pk, grandchild.pk})

    def test_invalidation_links_followed(self):
        root = self._node('Racine')
        linked = self._node('Lié (interaction)')
        root.invalidation_links.add(linked)

        graph.invalidate_cascade(root)

        linked.refresh_from_db()
        self.assertEqual(linked.statut, AssumptionNode.Statut.STALE)

    def test_blue_alert_per_invalidated_node(self):
        root = self._node('Racine')
        child = self._node('Enfant', parent=root)
        self._node('Petit-enfant', parent=child)

        graph.invalidate_cascade(root)

        alerts = EngineAlert.objects.filter(company=self.company)
        self.assertEqual(alerts.count(), 2)
        for a in alerts:
            self.assertEqual(a.severity, EngineAlert.Severity.INFO)  # 🔵
            self.assertEqual(a.detail.get('reason'), 'cascade_invalidation')

    def test_no_auto_retest_triggered(self):
        # INVARIANT §3.5 : la cascade ne teste JAMAIS un enfant automatiquement.
        root = self._node('Racine')
        tested_at = timezone.now()
        child = self._node('Enfant', parent=root, last_tested_at=tested_at)

        graph.invalidate_cascade(root)

        child.refresh_from_db()
        self.assertEqual(child.last_tested_at, tested_at)  # jamais re-testé
        self.assertEqual(Experiment.objects.count(), 0)
        self.assertEqual(DecisionLog.objects.count(), 0)

    def test_idempotent_second_pass(self):
        root = self._node('Racine')
        self._node('Enfant', parent=root)

        graph.invalidate_cascade(root)
        result2 = graph.invalidate_cascade(root)

        # 2e passe : l'enfant est déjà stale → rien de neuf, pas d'alerte doublée.
        self.assertEqual(result2['invalidated'], [])
        self.assertEqual(EngineAlert.objects.filter(company=self.company).count(),
                         1)

    def test_retired_node_not_resurrected(self):
        root = self._node('Racine')
        retired = self._node(
            'Retiré', parent=root, statut=AssumptionNode.Statut.RETIRED)

        graph.invalidate_cascade(root)

        retired.refresh_from_db()
        self.assertEqual(retired.statut, AssumptionNode.Statut.RETIRED)

    def test_cycle_is_bounded(self):
        # a → b via invalidation_links, b → a : la cascade termine (visited).
        a = self._node('A')
        b = self._node('B')
        a.invalidation_links.add(b)
        b.invalidation_links.add(a)

        result = graph.invalidate_cascade(a)

        b.refresh_from_db()
        self.assertEqual(b.statut, AssumptionNode.Statut.STALE)
        # a est l'origine (non marquée) ; seule b est invalidée.
        self.assertEqual(result['invalidated'], [b.pk])

    def test_stale_origin_still_cascades_to_fresh_grandchild(self):
        # Un nœud intermédiaire déjà stale ne bloque pas la cascade plus bas.
        root = self._node('Racine')
        mid = self._node(
            'Milieu', parent=root, statut=AssumptionNode.Statut.STALE)
        leaf = self._node('Feuille', parent=mid)

        result = graph.invalidate_cascade(root)

        leaf.refresh_from_db()
        self.assertEqual(leaf.statut, AssumptionNode.Statut.STALE)
        self.assertIn(leaf.pk, result['invalidated'])
        self.assertNotIn(mid.pk, result['invalidated'])  # déjà stale, non re-marqué
