"""Tests XKB19 — Partage web public d'article.

Couvre :
* un article partagé s'ouvre SANS auth par son token ;
* dépublier (``actif=False``) rend 404 immédiatement ;
* un token expiré rend 410 ;
* un token inconnu rend 404 ;
* isolation cross-tenant à la création (article d'une autre société refusé) ;
* le compteur ``consultations`` s'incrémente à chaque accès public.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb.models import KbArticle, PartageArticleKb

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


class PartageArticleKbApiTests(TestCase):
    PARTAGES = '/api/django/kb/partages/'

    def setUp(self):
        self.co = make_company('kb-partage', 'P')
        self.user = make_user(self.co, 'kb-partage-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='SOP publique', corps='Contenu SOP')

    def test_create_partage_scopes_company_server_side(self):
        resp = auth(self.user).post(
            self.PARTAGES, {'article': self.article.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        partage = PartageArticleKb.objects.get(id=resp.data['id'])
        self.assertEqual(partage.company, self.co)
        self.assertEqual(partage.created_by, self.user)
        self.assertTrue(partage.token)

    def test_create_partage_rejects_cross_tenant_article(self):
        other_co = make_company('kb-partage-other', 'O')
        other_article = KbArticle.objects.create(
            company=other_co, titre='Autre', corps='X')
        resp = auth(self.user).post(
            self.PARTAGES, {'article': other_article.id}, format='json')
        self.assertEqual(resp.status_code, 400)


class PartageArticlePublicEndpointTests(TestCase):
    PUBLIC = '/api/django/kb/public/'

    def setUp(self):
        self.co = make_company('kb-partage-pub', 'PUB')
        self.user = make_user(self.co, 'kb-partage-pub-u1')
        self.article = KbArticle.objects.create(
            company=self.co, titre='FAQ publique', corps='Réponse détaillée')
        self.partage = PartageArticleKb.objects.create(
            company=self.co, article=self.article, created_by=self.user)

    def test_public_access_without_auth(self):
        client = APIClient()
        resp = client.get(f'{self.PUBLIC}{self.partage.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['titre'], 'FAQ publique')
        self.assertEqual(resp.data['corps'], 'Réponse détaillée')

    def test_unknown_token_returns_404(self):
        client = APIClient()
        resp = client.get(f'{self.PUBLIC}totally-unknown-token/')
        self.assertEqual(resp.status_code, 404)

    def test_depublier_makes_it_404_immediately(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/kb/partages/{self.partage.id}/depublier/')
        self.assertEqual(resp.status_code, 200, resp.data)

        client = APIClient()
        public_resp = client.get(f'{self.PUBLIC}{self.partage.token}/')
        self.assertEqual(public_resp.status_code, 404)

    def test_expired_token_returns_410(self):
        self.partage.expires_at = timezone.now() - timedelta(days=1)
        self.partage.save(update_fields=['expires_at'])

        client = APIClient()
        resp = client.get(f'{self.PUBLIC}{self.partage.token}/')
        self.assertEqual(resp.status_code, 410)

    def test_consultation_counter_increments(self):
        client = APIClient()
        client.get(f'{self.PUBLIC}{self.partage.token}/')
        client.get(f'{self.PUBLIC}{self.partage.token}/')
        self.partage.refresh_from_db()
        self.assertEqual(self.partage.consultations, 2)
