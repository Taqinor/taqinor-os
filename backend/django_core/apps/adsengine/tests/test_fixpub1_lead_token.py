"""FIXPUB1 — Repli du token Lead Ads.

Sans ``META_LEAD_ADS_ACCESS_TOKEN`` (env), le pull-sync des leads retombe sur le
token sauvegardé de la MetaConnection active de la société ; l'env GAGNE quand les
deux sont posés. Seule la SOURCE du token est journalisée, jamais sa valeur.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import MetaConnection
from apps.adsengine.tasks import (
    _lead_ads_access_token, pull_meta_leads)


class LeadTokenFake:
    """Client Meta minimal : une ad porteuse d'un lead lead-form."""

    def get_ad_leads(self, ad_id, *, since_unix=None):
        if ad_id == 'ad1':
            return [{
                'id': 'lg-tok-1', 'created_time': '2026-07-16T10:00:00Z',
                'form_id': 'f1', 'ad_id': 'ad1',
                'field_data': [
                    {'name': 'phone_number', 'values': ['+212600112233']},
                ],
            }]
        return []

    def get_ad_targeting_ids(self, ad_id):
        return {'adset_id': 'as1', 'campaign_id': 'c1'}


class LeadAdsTokenResolutionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='TK Co', slug='tk')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'conn-tok'}, ad_account_id='act_1')

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='')
    def test_falls_back_to_connection_token(self):
        token, source = _lead_ads_access_token(self.conn)
        self.assertEqual(token, 'conn-tok')
        self.assertEqual(source, 'connexion')

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='env-tok')
    def test_env_wins_when_both_present(self):
        token, source = _lead_ads_access_token(self.conn)
        self.assertEqual(token, 'env-tok')
        self.assertEqual(source, 'env')

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='')
    def test_none_when_no_token_anywhere(self):
        other = Company.objects.create(nom='NoTok', slug='notok')
        conn = MetaConnection.objects.create(
            company=other, enabled=True, credentials={}, ad_account_id='act_2')
        token, source = _lead_ads_access_token(conn)
        self.assertEqual(token, '')
        self.assertIsNone(source)


class PullMetaLeadsTokenForwardTests(TestCase):
    """La tâche ``pull_meta_leads`` résout le token puis le transmet au service
    crm de création de lead (chemin de résolution des noms d'annonce)."""

    def setUp(self):
        self.company = Company.objects.create(nom='FW Co', slug='fw')
        self.conn = MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'conn-tok'}, ad_account_id='act_1')
        sync.sync_ads(self.company, [{'id': 'ad1'}])

    def _run_and_capture_token(self):
        with patch('apps.adsengine.meta_client.MetaClient.from_connection',
                   return_value=LeadTokenFake()), \
                patch('apps.crm.services.create_lead_from_meta_lead_ads') as spy:
            spy.return_value = object()
            pull_meta_leads()
        self.assertTrue(spy.called)
        return spy.call_args.kwargs.get('access_token')

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='')
    def test_connection_token_forwarded_when_env_absent(self):
        self.assertEqual(self._run_and_capture_token(), 'conn-tok')

    @override_settings(META_LEAD_ADS_ACCESS_TOKEN='env-tok')
    def test_env_token_forwarded_when_present(self):
        self.assertEqual(self._run_and_capture_token(), 'env-tok')
