"""FIXPUB3 — Rattrapage COMPLET « tout l'historique ».

UNE tâche async par société enchaîne historique des insights + breakdowns +
créatifs live + leads (best-effort par étape) ; l'endpoint
``campaigns/backfill-complet/`` la met en file (202, gaté ``adsengine_manage``).
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import MetaConnection
from apps.adsengine.tasks import backfill_complet

User = get_user_model()

URL = '/api/django/adsengine/campaigns/backfill-complet/'


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


class BackfillCompletTaskTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='BC Co', slug='bc')

    def test_noop_without_live_connection(self):
        # Aucune connexion Meta → NO-OP propre (ran=False), aucun appel réseau.
        summary = backfill_complet(self.company.id)
        self.assertFalse(summary['ran'])
        self.assertEqual(summary['insights'], 0)
        self.assertEqual(summary['leads'], 0)

    def test_noop_when_company_missing(self):
        summary = backfill_complet(999999)
        self.assertFalse(summary['ran'])

    def test_runs_all_four_steps(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        cmd = ('apps.adsengine.management.commands.insights_backfill.'
               'backfill_insights_for_connection')
        with patch('apps.adsengine.meta_client.MetaClient.from_connection',
                   return_value=object()), \
                patch(cmd, return_value=3), \
                patch('apps.adsengine.tasks.sync_breakdowns_for_company',
                      return_value=2), \
                patch('apps.adsengine.tasks.sync_ad_creatives',
                      return_value=1), \
                patch('apps.adsengine.tasks.pull_ad_leads_for_company',
                      return_value=4):
            summary = backfill_complet(self.company.id)
        self.assertTrue(summary['ran'])
        self.assertEqual(summary['insights'], 3)
        self.assertEqual(summary['breakdowns'], 2)
        self.assertEqual(summary['creatives'], 1)
        self.assertEqual(summary['leads'], 4)

    def test_step_failure_does_not_abort_others(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        cmd = ('apps.adsengine.management.commands.insights_backfill.'
               'backfill_insights_for_connection')
        with patch('apps.adsengine.meta_client.MetaClient.from_connection',
                   return_value=object()), \
                patch(cmd, side_effect=RuntimeError('boom')), \
                patch('apps.adsengine.tasks.sync_breakdowns_for_company',
                      return_value=2), \
                patch('apps.adsengine.tasks.sync_ad_creatives',
                      return_value=1), \
                patch('apps.adsengine.tasks.pull_ad_leads_for_company',
                      return_value=4):
            summary = backfill_complet(self.company.id)
        # L'étape insights échoue (0) mais les suivantes s'exécutent quand même.
        self.assertTrue(summary['ran'])
        self.assertEqual(summary['insights'], 0)
        self.assertEqual(summary['breakdowns'], 2)
        self.assertEqual(summary['leads'], 4)


class BackfillCompletEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EP Co', slug='ep')
        self.manager = make_user(self.company, 'mgr', ['adsengine_manage'])
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def test_manager_queues_task(self):
        with patch('apps.adsengine.tasks.backfill_complet.delay') as delay:
            resp = auth(self.manager).post(URL)
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertTrue(resp.data['queued'])
        delay.assert_called_once_with(self.company.id)

    def test_queues_and_runs_eager(self):
        # « Queues under CELERY_TASK_ALWAYS_EAGER » : la tâche eager tourne
        # jusqu'au bout (NO-OP propre sans connexion Meta) → 202, aucun broker.
        from erp_agentique.celery import app as celery_app
        prev = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True
        self.addCleanup(
            lambda: setattr(celery_app.conf, 'task_always_eager', prev))
        resp = auth(self.manager).post(URL)
        self.assertEqual(resp.status_code, 202, resp.data)

    def test_viewer_forbidden(self):
        resp = auth(self.viewer).post(URL)
        self.assertEqual(resp.status_code, 403)
