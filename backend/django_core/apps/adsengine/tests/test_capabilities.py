"""ENG8 — Tests des toggles de capacités (auto-apply par capacité).

Invariant : par défaut TOUT exige l'approbation humaine. Une capacité ACTIVÉE
(``auto_rotate_creative`` / ``auto_rebalance_within_band``) fait sauter
l'approbation pour SON kind uniquement — mais écrit toujours une ligne
``EngineAction auto=True`` (trace d'audit) et journalise. Le reste (autres kinds)
reste soumis à approbation même quand une capacité est activée.
"""
from unittest.mock import Mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import services
from apps.adsengine.models import EngineAction, GuardrailConfig


class CapabilityEnabledTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cap Co', slug='cap-co')

    def test_no_config_means_no_auto(self):
        self.assertFalse(services.capability_enabled(
            None, EngineAction.Kind.ROTATE_CREATIVE))

    def test_toggle_off_means_no_auto(self):
        cfg = GuardrailConfig.objects.create(company=self.company)
        self.assertFalse(services.capability_enabled(
            cfg, EngineAction.Kind.ROTATE_CREATIVE))
        self.assertFalse(services.capability_enabled(
            cfg, EngineAction.Kind.REBALANCE_BUDGET))

    def test_toggle_on_enables_only_its_kind(self):
        cfg = GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=True)
        self.assertTrue(services.capability_enabled(
            cfg, EngineAction.Kind.ROTATE_CREATIVE))
        # L'autre capacité reste désactivée.
        self.assertFalse(services.capability_enabled(
            cfg, EngineAction.Kind.REBALANCE_BUDGET))
        # Un kind hors mapping n'est JAMAIS auto (toujours approbation).
        self.assertFalse(services.capability_enabled(
            cfg, EngineAction.Kind.CREATE_CAMPAIGN))


class ExecuteAutoActionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Auto Co', slug='auto-co')

    def test_capability_off_falls_back_to_proposal(self):
        GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=False)
        client = Mock()
        action = services.execute_auto_action(
            self.company, kind=EngineAction.Kind.ROTATE_CREATIVE,
            reason_fr="Roter le créatif fatigué de l'ad set A.",
            payload={'name': 'Ad v2', 'adset_id': 'as1'}, client=client)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertFalse(action.auto)
        client.create_ad.assert_not_called()

    def test_capability_on_auto_applies_with_audit_row(self):
        GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=True)
        client = Mock()
        client.create_ad.return_value = {'id': 'ad-77'}
        action = services.execute_auto_action(
            self.company, kind=EngineAction.Kind.ROTATE_CREATIVE,
            reason_fr="Roter le créatif fatigué de l'ad set A.",
            payload={'name': 'Ad v2', 'adset_id': 'as1'}, client=client)
        # Auto-appliqué SANS approbation humaine, mais ligne auto=True écrite.
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertTrue(action.auto)
        self.assertIsNone(action.approved_by)
        self.assertEqual(action.result, {'id': 'ad-77'})
        client.create_ad.assert_called_once()

    def test_rebalance_capability_on_auto_applies(self):
        GuardrailConfig.objects.create(
            company=self.company, auto_rebalance_within_band=True)
        client = Mock()
        client.update_adset_budget.return_value = {'success': True}
        action = services.execute_auto_action(
            self.company, kind=EngineAction.Kind.REBALANCE_BUDGET,
            reason_fr="Rééquilibrer +10% vers l'ad set performant (dans la bande).",
            payload={'adset_id': 'as1', 'daily_budget': 110}, client=client)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertTrue(action.auto)
        client.update_adset_budget.assert_called_once()

    def test_non_capability_kind_always_proposed_even_with_toggles_on(self):
        # Toutes les capacités activées : un CREATE_CAMPAIGN reste PROPOSÉ.
        GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=True,
            auto_rebalance_within_band=True)
        client = Mock()
        action = services.execute_auto_action(
            self.company, kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr="Nouvelle campagne leads à Casablanca.",
            payload={'name': 'Solaire', 'objective': 'OUTCOME_LEADS'},
            client=client)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertFalse(action.auto)
        client.create_campaign.assert_not_called()
