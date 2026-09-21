"""Tests ZGED10 — Image de couverture + emoji/icône sur l'article KB.

Couvre :
* poser un emoji l'affiche dans la fiche (serializer) ;
* téléverser une couverture pose la clé et ``has_couverture`` devient vrai ;
* retirer la couverture (DELETE) supprime la clé ;
* le fichier ne vit jamais en base — seule sa clé MinIO l'est ;
* scoping société (une couverture/emoji ne fuit jamais entre sociétés).
"""
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb.models import KbArticle

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KbCouvertureEmojiTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-couv', 'C')
        self.user = make_user(self.co, 'kb-couv-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Article illustré', corps='X')

    def test_emoji_visible_in_serializer(self):
        self.article.emoji = '📘'
        self.article.save(update_fields=['emoji'])
        resp = auth(self.user).get(f'{self.ARTICLES}{self.article.id}/')
        self.assertEqual(resp.data['emoji'], '📘')

    def test_has_couverture_false_by_default(self):
        resp = auth(self.user).get(f'{self.ARTICLES}{self.article.id}/')
        self.assertFalse(resp.data['has_couverture'])

    def test_upload_couverture_sets_key_and_flag(self):
        png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64

        def fake_store(file):
            return ({'file_key': 'attachments/kb-cover.png',
                     'filename': 'kb-cover.png', 'size': len(png),
                     'mime': 'image/png'}, None)

        with mock.patch(
                'apps.records.storage.store_attachment',
                side_effect=fake_store):
            up = BytesIO(png)
            up.name = 'kb-cover.png'
            resp = auth(self.user).post(
                f'{self.ARTICLES}{self.article.id}/couverture/',
                {'fichier': up}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['has_couverture'])
        self.article.refresh_from_db()
        self.assertEqual(
            self.article.couverture_file_key, 'attachments/kb-cover.png')

    def test_remove_couverture_clears_key(self):
        self.article.couverture_file_key = 'attachments/kb-old.png'
        self.article.save(update_fields=['couverture_file_key'])
        resp = auth(self.user).delete(
            f'{self.ARTICLES}{self.article.id}/couverture/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['has_couverture'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.couverture_file_key, '')

    def test_couverture_image_proxy_returns_bytes(self):
        self.article.couverture_file_key = 'attachments/kb-cover.png'
        self.article.save(update_fields=['couverture_file_key'])
        with mock.patch(
                'apps.records.storage.fetch_attachment',
                return_value=(b'\x89PNG\r\n\x1a\n' + b'\x00' * 16, None)):
            resp = auth(self.user).get(
                f'{self.ARTICLES}{self.article.id}/couverture-image/')
        self.assertEqual(resp.status_code, 200)

    def test_couverture_image_proxy_404_without_couverture(self):
        resp = auth(self.user).get(
            f'{self.ARTICLES}{self.article.id}/couverture-image/')
        self.assertEqual(resp.status_code, 404)

    def test_couverture_scoped_to_company(self):
        other_co = make_company('kb-couv-other', 'O')
        other_user = make_user(other_co, 'kb-couv-other-u1')
        resp = auth(other_user).get(f'{self.ARTICLES}{self.article.id}/')
        self.assertEqual(resp.status_code, 404)
