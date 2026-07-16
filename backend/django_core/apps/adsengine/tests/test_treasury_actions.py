"""ADSENG22 — Tests des kinds ``EngineAction`` trésorerie.

Prouve le cycle complet propose→approuve→applique PAR kind :
  * ``pause_for_month`` route par le chemin PAUSED-only (``update_status_
    paused``), jamais un statut paramétrable ;
  * ``increase_pace`` / ``rebalance_adset_budget`` passent par TOUS les
    garde-fous budget (plafond, variation hebdo, pas ≤15%, propriété miroir,
    ligne de base G4) AVANT d'atteindre ``update_adset_budget`` ;
  * ``enable_cbo`` est PROPOSE-ONLY : un apply lève et l'action passe
    « echouee » (le moteur n'active jamais CBO programmatiquement).

Vérifie aussi que la garde ``_guard_before_dispatch``, la réclamation CAS et la
branche PAUSE existantes restent intactes (le client n'est jamais atteint sur
une violation).
"""
import datetime
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.roles.models import Role
from apps.adsengine import budget_applier, guardrails, pacing, services
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, GuardrailConfig,
    InsightSnapshot,
)

User = get_user_model()


def make_user(company):
    role = Role.objects.create(
        company=company, nom='approver-role', permissions=['adsengine_approve'])
    return User.objects.create_user(
        username='approver', password='x', company=company,
        role_legacy='normal', role=role)


class PauseForMonthCycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pfm', slug='pfm')
        self.user = make_user(self.company)

    def test_full_cycle_routes_through_paused_only(self):
        action = services.propose_pause_for_month(
            self.company, target_meta_id='c1', target_type='campaign')
        self.assertEqual(action.kind, pacing.KIND_PAUSE_FOR_MONTH)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        services.approve_action(action, user=self.user)
        client = Mock()
        client.update_status_paused.return_value = {
            'id': 'c1', 'status': 'PAUSED'}
        services.apply_action(action, client=client)
        # Chemin PAUSED-only exclusif : jamais un update de budget/statut libre.
        client.update_status_paused.assert_called_once()
        # L'appel ne porte AUCUN argument `status` paramétrable : la méthode
        # dédiée FORCE PAUSED (elle ne reçoit qu'object_id/level). Un `hasattr`
        # sur un Mock renvoie toujours True — on inspecte donc les vrais kwargs.
        _call_args, call_kwargs = client.update_status_paused.call_args
        self.assertNotIn('status', call_kwargs)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)


class BudgetKindsCycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bk', slug='bk')
        self.user = make_user(self.company)
        self.cfg = GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=200,
            weekly_change_pct_max=20)
        AdSetMirror.objects.create(company=self.company, meta_id='as1')

    def _apply(self, action):
        client = Mock()
        client.update_adset_budget.return_value = {'success': True}
        services.apply_action(action, client=client)
        return client

    def test_increase_pace_cycle_reaches_update_adset_budget(self):
        action = budget_applier.propose_increase_pace(
            self.company, adset_meta_id='as1', current_daily_budget_mad=100,
            reason_fr='Sous-rythme : coup de pouce.', config=self.cfg)
        self.assertEqual(action.kind, pacing.KIND_INCREASE_PACE)
        services.approve_action(action, user=self.user)
        client = self._apply(action)
        client.update_adset_budget.assert_called_once()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_rebalance_cycle_reaches_update_adset_budget(self):
        action = budget_applier.propose_rebalance_adset_budget(
            self.company, adset_meta_id='as1', current_daily_budget_mad=100,
            target_daily_budget_mad=110, reason_fr='Bandit.', config=self.cfg)
        self.assertEqual(action.kind, pacing.KIND_REBALANCE_ADSET_BUDGET)
        services.approve_action(action, user=self.user)
        client = self._apply(action)
        client.update_adset_budget.assert_called_once()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_foreign_adset_never_reaches_client(self):
        # Action fabriquée à la main ciblant un ad set HORS miroirs société.
        action = EngineAction.objects.create(
            company=self.company, kind=pacing.KIND_REBALANCE_ADSET_BUDGET,
            reason_fr='Rééquilibrage.', status=EngineAction.Statut.APPROUVEE,
            payload={'adset_id': 'ghost', 'current_budget': 10000,
                     'daily_budget': 11000})
        client = Mock()
        with self.assertRaises(budget_applier.MirrorOwnershipViolation):
            services.apply_action(action, client=client)
        client.update_adset_budget.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)

    def test_step_over_15pct_refused_at_dispatch(self):
        # 100 → 118 MAD = +18% : SOUS la variation hebdo (20%) mais AU-DESSUS du
        # pas quotidien (15%) → refusé par assert_step_within_cap (le pas ≤15%
        # est plus strict que le plafond hebdo — belt-and-suspenders).
        action = EngineAction.objects.create(
            company=self.company, kind=pacing.KIND_REBALANCE_ADSET_BUDGET,
            reason_fr='Rééquilibrage.', status=EngineAction.Statut.APPROUVEE,
            payload={'adset_id': 'as1', 'current_budget': 10000,
                     'daily_budget': 11800})
        client = Mock()
        with self.assertRaises(budget_applier.BudgetStepViolation):
            services.apply_action(action, client=client)
        client.update_adset_budget.assert_not_called()

    def test_g4_baseline_blocks_compounding_at_dispatch(self):
        # Ancre 7 j = 100 MAD (appliquée il y a 10 j). Une transition de 118→135
        # (14,4% per-jour, OK) dépasse +35% vs l'ancre → G4 refuse.
        when = timezone.now() - datetime.timedelta(days=10)
        EngineAction.objects.create(
            company=self.company, kind=pacing.KIND_REBALANCE_ADSET_BUDGET,
            reason_fr='Base.', status=EngineAction.Statut.APPLIQUEE,
            payload={'adset_id': 'as1', 'daily_budget': 10000,
                     'new_daily_budget_mad': 100.0},
            applied_at=when)
        action = EngineAction.objects.create(
            company=self.company, kind=pacing.KIND_REBALANCE_ADSET_BUDGET,
            reason_fr='Rééquilibrage.', status=EngineAction.Statut.APPROUVEE,
            payload={'adset_id': 'as1', 'current_budget': 11800,
                     'daily_budget': 13500})
        client = Mock()
        with self.assertRaises(guardrails.GuardrailViolation):
            services.apply_action(action, client=client)
        client.update_adset_budget.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)


class EnableCboProposeOnlyTests(TestCase):
    AS_OF = datetime.date(2026, 7, 20)

    def setUp(self):
        self.company = Company.objects.create(nom='Cbo2', slug='cbo2')
        self.user = make_user(self.company)
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='camp1')
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(AdSetMirror)
        for i in range(8):
            adset = AdSetMirror.objects.create(
                company=self.company, meta_id=f'as{i}', campaign=self.campaign)
            for d in range(10):
                InsightSnapshot.objects.create(
                    company=self.company, content_type=ct, object_id=adset.pk,
                    date=self.AS_OF - datetime.timedelta(days=d), spend=20)

    def test_apply_of_enable_cbo_is_refused_and_marks_echouee(self):
        action = budget_applier.propose_enable_cbo(
            self.company, campaign_meta_id='camp1',
            reason_fr='8 ad sets consistants.', as_of=self.AS_OF)
        self.assertEqual(action.kind, pacing.KIND_ENABLE_CBO)
        services.approve_action(action, user=self.user)
        client = Mock()
        with self.assertRaises(ValueError):
            services.apply_action(action, client=client)
        # Aucune méthode Meta appelée : le moteur n'active jamais CBO.
        client.update_adset_budget.assert_not_called()
        client.update_status_paused.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
