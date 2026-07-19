"""PUB91 — Tests du backtest de règle sur l'historique réel (dry-run).

Prouve : (1) une règle est rejouée jour par jour sur les snapshots réels et
liste les actions qu'elle AURAIT proposées ; (2) AUCUNE EngineAction n'est créée
(dry-run pur) ; (3) la borne « as-of » empêche la fuite de données futures
(pas de lookahead) ; (4) l'endpoint est gaté et ne persiste rien.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import rule_backtest
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, InsightSnapshot, RulePolicy,
)

User = get_user_model()


class RuleBacktestModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BT Co', slug='bt-co')
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_1', name='Solaire',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_1', name='Toit', campaign=camp)
        self.ct = ContentType.objects.get_for_model(AdSetMirror)
        self.policy = RulePolicy.objects.create(
            company=self.company, template_key='frequency_high',
            enabled=False, dry_run=True)

    def _snap(self, day, frequency):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct,
            object_id=self.adset.pk, date=day, spend=Decimal('50.00'),
            impressions=1000, frequency=Decimal(str(frequency)))

    def _fill(self, start, count, frequency):
        for i in range(count):
            self._snap(start + datetime.timedelta(days=i), frequency)

    def test_backtest_lists_would_have_proposed_actions(self):
        # 10 j calmes (fréq 2.0) puis 10 j fatigués (fréq 4.0 > seuil 3.0).
        base = datetime.date(2026, 6, 1)
        self._fill(base, 10, 2.0)
        self._fill(base + datetime.timedelta(days=10), 10, 4.0)
        now = timezone.make_aware(datetime.datetime(2026, 6, 20, 12, 0))

        result = rule_backtest.backtest_rule(self.policy, now=now, days=20)
        self.assertTrue(result['supported'])
        self.assertEqual(result['summary']['action_kind'], 'rotate_creative')
        self.assertGreater(result['summary']['would_propose'], 0)
        # Les propositions ne concernent QUE des jours où la fréquence dépasse.
        proposed_days = {p['date'] for p in result['proposals']}
        self.assertNotIn('2026-06-03', proposed_days)   # période calme
        self.assertIn('2026-06-20', proposed_days)       # période fatiguée

    def test_backtest_creates_no_engine_action(self):
        base = datetime.date(2026, 6, 1)
        self._fill(base, 10, 4.0)
        now = timezone.make_aware(datetime.datetime(2026, 6, 10, 12, 0))
        before = EngineAction.objects.count()
        rule_backtest.backtest_rule(self.policy, now=now, days=10)
        self.assertEqual(EngineAction.objects.count(), before)

    def test_as_of_bound_prevents_future_leak(self):
        # Fréquence haute UNIQUEMENT le dernier jour ; rejouer un jour ANTÉRIEUR
        # ne doit JAMAIS voir cette donnée future (pas de lookahead).
        base = datetime.date(2026, 6, 1)
        self._fill(base, 9, 2.0)
        self._snap(datetime.date(2026, 6, 10), 5.0)  # pic futur isolé
        now = timezone.make_aware(datetime.datetime(2026, 6, 10, 12, 0))
        result = rule_backtest.backtest_rule(self.policy, now=now, days=10)
        proposed_days = {p['date'] for p in result['proposals']}
        # Le pic est le 10 ; aucun jour AVANT le 10 ne doit avoir déclenché.
        earlier = {d for d in proposed_days if d < '2026-06-10'}
        self.assertEqual(earlier, set())

    def test_unknown_template_is_unsupported_not_wrong(self):
        # Un template sans évaluateur câblé → supported False + raison FR, jamais
        # un backtest faux. (On force un template_key hors registre.)
        self.policy.template_key = 'template_inexistant_xyz'
        result = rule_backtest.backtest_rule(self.policy, days=10)
        self.assertFalse(result['supported'])
        self.assertTrue(result['reason'])
        self.assertEqual(result['proposals'], [])


class RuleBacktestEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BTE Co', slug='bte-co')
        self.policy = RulePolicy.objects.create(
            company=self.company, template_key='frequency_high',
            enabled=False, dry_run=True)

    def _api(self, perms):
        role = Role.objects.create(
            company=self.company, nom='r-' + perms[0], permissions=perms)
        user = User.objects.create_user(
            username='u-' + perms[0], password='x', company=self.company,
            role_legacy='normal', role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_backtest_endpoint_gated_and_dry_run(self):
        api = self._api(['adsengine_view'])
        before = EngineAction.objects.count()
        resp = api.get(
            f'/api/django/adsengine/regles/{self.policy.pk}/backtest/?jours=30')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('proposals', resp.data)
        self.assertIn('summary', resp.data)
        self.assertEqual(EngineAction.objects.count(), before)

    def test_backtest_endpoint_forbidden_without_permission(self):
        api = self._api(['unrelated_perm'])
        resp = api.get(
            f'/api/django/adsengine/regles/{self.policy.pk}/backtest/')
        self.assertEqual(resp.status_code, 403)
