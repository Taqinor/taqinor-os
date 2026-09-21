"""Tests XKB15 — Favoris & récents KB.

Couvre :
* favoriser/défavoriser togglent (créer/supprimer la ligne) ;
* « Mes favoris » ne liste QUE les favoris de l'utilisateur courant ;
* les récents reflètent les dernières lectures de l'utilisateur SEUL (depuis
  ``KbLecture.lu_le``), dans l'ordre du plus récent au plus ancien ;
* isolation cross-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import KbArticle, KbFavori

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class KbFavorisTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'
    FAVORIS = '/api/django/kb/favoris/'

    def setUp(self):
        self.co = make_company('kb-fav', 'F')
        self.user1 = make_user(self.co, 'kb-fav-u1')
        self.user2 = make_user(self.co, 'kb-fav-u2')
        self.article = KbArticle.objects.create(company=self.co, titre='X')

    def test_toggle_favori_creates_then_removes(self):
        api = auth(self.user1)
        resp1 = api.post(f'{self.ARTICLES}{self.article.id}/toggler-favori/')
        self.assertEqual(resp1.status_code, 200, resp1.data)
        self.assertTrue(resp1.data['favori'])
        self.assertTrue(
            KbFavori.objects.filter(
                article=self.article, utilisateur=self.user1).exists())

        resp2 = api.post(f'{self.ARTICLES}{self.article.id}/toggler-favori/')
        self.assertFalse(resp2.data['favori'])
        self.assertFalse(
            KbFavori.objects.filter(
                article=self.article, utilisateur=self.user1).exists())

    def test_service_toggle_directly(self):
        actif1, favori1 = services.toggler_favori(
            self.article, utilisateur=self.user1)
        self.assertTrue(actif1)
        self.assertIsNotNone(favori1)
        self.assertEqual(favori1.company, self.co)

        actif2, favori2 = services.toggler_favori(
            self.article, utilisateur=self.user1)
        self.assertFalse(actif2)
        self.assertIsNone(favori2)

    def test_mes_favoris_only_shows_own(self):
        KbFavori.objects.create(
            company=self.co, article=self.article, utilisateur=self.user1)
        resp = auth(self.user2).get(self.FAVORIS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

        resp2 = auth(self.user1).get(self.FAVORIS)
        self.assertEqual(len(rows(resp2)), 1)

    def test_favori_create_forces_utilisateur_server_side(self):
        api = auth(self.user1)
        resp = api.post(self.FAVORIS, {
            'article': self.article.id, 'utilisateur': self.user2.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbFavori.objects.get(id=resp.data['id'])
        self.assertEqual(obj.utilisateur, self.user1)


class KbRecentsTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-recents', 'R')
        self.user1 = make_user(self.co, 'kb-recents-u1')
        self.user2 = make_user(self.co, 'kb-recents-u2')
        self.article_a = KbArticle.objects.create(company=self.co, titre='A')
        self.article_b = KbArticle.objects.create(company=self.co, titre='B')

    def test_recents_reflect_own_reads_only(self):
        services.marquer_lu(self.article_a, utilisateur=self.user1)
        services.marquer_lu(self.article_b, utilisateur=self.user2)
        recents = selectors.recents_pour_utilisateur(self.user1)
        ids = {r['id'] for r in recents}
        self.assertIn(self.article_a.id, ids)
        self.assertNotIn(self.article_b.id, ids)

    def test_recents_ordered_most_recent_first(self):
        services.marquer_lu(self.article_a, utilisateur=self.user1)
        services.marquer_lu(self.article_b, utilisateur=self.user1)
        recents = selectors.recents_pour_utilisateur(self.user1)
        self.assertEqual(recents[0]['id'], self.article_b.id)

    def test_recents_endpoint(self):
        services.marquer_lu(self.article_a, utilisateur=self.user1)
        resp = auth(self.user1).get(f'{self.ARTICLES}recents/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r['id'] for r in resp.data}
        self.assertIn(self.article_a.id, ids)

    def test_recents_empty_for_user_with_no_reads(self):
        self.assertEqual(selectors.recents_pour_utilisateur(self.user2), [])
