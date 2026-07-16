"""Tests XKB10 — Éditeur Markdown + pièces jointes + sommaire auto.

Couvre (portée backend) :
* ``corps_format`` (texte/markdown) se pose et se lit normalement ;
* le sommaire auto extrait les titres ATX Markdown dans l'ordre, et est vide
  pour un article texte brut (pas de faux positifs) ;
* ``('kb', 'kbarticle')`` est whitelisté dans ``records.ALLOWED_TARGETS`` :
  une pièce jointe/image peut être rattachée à un article KB (upload MinIO
  mocké — on teste le flux, pas boto3, comme le reste du dépôt) et apparaît
  ensuite listée pour cet article.
"""
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors
from apps.kb.models import KbArticle
from apps.records.models import ALLOWED_TARGETS

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


class KbCorpsFormatTests(TestCase):
    def setUp(self):
        self.co = make_company('kb-md', 'M')

    def test_default_corps_format_is_texte(self):
        article = KbArticle.objects.create(company=self.co, titre='X')
        self.assertEqual(article.corps_format, KbArticle.CorpsFormat.TEXTE)

    def test_corps_format_markdown_settable(self):
        article = KbArticle.objects.create(
            company=self.co, titre='X', corps_format='markdown')
        self.assertEqual(article.corps_format, 'markdown')


class KbSommaireAutoTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-som', 'S')
        self.user = make_user(self.co, 'kb-som-user')

    def test_sommaire_extracts_atx_headings_in_order(self):
        corps = (
            "# Titre principal\n"
            "Du texte.\n"
            "## Sous-titre A\n"
            "- item\n"
            "### Sous-sous-titre\n"
            "## Sous-titre B\n"
        )
        article = KbArticle.objects.create(
            company=self.co, titre='Doc', corps=corps, corps_format='markdown')
        sommaire = selectors.sommaire_article(article)
        self.assertEqual(sommaire, [
            {'niveau': 1, 'texte': 'Titre principal'},
            {'niveau': 2, 'texte': 'Sous-titre A'},
            {'niveau': 3, 'texte': 'Sous-sous-titre'},
            {'niveau': 2, 'texte': 'Sous-titre B'},
        ])

    def test_sommaire_empty_for_plain_text_article(self):
        article = KbArticle.objects.create(
            company=self.co, titre='Doc', corps='# Pas un sommaire',
            corps_format='texte')
        self.assertEqual(selectors.sommaire_article(article), [])

    def test_sommaire_endpoint(self):
        article = KbArticle.objects.create(
            company=self.co, titre='Doc', corps='# Un titre',
            corps_format='markdown')
        resp = auth(self.user).get(f'{self.ARTICLES}{article.id}/sommaire/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [{'niveau': 1, 'texte': 'Un titre'}])


class KbAttachmentWhitelistTests(TestCase):
    """XKB10/XKB13 — ``kb.kbarticle`` whitelisté pour pièces jointes."""

    def setUp(self):
        self.co = make_company('kb-attach', 'AT')
        self.user = make_user(self.co, 'kb-attach-user')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Article avec image')
        self.api = auth(self.user)

    def test_kbarticle_whitelisted_in_allowed_targets(self):
        self.assertIn(('kb', 'kbarticle'), ALLOWED_TARGETS)

    def test_upload_image_to_article_roundtrip(self):
        png = (b'\x89PNG\r\n\x1a\n' + b'\x00' * 64)

        def fake_store(file, **kwargs):  # accepte company= (SCA42)
            return ({'file_key': 'attachments/kb-test.png',
                     'filename': 'kb-test.png', 'size': len(png),
                     'mime': 'image/png'}, None)

        with mock.patch(
                'apps.records.views.store_attachment', side_effect=fake_store):
            up = BytesIO(png)
            up.name = 'kb-test.png'
            resp = self.api.post('/api/django/records/attachments/', {
                'model': 'kb.kbarticle', 'id': self.article.id, 'file': up,
            }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)

        lst = self.api.get(
            f'/api/django/records/attachments/'
            f'?model=kb.kbarticle&id={self.article.id}')
        data = lst.data['results'] if 'results' in lst.data else lst.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['filename'], 'kb-test.png')
