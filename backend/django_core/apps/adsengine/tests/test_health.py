"""SIG1 — Tests des deux scores de santé SÉPARÉS (dd-assumption-engine §11).

Golden-table sur ``health.py`` (module pur, poids fixes) + l'INVARIANT DUR :
un score de santé est affichage/alerte SEULEMENT — il ne doit JAMAIS être lu
par le bandit (``bandit.py``), l'échelle de récompense (``rewards.py``) ou
l'allocation (``allocation.py``). Une vente lente (opérations) ne doit jamais
salir l'allocation créative.
"""
import inspect
import os
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.adsengine import allocation, bandit, health, rewards


class HealthScoreGoldenTests(SimpleTestCase):
    """Golden-table : poids fixes × signaux → score exact."""

    def _config(self, ctr=60, freshness=40, cpl=60, delivery=40):
        return SimpleNamespace(
            health_creative_weight_ctr=ctr,
            health_creative_weight_freshness=freshness,
            health_ops_weight_cpl=cpl,
            health_ops_weight_delivery=delivery,
        )

    def test_creative_health_default_weights(self):
        # 60% * 1.0 + 40% * 0.5 = 0.8
        score = health.creative_health(
            {'ctr': 1.0, 'freshness': 0.5}, self._config())
        self.assertAlmostEqual(score, 0.8, places=9)

    def test_creative_health_all_zero(self):
        score = health.creative_health(
            {'ctr': 0.0, 'freshness': 0.0}, self._config())
        self.assertEqual(score, 0.0)

    def test_creative_health_all_perfect(self):
        score = health.creative_health(
            {'ctr': 1.0, 'freshness': 1.0}, self._config())
        self.assertEqual(score, 1.0)

    def test_operations_health_default_weights(self):
        # 60% * 0.2 + 40% * 0.9 = 0.48
        score = health.operations_health(
            {'cpl': 0.2, 'delivery': 0.9}, self._config())
        self.assertAlmostEqual(score, 0.48, places=9)

    def test_operations_health_equal_weights(self):
        score = health.operations_health(
            {'cpl': 0.4, 'delivery': 0.8},
            self._config(cpl=50, delivery=50))
        self.assertAlmostEqual(score, 0.6, places=9)

    def test_missing_signal_defaults_to_zero(self):
        score = health.creative_health({}, self._config())
        self.assertEqual(score, 0.0)

    def test_clamps_out_of_range_signals(self):
        score = health.creative_health(
            {'ctr': 5.0, 'freshness': -3.0}, self._config())
        self.assertEqual(score, 1.0)  # ctr clampé à 1.0, freshness à 0.0

    def test_zero_total_weight_returns_zero_not_error(self):
        score = health.creative_health(
            {'ctr': 1.0, 'freshness': 1.0}, self._config(ctr=0, freshness=0))
        self.assertEqual(score, 0.0)

    def test_config_without_health_attrs_uses_module_defaults(self):
        # Objet minimal sans les attributs health_* → défauts du module.
        score = health.creative_health(
            {'ctr': 1.0, 'freshness': 0.5}, SimpleNamespace())
        self.assertAlmostEqual(score, 0.8, places=9)

    def test_slow_sale_ops_score_independent_of_creative_score(self):
        # Le CŒUR du §11 : une vente lente (ops) ne doit JAMAIS influencer le
        # score créatif — deux fonctions, deux entrées séparées, jamais de
        # signal partagé.
        config = self._config()
        creative = health.creative_health(
            {'ctr': 0.9, 'freshness': 0.9}, config)
        ops_bad = health.operations_health(
            {'cpl': 0.0, 'delivery': 0.0}, config)
        ops_good = health.operations_health(
            {'cpl': 1.0, 'delivery': 1.0}, config)
        # Le score créatif ne varie PAS selon que les opérations sont
        # mauvaises ou bonnes — il n'a même pas accès aux signaux ops.
        self.assertAlmostEqual(creative, 0.9, places=9)
        self.assertNotEqual(ops_bad, ops_good)


class HealthNeverConsumedByAllocationInvariantTests(SimpleTestCase):
    """INVARIANT DUR — santé = affichage/alerte SEULEMENT, jamais lue par le
    bandit ou l'allocation (§11). Vérifié STRUCTURELLEMENT (source + import
    graph), pas seulement par convention."""

    MODULES = [bandit, rewards, allocation]

    def test_modules_never_import_health(self):
        for module in self.MODULES:
            source = inspect.getsource(module)
            self.assertNotIn(
                'health', source.lower(),
                f'{module.__name__} référence "health" — un score de santé '
                'ne doit JAMAIS être lu par le bandit/l\'allocation (§11).')

    def test_modules_have_zero_io_no_model_imports(self):
        # Discipline documentée de ces 3 modules : purs, sans accès base.
        for module in self.MODULES:
            source = inspect.getsource(module)
            self.assertNotIn('from .models import', source)
            self.assertNotIn('from django.db import models', source)

    def test_health_module_is_not_imported_by_allocation_path(self):
        for module in self.MODULES:
            file_path = inspect.getfile(module)
            with open(file_path, encoding='utf-8') as fh:
                content = fh.read()
            self.assertNotIn('import health', content)
            self.assertNotIn('from . import health', content)
            self.assertNotIn('from apps.adsengine import health', content)
            self.assertNotIn('from apps.adsengine.health', content)

    def test_health_module_itself_is_pure(self):
        # health.py ne doit rien connaître du bandit/de l'allocation non plus
        # (séparation dans les DEUX sens — pas de couplage caché).
        source = inspect.getsource(health)
        self.assertNotIn('bandit', source.lower())
        self.assertNotIn('allocation', source.lower())
        self.assertNotIn('rewards', source.lower())

    def test_health_module_path_exists_once(self):
        # Sanity : on a bien testé le VRAI fichier (pas un stub vide).
        path = inspect.getfile(health)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)
