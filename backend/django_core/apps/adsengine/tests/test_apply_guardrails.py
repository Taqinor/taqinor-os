"""ENGFIX1 — Les garde-fous budget sont CÂBLÉS sur le chemin d'apply.

Avant ce fix, ``guardrails.check_daily_ceiling`` / ``check_weekly_change``
existaient mais n'étaient JAMAIS appelés par ``services`` : un REBALANCE_BUDGET
approuvé atteignait ``client.update_adset_budget`` sans aucun plafond. On prouve
ici que le garde-fou tourne AVANT le dispatch (le client n'est jamais appelé sur
un dépassement) et que le budget du payload est bien lu en CENTIMES (÷100 → MAD)
avant comparaison au plafond MAD (G2).
"""
from unittest.mock import Mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import guardrails, services
from apps.adsengine.models import EngineAction, GuardrailConfig


class RebalanceGuardrailApplyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Guard Co', slug='guard-co')
        # Plafond 100 MAD, variation hebdo max 20 %.
        GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=100,
            weekly_change_pct_max=20)

    def _approved_rebalance(self, payload):
        return EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.REBALANCE_BUDGET,
            reason_fr="Rééquilibrer le budget de l'ad set performant.",
            payload=payload, status=EngineAction.Statut.APPROUVEE)

    def test_over_ceiling_is_refused_client_never_called(self):
        # 20000 centimes = 200 MAD > plafond 100 MAD → refus AVANT le client.
        action = self._approved_rebalance(
            {'adset_id': 'as1', 'daily_budget': 20000, 'current_budget': 20000})
        client = Mock()
        with self.assertRaises(guardrails.GuardrailViolation):
            services.apply_action(action, client=client)
        client.update_adset_budget.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
        self.assertIn('plafond', action.error.lower())

    def test_within_limits_passes_guard_and_dispatches(self):
        # 5000 centimes = 50 MAD < 100 MAD ; variation 0 % → les deux passent.
        action = self._approved_rebalance(
            {'adset_id': 'as1', 'daily_budget': 5000, 'current_budget': 5000})
        client = Mock()
        client.update_adset_budget.return_value = {'success': True}
        services.apply_action(action, client=client)
        client.update_adset_budget.assert_called_once()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_budget_unit_is_centimes_not_mad(self):
        # 10000 centimes = 100 MAD EXACTEMENT = plafond 100 MAD (non strict >).
        # Sans la conversion ÷100, 10000 > 100 refuserait à tort : la réussite
        # ici PROUVE que le budget est lu en centimes puis converti en MAD.
        action = self._approved_rebalance(
            {'adset_id': 'as1', 'daily_budget': 10000, 'current_budget': 10000})
        client = Mock()
        client.update_adset_budget.return_value = {'success': True}
        services.apply_action(action, client=client)
        client.update_adset_budget.assert_called_once()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_missing_current_budget_is_inoperative_and_blocks(self):
        # current_budget absent → la variation hebdo ne PEUT PAS s'évaluer :
        # GuardrailInoperative (fail-safe) — jamais un skip silencieux.
        action = self._approved_rebalance(
            {'adset_id': 'as1', 'daily_budget': 5000})
        client = Mock()
        with self.assertRaises(guardrails.GuardrailInoperative):
            services.apply_action(action, client=client)
        client.update_adset_budget.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
