"""AACQ4 — ``MetaClient.update_adset_budget`` existe : une action budget
approuvée et passée par les garde-fous s'applique sur un VRAI ``MetaClient``
(transport HTTP simulé, aucun appel Meta réel) ; contrat AST : toute méthode
``client.<m>`` appelée par ``_dispatch*`` / ``_build_batch_op`` existe.
"""
import ast
import inspect
from unittest import mock
from urllib.parse import parse_qs

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.meta_client import MetaClient
from apps.adsengine.models import (
    AdSetMirror, EngineAction, GuardrailConfig, MetaConnection,
)
from apps.adsengine.pacing import KIND_INCREASE_PACE

User = get_user_model()


class BudgetMetaTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bud', slug='aacq4-bud')
        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_aacq4', currency='MAD',
            enabled=True, credentials={'access_token': 'tok-aacq4'})
        GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=1000,
            weekly_change_pct_max=20)
        AdSetMirror.objects.create(
            company=self.company, meta_id='as-aacq4', name='AS',
            status='ACTIVE', budget='10000')
        role = Role.objects.create(
            company=self.company, nom='aacq4-admin',
            permissions=['adsengine_view', 'adsengine_manage',
                         'adsengine_approve'])
        self.admin = User.objects.create_user(
            username='aacq4-admin', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.requests = []

    def _client(self, connection=None, **kwargs):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(200, json={'success': True})
        return MetaClient(
            access_token='tok-aacq4', ad_account_id='act_aacq4',
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0, backoff_base=0)

    def _action(self, kind, *, daily, current, adset_id='as-aacq4'):
        return EngineAction.objects.create(
            company=self.company, kind=kind, reason_fr='Budget.',
            status=EngineAction.Statut.APPROUVEE, approved_by=self.admin,
            payload={'adset_id': adset_id, 'daily_budget': daily,
                     'current_budget': current})

    def _apply(self, action):
        with mock.patch.object(MetaClient, 'from_connection',
                               side_effect=self._client):
            return self.api.post(
                f'/api/django/adsengine/actions/{action.pk}/apply/')

    def _form(self, request):
        return parse_qs(request.content.decode('utf-8'))

    def test_rebalance_applique_vrai_client(self):
        action = self._action(EngineAction.Kind.REBALANCE_BUDGET,
                              daily=11000, current=10000)
        resp = self._apply(action)
        self.assertEqual(resp.status_code, 200, resp.data)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertIsNotNone(action.applied_at)
        self.assertEqual(action.result, {'success': True})
        self.assertEqual(len(self.requests), 1)
        req = self.requests[0]
        self.assertEqual(req.method, 'POST')
        self.assertTrue(req.url.path.endswith('/as-aacq4'), req.url)
        self.assertEqual(self._form(req)['daily_budget'], ['11000'])

    def test_increase_pace_applique(self):
        action = self._action(KIND_INCREASE_PACE, daily=11000, current=10000)
        resp = self._apply(action)
        self.assertEqual(resp.status_code, 200, resp.data)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertEqual(len(self.requests), 1)

    def test_corps_sans_status(self):
        client = self._client()
        client.update_adset_budget(
            adset_id='as-aacq4', daily_budget=11000,
            extra_fields={'status': 'ACTIVE'})
        form = self._form(self.requests[0])
        self.assertNotIn('status', form)
        self.assertNotIn('ACTIVE', self.requests[0].content.decode('utf-8'))
        self.assertEqual(form['daily_budget'], ['11000'])

    def test_plafond_bloque_avant_post(self):
        # 2 000 MAD > plafond 1 000 MAD : refus AVANT tout POST.
        action = self._action(EngineAction.Kind.REBALANCE_BUDGET,
                              daily=200000, current=190000)
        resp = self._apply(action)
        self.assertEqual(resp.status_code, 502, resp.data)
        self.assertEqual(self.requests, [])
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)

    def test_adset_hors_miroirs_refuse(self):
        action = self._action(KIND_INCREASE_PACE, daily=11000, current=10000,
                              adset_id='as-etranger')
        resp = self._apply(action)
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self.requests, [])


class ContratDispatchTests(SimpleTestCase):
    def test_methodes_dispatch_existent(self):
        tree = ast.parse(inspect.getsource(services))
        appelees = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not (node.name.startswith('_dispatch')
                    or node.name == '_build_batch_op'):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == 'client'):
                    appelees.setdefault(sub.func.attr, set()).add(node.name)
        self.assertIn('update_adset_budget', appelees)
        manquantes = {m: sorted(f) for m, f in appelees.items()
                      if not hasattr(MetaClient, m)}
        self.assertEqual(manquantes, {})
