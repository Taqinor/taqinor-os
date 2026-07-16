"""ADSENG4 — Tests gardien + trésorerie.

Prouve : les nouveaux garde-fous ont les défauts attendus, l'escalade
WARNING→CRITICAL se déclenche après 3 cycles non résolus (jamais sur une alerte
résolue), le cooldown effectif suit la sévérité, RulePolicy naît en défaut sûr
(off + dry-run) avec l'invariant auto⇒non-simulation, PacingState upsert est
idempotent sur les 5 états, et le seed des règles est idempotent.
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.adsengine.models import (
    EngineAlert, GuardrailConfig, PacingState, RulePolicy,
)

User = get_user_model()


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class GuardrailTreasuryFieldsTests(TestCase):
    def test_new_fields_have_safe_defaults(self):
        company = Company.objects.create(nom='GC Co', slug='gc-co')
        cfg = GuardrailConfig.objects.create(company=company)
        self.assertEqual(cfg.pacing_band_pct, 15)
        self.assertEqual(cfg.exploration_floor_mad, 20)
        self.assertEqual(cfg.exploration_floor_pct, 20)
        # Enveloppe mensuelle nullable (dérivée si absente).
        self.assertIsNone(cfg.monthly_budget_ceiling_mad)


class EngineAlertEscalationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Al Co', slug='al-co')

    def _warning(self):
        return EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Zéro résultat', severity=EngineAlert.Severity.ATTENTION)

    def test_escalates_after_three_cycles(self):
        alert = self._warning()
        self.assertFalse(alert.register_unresolved_cycle())  # cycle 1
        self.assertFalse(alert.register_unresolved_cycle())  # cycle 2
        escalated = alert.register_unresolved_cycle()        # cycle 3
        self.assertTrue(escalated)
        alert.refresh_from_db()
        self.assertEqual(alert.severity, EngineAlert.Severity.CRITIQUE)
        self.assertEqual(alert.unresolved_cycles, 3)

    def test_resolved_alert_never_escalates(self):
        alert = self._warning()
        alert.resolved = True
        alert.save(update_fields=['resolved'])
        for _ in range(5):
            self.assertFalse(alert.register_unresolved_cycle())
        alert.refresh_from_db()
        self.assertEqual(alert.severity, EngineAlert.Severity.ATTENTION)
        self.assertEqual(alert.unresolved_cycles, 0)

    def test_effective_cooldown_defaults_per_severity(self):
        crit = EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.GARDE_FOU,
            message='Urgent', severity=EngineAlert.Severity.CRITIQUE)
        warn = self._warning()
        info = EngineAlert.objects.create(
            company=self.company, alert_type=EngineAlert.Type.ANOMALIE,
            message='Info', severity=EngineAlert.Severity.INFO)
        self.assertEqual(crit.effective_cooldown_hours, 6)
        self.assertEqual(warn.effective_cooldown_hours, 24)
        self.assertEqual(info.effective_cooldown_hours, 72)
        # Une valeur explicite prime sur le défaut de sévérité.
        warn.cooldown_hours = 12
        self.assertEqual(warn.effective_cooldown_hours, 12)


class RulePolicyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RP Co', slug='rp-co')
        self.manager = make_user(
            self.company, 'rpmgr', ['adsengine_view', 'adsengine_manage'])

    def test_default_is_safe_off_and_dry_run(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery')
        self.assertFalse(rule.enabled)
        self.assertTrue(rule.dry_run)
        self.assertEqual(rule.mode, RulePolicy.Mode.PROPOSE)
        # auto n'est effectif que hors simulation.
        self.assertFalse(rule.is_auto_effective)

    def test_auto_effective_requires_not_dry_run(self):
        rule = RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery',
            mode=RulePolicy.Mode.AUTO, dry_run=False)
        self.assertTrue(rule.is_auto_effective)

    def test_api_rejects_auto_while_dry_run(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/regles/',
            {'template_key': 'zero_results', 'mode': 'auto', 'dry_run': True},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_api_create_sets_created_by_and_company(self):
        resp = auth(self.manager).post(
            '/api/django/adsengine/regles/',
            {'template_key': 'frequency_high'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rule = RulePolicy.objects.get(pk=resp.data['id'])
        self.assertEqual(rule.company_id, self.company.id)
        self.assertEqual(rule.created_by_id, self.manager.id)
        self.assertFalse(rule.enabled)

    def test_unique_per_company_template(self):
        RulePolicy.objects.create(
            company=self.company, template_key='zero_delivery')
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RulePolicy.objects.create(
                    company=self.company, template_key='zero_delivery')


class PacingStateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PS Co', slug='ps-co')

    def test_upsert_idempotent_on_month(self):
        month = datetime.date(2026, 7, 1)
        s1, c1 = PacingState.upsert(
            company=self.company, period_start=month,
            spend_to_date=Decimal('100.00'),
            state=PacingState.State.ON_TRACK)
        self.assertTrue(c1)
        s2, c2 = PacingState.upsert(
            company=self.company, period_start=month,
            spend_to_date=Decimal('250.00'),
            state=PacingState.State.BREACH_IMMINENT)
        self.assertFalse(c2)
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(
            PacingState.objects.filter(company=self.company).count(), 1)
        s2.refresh_from_db()
        self.assertEqual(s2.spend_to_date, Decimal('250.00'))
        self.assertEqual(s2.state, PacingState.State.BREACH_IMMINENT)

    def test_five_states_are_valid(self):
        valid = {
            'on_track', 'under_pacing', 'over_pacing',
            'breach_imminent', 'paused_for_month',
        }
        self.assertEqual(
            {c[0] for c in PacingState.State.choices}, valid)


class SeedRulePoliciesTests(TestCase):
    def setUp(self):
        self.c1 = Company.objects.create(nom='Seed1', slug='seed1')

    def test_seeds_rule_policies_off_and_idempotent(self):
        from apps.adsengine.rules import RULE_TEMPLATES
        call_command('seed_adsengine', stdout=StringIO())
        n = len(RULE_TEMPLATES)
        self.assertEqual(
            RulePolicy.objects.filter(company=self.c1).count(), n)
        self.assertFalse(
            RulePolicy.objects.filter(company=self.c1, enabled=True).exists())
        # Double exécution : jamais de doublon.
        call_command('seed_adsengine', stdout=StringIO())
        self.assertEqual(
            RulePolicy.objects.filter(company=self.c1).count(), n)
