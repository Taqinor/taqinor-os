"""ADSDEEP13 — Tests du proxy previews : iframe servie pour un format
whitelisté, format hors liste rejeté (400), isolation société, 404 propre.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import sync
from apps.adsengine.models import MetaConnection

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


class FakeClient:
    def get_ad_previews(self, ad_id, ad_format):
        return f'<iframe src="preview/{ad_id}/{ad_format}"></iframe>'


class AdPreviewsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV Co', slug='pv')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        sync.sync_ads(self.company, [{'id': 'ad1', 'name': 'AD'}])

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_preview_served_for_whitelisted_format(self, mock_cls):
        mock_cls.from_connection.return_value = FakeClient()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/ads/ad1/previews/',
            {'format': 'INSTAGRAM_STORY'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['format'], 'INSTAGRAM_STORY')
        self.assertIn('<iframe', resp.data['body'])

    def test_non_whitelisted_format_rejected(self):
        resp = auth(self.viewer).get(
            '/api/django/adsengine/ads/ad1/previews/',
            {'format': 'DESKTOP_HACK'})
        self.assertEqual(resp.status_code, 400)

    def test_cross_company_ad_is_404(self):
        other = Company.objects.create(nom='PV B', slug='pvb')
        sync.sync_ads(other, [{'id': 'adX'}])
        resp = auth(self.viewer).get(
            '/api/django/adsengine/ads/adX/previews/')
        self.assertEqual(resp.status_code, 404)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        resp = auth(nobody).get('/api/django/adsengine/ads/ad1/previews/')
        self.assertEqual(resp.status_code, 403)
