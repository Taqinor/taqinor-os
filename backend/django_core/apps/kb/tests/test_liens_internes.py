"""Tests XKB11 — Liens internes article↔article + rétroliens.

Couvre :
* lier A→B crée le lien (type_cible='article') ;
* la fiche de B liste A en rétrolien ;
* un article cible d'une autre société est rejeté ;
* une cible article inexistante est rejetée.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors
from apps.kb.models import KbArticle, KbArticleLien

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


class KbLiensInternesTests(TestCase):
    LIENS = '/api/django/kb/article-liens/'
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co_a = make_company('kb-lien-a', 'A')
        self.co_b = make_company('kb-lien-b', 'B')
        self.user_a = make_user(self.co_a, 'kb-lien-user-a')
        self.article_a = KbArticle.objects.create(company=self.co_a, titre='A')
        self.article_b = KbArticle.objects.create(company=self.co_a, titre='B')
        self.article_autre_co = KbArticle.objects.create(
            company=self.co_b, titre='Autre société')

    def test_lien_a_vers_b_created(self):
        api = auth(self.user_a)
        resp = api.post(self.LIENS, {
            'article': self.article_a.id, 'type_cible': 'article',
            'cible_id': self.article_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticleLien.objects.get(id=resp.data['id'])
        self.assertEqual(obj.type_cible, 'article')
        self.assertEqual(obj.cible_id, self.article_b.id)

    def test_retrolien_lists_source_article(self):
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible=KbArticleLien.TypeCible.ARTICLE,
            cible_id=self.article_b.id)
        retro = selectors.retroliens(self.article_b)
        self.assertEqual(len(retro), 1)
        self.assertEqual(retro[0]['id'], self.article_a.id)

    def test_retrolien_endpoint(self):
        KbArticleLien.objects.create(
            company=self.co_a, article=self.article_a,
            type_cible=KbArticleLien.TypeCible.ARTICLE,
            cible_id=self.article_b.id)
        resp = auth(self.user_a).get(
            f'{self.ARTICLES}{self.article_b.id}/retroliens/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in resp.data}
        self.assertIn(self.article_a.id, ids)

    def test_reject_cross_tenant_article_target(self):
        api = auth(self.user_a)
        resp = api.post(self.LIENS, {
            'article': self.article_a.id, 'type_cible': 'article',
            'cible_id': self.article_autre_co.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_reject_nonexistent_article_target(self):
        api = auth(self.user_a)
        resp = api.post(self.LIENS, {
            'article': self.article_a.id, 'type_cible': 'article',
            'cible_id': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_non_article_target_unaffected_by_validation(self):
        # Une cible non-article (ex. produit) reste validée sans exiger
        # l'existence d'un KbArticle correspondant (comportement historique).
        api = auth(self.user_a)
        resp = api.post(self.LIENS, {
            'article': self.article_a.id, 'type_cible': 'produit',
            'cible_id': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
