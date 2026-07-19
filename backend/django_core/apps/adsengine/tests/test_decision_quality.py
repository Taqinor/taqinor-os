"""PUB86 — Tests du registre de qualité des décisions (regret réalisé).

Prouve : (1) le cœur pur ``realized_regret`` chiffre en MAD les « laissés sur la
table » d'un champion a posteriori, avec un intervalle honnête sous peu de
données ; (2) sur fixtures multi-semaines, ``regret_registry`` agrège le regret
par type de décision (variable testée) et l'endpoint est gaté ``adsengine_view``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import decision_quality
from apps.adsengine.models import (
    ArmDailyStat, DecisionLog, Experiment, ExperimentArm,
)

User = get_user_model()


class RealizedRegretPureTests(SimpleTestCase):
    """Cœur pur — aucun accès base (SimpleTestCase)."""

    def test_champion_is_lowest_cost_per_conversion(self):
        # A : 300 MAD / 10 conv = 30/conv ; B : 300 MAD / 5 conv = 60/conv.
        r = decision_quality.realized_regret([
            {'label': 'A', 'spend': 300, 'conversions': 10},
            {'label': 'B', 'spend': 300, 'conversions': 5},
        ], min_conversions=1)
        self.assertEqual(r['best_label'], 'A')
        self.assertAlmostEqual(r['best_cpc'], 30.0, places=3)

    def test_regret_is_mad_left_on_the_table(self):
        # B a payé 300 pour 5 conv ; au tarif du champion (30/conv) ces 5 conv
        # auraient coûté 150 → 150 MAD gaspillés. A (champion) : 0.
        r = decision_quality.realized_regret([
            {'label': 'A', 'spend': 300, 'conversions': 10},
            {'label': 'B', 'spend': 300, 'conversions': 5},
        ], min_conversions=1)
        self.assertAlmostEqual(r['total_regret_mad'], 150.0, places=2)
        per = {a['label']: a['wasted_mad'] for a in r['per_arm']}
        self.assertAlmostEqual(per['A'], 0.0, places=3)
        self.assertAlmostEqual(per['B'], 150.0, places=2)

    def test_no_regret_when_single_arm_or_all_equal(self):
        r = decision_quality.realized_regret([
            {'label': 'A', 'spend': 300, 'conversions': 10},
            {'label': 'B', 'spend': 300, 'conversions': 10},
        ], min_conversions=1)
        self.assertAlmostEqual(r['total_regret_mad'], 0.0, places=3)

    def test_interval_present_and_brackets_point_estimate(self):
        r = decision_quality.realized_regret([
            {'label': 'A', 'spend': 300, 'conversions': 10},
            {'label': 'B', 'spend': 300, 'conversions': 5},
        ], min_conversions=1)
        self.assertIsNotNone(r['interval'])
        self.assertLessEqual(r['interval']['low'], r['total_regret_mad'])
        self.assertGreaterEqual(r['interval']['high'], r['total_regret_mad'])

    def test_insufficient_data_flag_under_floor(self):
        # Champion à 3 conversions < plancher 5 → intervalle honnête signalé.
        r = decision_quality.realized_regret([
            {'label': 'A', 'spend': 90, 'conversions': 3},
            {'label': 'B', 'spend': 120, 'conversions': 2},
        ], min_conversions=5)
        self.assertTrue(r['insufficient_data'])
        self.assertIsNotNone(r['interval'])

    def test_no_conversions_anywhere_is_uncomputable(self):
        r = decision_quality.realized_regret([
            {'label': 'A', 'spend': 90, 'conversions': 0},
            {'label': 'B', 'spend': 120, 'conversions': 0},
        ])
        self.assertTrue(r['insufficient_data'])
        self.assertIsNone(r['total_regret_mad'])
        self.assertIsNone(r['interval'])


class RegretRegistryModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Regret Co', slug='regret-co')

    def _experiment_with_arms(self, name, variable, arm_specs):
        """Crée une expérience + bras + stats quotidiennes multi-semaines.

        ``arm_specs`` : liste de ``(label, [(date, spend, conversations), …])``.
        """
        exp = Experiment.objects.create(
            company=self.company, name=name, tested_variable=variable,
            status=Experiment.Statut.EN_COURS)
        for label, stats in arm_specs:
            arm = ExperimentArm.objects.create(
                company=self.company, experiment=exp, label=label)
            for d, spend, conv in stats:
                ArmDailyStat.objects.create(
                    company=self.company, arm=arm, date=d,
                    impressions=1000, conversations=conv, spend=spend)
            # Une décision loggée par bras pour le contexte.
            DecisionLog.objects.create(company=self.company, experiment=exp)
        return exp

    def test_registry_aggregates_regret_by_decision_type(self):
        # Fixtures sur 3 semaines : un bras champion clair + un bras dispendieux.
        wk = [datetime.date(2026, 6, 1), datetime.date(2026, 6, 8),
              datetime.date(2026, 6, 15)]
        self._experiment_with_arms('Hook test', Experiment.Variable.HOOK, [
            ('Hook A', [(wk[0], 100, 4), (wk[1], 100, 4), (wk[2], 100, 4)]),
            ('Hook B', [(wk[0], 100, 2), (wk[1], 100, 2), (wk[2], 100, 2)]),
        ])
        reg = decision_quality.regret_registry(self.company)
        self.assertGreater(reg['total_regret_mad'], 0)
        types = {t['tested_variable']: t for t in reg['par_type']}
        self.assertIn('hook', types)
        self.assertEqual(types['hook']['experiments'], 1)
        # Champion Hook A (300 MAD / 12 conv = 25/conv) ; Hook B 300/6 = 50 →
        # 6 conv × 25 = 150 dû, 300 payé → 150 MAD de regret.
        self.assertAlmostEqual(types['hook']['regret_mad'], 150.0, delta=1.0)

    def test_registry_marks_insufficient_on_thin_data(self):
        wk = datetime.date(2026, 6, 1)
        self._experiment_with_arms('Visuel test', Experiment.Variable.VISUEL, [
            ('Visuel A', [(wk, 60, 2)]),
            ('Visuel B', [(wk, 90, 1)]),
        ])
        reg = decision_quality.regret_registry(self.company)
        self.assertTrue(reg['insufficient_data'])
        self.assertIsNotNone(reg['interval'])


class RegretEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ep Co', slug='ep-co')

    def _user(self, perms):
        role = Role.objects.create(
            company=self.company, nom='r', permissions=perms)
        return User.objects.create_user(
            username='u-' + '-'.join(perms) or 'u', password='x',
            company=self.company, role_legacy='normal', role=role)

    def test_endpoint_gated_and_returns_registry(self):
        user = self._user(['adsengine_view'])
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get('/api/django/adsengine/reporting/regret/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('par_type', resp.data)
        self.assertIn('total_regret_mad', resp.data)

    def test_endpoint_forbidden_without_permission(self):
        user = self._user(['unrelated_perm'])
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get('/api/django/adsengine/reporting/regret/')
        self.assertEqual(resp.status_code, 403)
