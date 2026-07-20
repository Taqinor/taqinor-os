"""ADSDEEP12 — Tests du résolveur de médias : URL fraîche servie, rien de
persisté en base, 404 propre sans média / sans connexion, cache Redis.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import AdCreativeMirror, MetaConnection

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
    def get_video_source(self, video_id):
        return {'source': f'https://cdn.fb/{video_id}.mp4?exp=123'}

    def get_ad_image(self, image_hash):
        return {'permalink_url': f'https://fb/permalink/{image_hash}'}


class MediaResolveTests(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='MR Co', slug='mr')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_fresh_video_url_served_and_not_persisted(self, mock_cls):
        mock_cls.from_connection.return_value = FakeClient()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/media/v99/?kind=video')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['url'], 'https://cdn.fb/v99.mp4?exp=123')
        self.assertFalse(resp.data['cached'])
        # Rien de persisté : aucune URL CDN écrite en base.
        self.assertFalse(
            AdCreativeMirror.objects.filter(
                company=self.company).exclude(video_id='').exists())

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_image_permalink_served(self, mock_cls):
        mock_cls.from_connection.return_value = FakeClient()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/media/abc/?kind=image')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['url'], 'https://fb/permalink/abc')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_second_call_is_cached(self, mock_cls):
        fake = FakeClient()
        mock_cls.from_connection.return_value = fake
        api = auth(self.viewer)
        api.get('/api/django/adsengine/media/v99/?kind=video')
        resp = api.get('/api/django/adsengine/media/v99/?kind=video')
        self.assertTrue(resp.data['cached'])

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_picture_served_when_source_empty(self, mock_cls):
        # FIXPUB7 — Meta refuse la source mp4 (Page non assignée au System User)
        # mais renvoie la miniature : la réponse la porte en repli (200, pas 404).
        class RefusedVideo:
            def get_video_source(self, vid):
                return {'source': '', 'picture': f'https://cdn.fb/{vid}.jpg'}
        mock_cls.from_connection.return_value = RefusedVideo()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/media/vpic/?kind=video')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['url'], '')
        self.assertEqual(resp.data['picture'], 'https://cdn.fb/vpic.jpg')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_video_response_carries_picture_field(self, mock_cls):
        # La réponse porte TOUJOURS le champ ``picture`` (additif) à côté de l'URL.
        class VideoWithBoth:
            def get_video_source(self, vid):
                return {'source': f'https://cdn.fb/{vid}.mp4',
                        'picture': f'https://cdn.fb/{vid}.jpg'}
        mock_cls.from_connection.return_value = VideoWithBoth()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/media/vboth/?kind=video')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['url'], 'https://cdn.fb/vboth.mp4')
        self.assertEqual(resp.data['picture'], 'https://cdn.fb/vboth.jpg')

    @patch('apps.adsengine.meta_client.MetaClient')
    def test_missing_media_is_404(self, mock_cls):
        class Empty:
            def get_video_source(self, vid):
                return {}
        mock_cls.from_connection.return_value = Empty()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/media/none/?kind=video')
        self.assertEqual(resp.status_code, 404)

    def test_no_connection_is_404(self):
        MetaConnection.objects.filter(company=self.company).delete()
        resp = auth(self.viewer).get(
            '/api/django/adsengine/media/v99/?kind=video')
        self.assertEqual(resp.status_code, 404)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        resp = auth(nobody).get('/api/django/adsengine/media/v99/')
        self.assertEqual(resp.status_code, 403)
