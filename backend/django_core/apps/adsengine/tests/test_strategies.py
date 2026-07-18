"""ADSDEEP41 — Tests des bundles « Stratégies » (seed idempotent, désactivés).

Prouve : chaque bundle référence des templates RÉELS du catalogue fixe ; le seed
est idempotent (2e passage = 0 création) ; toute policy seedée est DÉSACTIVÉE +
en simulation + mode propose (rien ne tourne tant que le fondateur n'a pas opté) ;
chaque bundle porte une phrase de doc fondateur.
"""
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import rule_templates
from apps.adsengine.models import RulePolicy


class StrategyCatalogueTests(TestCase):
    def test_every_strategy_template_is_a_real_catalogue_key(self):
        for key, bundle in rule_templates.STRATEGIES.items():
            self.assertTrue(bundle['label_fr'].strip(), key)
            self.assertTrue(bundle['doc_fr'].strip(), key)
            for item in bundle['templates']:
                self.assertIn(
                    item['template_key'], rule_templates.RULE_TEMPLATES,
                    f"bundle {key} référence un template inconnu")

    def test_strategy_choices_cover_all_bundles(self):
        self.assertEqual(
            {k for k, _ in rule_templates.strategy_choices()},
            set(rule_templates.STRATEGIES.keys()))


class SeedStrategiesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='St Co', slug='st-co')

    def _distinct_template_count(self):
        keys = set()
        for bundle in rule_templates.STRATEGIES.values():
            for item in bundle['templates']:
                keys.add(item['template_key'])
        return len(keys)

    def test_seed_creates_all_disabled(self):
        created = rule_templates.seed_strategies(self.company)
        self.assertEqual(len(created), self._distinct_template_count())
        policies = RulePolicy.objects.filter(company=self.company)
        self.assertEqual(policies.count(), self._distinct_template_count())
        # DÉFAUT SÛR : tout désactivé + simulation + mode propose.
        for p in policies:
            self.assertFalse(p.enabled)
            self.assertTrue(p.dry_run)
            self.assertEqual(p.mode, RulePolicy.Mode.PROPOSE)

    def test_seed_is_idempotent(self):
        rule_templates.seed_strategies(self.company)
        again = rule_templates.seed_strategies(self.company)
        self.assertEqual(again, [])
        self.assertEqual(
            RulePolicy.objects.filter(company=self.company).count(),
            self._distinct_template_count())

    def test_each_bundle_template_has_a_policy(self):
        rule_templates.seed_strategies(self.company)
        for bundle in rule_templates.STRATEGIES.values():
            for item in bundle['templates']:
                self.assertTrue(
                    RulePolicy.objects.filter(
                        company=self.company,
                        template_key=item['template_key']).exists())
