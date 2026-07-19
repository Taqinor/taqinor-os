"""PUB88 — Tests du livre de compte de l'exploration (exploration/exploitation).

Prouve : (1) le classifieur pur répartit le budget d'une décision entre
exploration et « gagnant confirmé » (P ≥ 80 %) ; (2) sur fixtures, la ligne
MENSUELLE agrège exactement les allocations loggées ; (3) l'endpoint est gaté.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import reporting
from apps.adsengine.models import DecisionLog, Experiment

User = get_user_model()


class ClassifyAllocationPureTests(SimpleTestCase):
    def test_confirmed_winner_is_exploitation(self):
        expl, exploit = reporting.classify_allocation(
            {'A': 80, 'B': 20}, {'A': 0.9, 'B': 0.1})
        self.assertEqual(exploit, 80.0)
        self.assertEqual(expl, 20.0)

    def test_no_confirmed_winner_is_all_exploration(self):
        expl, exploit = reporting.classify_allocation(
            {'A': 50, 'B': 50}, {'A': 0.6, 'B': 0.4})
        self.assertEqual(exploit, 0.0)
        self.assertEqual(expl, 100.0)

    def test_missing_prob_defaults_to_exploration(self):
        expl, exploit = reporting.classify_allocation({'A': 30}, {})
        self.assertEqual(expl, 30.0)
        self.assertEqual(exploit, 0.0)


class ExplorationLedgerModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Expl Co', slug='expl-co')
        self.exp = Experiment.objects.create(
            company=self.company, name='E', status=Experiment.Statut.EN_COURS)

    def _decision(self, budget_map, prob_map, when):
        log = DecisionLog.objects.create(
            company=self.company, experiment=self.exp,
            allocations={'budget_mad': budget_map, 'prob_best': prob_map})
        # created_at est auto_now_add : on le repositionne pour dater le mois.
        DecisionLog.objects.filter(pk=log.pk).update(
            created_at=timezone.make_aware(when))
        return log

    def test_monthly_line_is_exact_on_fixtures(self):
        self._decision({'A': 80, 'B': 20}, {'A': 0.9, 'B': 0.1},
                       datetime.datetime(2026, 6, 10, 12, 0))
        self._decision({'A': 50, 'B': 50}, {'A': 0.6, 'B': 0.4},
                       datetime.datetime(2026, 6, 20, 12, 0))
        self._decision({'A': 100}, {'A': 0.95},
                       datetime.datetime(2026, 7, 5, 12, 0))

        ledger = reporting.exploration_ledger(self.company)
        by_month = {m['mois']: m for m in ledger}

        # Juin : exploitation 80 (A confirmé) ; exploration 20 + 100 = 120.
        self.assertEqual(by_month['2026-06']['exploitation_mad'], 80.0)
        self.assertEqual(by_month['2026-06']['exploration_mad'], 120.0)
        self.assertEqual(by_month['2026-06']['total_mad'], 200.0)
        self.assertEqual(by_month['2026-06']['exploration_pct'], 60.0)
        self.assertEqual(by_month['2026-06']['decisions'], 2)

        # Juillet : gagnant confirmé, 100 % exploitation.
        self.assertEqual(by_month['2026-07']['exploitation_mad'], 100.0)
        self.assertEqual(by_month['2026-07']['exploration_mad'], 0.0)
        self.assertEqual(by_month['2026-07']['exploration_pct'], 0.0)

    def test_months_ordered_oldest_first(self):
        self._decision({'A': 100}, {'A': 0.95},
                       datetime.datetime(2026, 7, 5, 12, 0))
        self._decision({'A': 100}, {'A': 0.95},
                       datetime.datetime(2026, 6, 5, 12, 0))
        ledger = reporting.exploration_ledger(self.company)
        self.assertEqual([m['mois'] for m in ledger], ['2026-06', '2026-07'])


class ExplorationLedgerEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ep2 Co', slug='ep2-co')

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

    def test_endpoint_returns_months_and_is_gated(self):
        api = self._api(['adsengine_view'])
        resp = api.get('/api/django/adsengine/reporting/exploration/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('mois', resp.data)

    def test_endpoint_forbidden_without_permission(self):
        api = self._api(['unrelated_perm'])
        resp = api.get('/api/django/adsengine/reporting/exploration/')
        self.assertEqual(resp.status_code, 403)
