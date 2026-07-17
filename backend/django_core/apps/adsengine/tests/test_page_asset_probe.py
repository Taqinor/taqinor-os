"""ADSDEEP16 — Tests de la sonde « accès asset Page » dans wiring-health :
vert quand un post se lit, rouge + correctif FR actionnable quand Meta refuse,
inconnu quand rien à sonder.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import sync
from apps.adsengine.meta_client import MetaError
from apps.adsengine.models import AdCreativeMirror, MetaConnection

User = get_user_model()
URL = '/api/django/adsengine/wiring-health/'


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


class PageAssetProbeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PA Co', slug='paco')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def _seed_creative_with_story(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        ad = sync.sync_ads(self.company, [{'id': 'ad1'}])[0]
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, effective_object_story_id='123_456')

    def test_unknown_without_connection(self):
        resp = auth(self.viewer).get(URL)
        self.assertEqual(resp.data['page_asset_access']['status'], 'inconnu')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_green_when_post_reads(self, mock_cls):
        self._seed_creative_with_story()
        client = mock_cls.from_connection.return_value
        client._request.return_value = {'id': '123_456'}
        resp = auth(self.viewer).get(URL)
        self.assertEqual(resp.data['page_asset_access']['status'], 'ok')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_red_with_actionable_fix_on_error(self, mock_cls):
        self._seed_creative_with_story()
        client = mock_cls.from_connection.return_value
        client._request.side_effect = MetaError('(#200) permission', code=200)
        resp = auth(self.viewer).get(URL)
        probe = resp.data['page_asset_access']
        self.assertEqual(probe['status'], 'error')
        self.assertIn('Assign Assets', probe['message'])
        self.assertIn('System User', probe['message'])

    def test_unknown_when_no_story_id(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        resp = auth(self.viewer).get(URL)
        self.assertEqual(resp.data['page_asset_access']['status'], 'inconnu')
