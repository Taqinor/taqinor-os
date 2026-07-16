"""ENG14 — Tests du seed idempotent ``seed_adsengine``.

Prouve : une GuardrailConfig par défaut est posée par société, rien de « live »
n'est créé, et une DOUBLE exécution laisse exactement le même état.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.adsengine.models import GuardrailConfig, MetaConnection


class SeedAdsengineTests(TestCase):
    def setUp(self):
        self.c1 = Company.objects.create(nom='S1', slug='s1')
        self.c2 = Company.objects.create(nom='S2', slug='s2')

    def _run(self):
        call_command('seed_adsengine', stdout=StringIO())

    def test_seeds_default_guardrail_per_company(self):
        self._run()
        self.assertEqual(GuardrailConfig.objects.count(), 2)
        cfg = GuardrailConfig.objects.get(company=self.c1)
        self.assertEqual(cfg.daily_budget_ceiling_mad, 100)
        self.assertEqual(cfg.weekly_change_pct_max, 20)
        # Rien de « live » : aucune connexion Meta créée.
        self.assertEqual(MetaConnection.objects.count(), 0)

    def test_double_run_is_idempotent(self):
        self._run()
        self._run()
        self.assertEqual(GuardrailConfig.objects.count(), 2)

    def test_does_not_overwrite_existing_config(self):
        GuardrailConfig.objects.create(
            company=self.c1, daily_budget_ceiling_mad=555)
        self._run()
        # La config existante n'est jamais écrasée (additif seulement).
        self.assertEqual(
            GuardrailConfig.objects.get(company=self.c1).daily_budget_ceiling_mad,
            555)

    def test_skips_inactive_company(self):
        Company.objects.create(nom='Off', slug='off', actif=False)
        self._run()
        # Seules les sociétés opérationnelles (actif=True) sont seedées.
        self.assertEqual(GuardrailConfig.objects.count(), 2)
