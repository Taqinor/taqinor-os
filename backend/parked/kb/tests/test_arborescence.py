"""Tests XKB8 — Arborescence d'articles (pages imbriquées).

Couvre :
* création/déplacement d'un sous-article (``parent`` self-FK) ;
* rejet d'un cycle (parent = soi-même, ou déplacement sous un descendant) ;
* rejet d'un parent d'une autre société ;
* l'arbre (``/articles/arbre/``) imbrique correctement enfants sous parents,
  triés par ``ordre`` ;
* le réordonnancement (``ordre``) via l'action ``deplacer``.
"""
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


class KbArborescenceTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co_a = make_company('kb-arbo-a', 'A')
        self.co_b = make_company('kb-arbo-b', 'B')
        self.user_a = make_user(self.co_a, 'kb-arbo-user-a')
        self.user_b = make_user(self.co_b, 'kb-arbo-user-b')
        self.racine = KbArticle.objects.create(
            company=self.co_a, titre='Racine')
        self.enfant1 = KbArticle.objects.create(
            company=self.co_a, titre='Enfant 1', parent=self.racine, ordre=2)
        self.enfant2 = KbArticle.objects.create(
            company=self.co_a, titre='Enfant 2', parent=self.racine, ordre=1)
        self.petit_enfant = KbArticle.objects.create(
            company=self.co_a, titre='Petit-enfant', parent=self.enfant1)
        self.article_b = KbArticle.objects.create(
            company=self.co_b, titre='Article B')

    def test_create_sous_article(self):
        api = auth(self.user_a)
        resp = api.post(self.ARTICLES, {
            'titre': 'Nouveau sous-article', 'parent': self.racine.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['parent'], self.racine.id)

    def test_reject_self_parent(self):
        api = auth(self.user_a)
        resp = api.patch(
            f'{self.ARTICLES}{self.racine.id}/',
            {'parent': self.racine.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_reject_cycle_via_descendant(self):
        # Déplacer la racine sous son propre petit-enfant crée un cycle.
        api = auth(self.user_a)
        resp = api.patch(
            f'{self.ARTICLES}{self.racine.id}/',
            {'parent': self.petit_enfant.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_reject_cross_tenant_parent(self):
        api = auth(self.user_a)
        resp = api.post(self.ARTICLES, {
            'titre': 'X', 'parent': self.article_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_arbre_nests_children_sorted_by_ordre(self):
        resp = auth(self.user_a).get(f'{self.ARTICLES}arbre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        racines = [n for n in resp.data if n['id'] == self.racine.id]
        self.assertEqual(len(racines), 1)
        enfants = racines[0]['enfants']
        # Triés par ordre : enfant2 (ordre=1) avant enfant1 (ordre=2).
        self.assertEqual([e['id'] for e in enfants],
                         [self.enfant2.id, self.enfant1.id])
        # Le petit-enfant est imbriqué sous enfant1, pas remonté à la racine.
        enfant1_node = next(e for e in enfants if e['id'] == self.enfant1.id)
        self.assertEqual(
            [e['id'] for e in enfant1_node['enfants']],
            [self.petit_enfant.id])

    def test_arbre_isolation_cross_tenant(self):
        resp = auth(self.user_b).get(f'{self.ARTICLES}arbre/')
        self.assertEqual(resp.status_code, 200)
        ids = {n['id'] for n in resp.data}
        self.assertNotIn(self.racine.id, ids)
        self.assertIn(self.article_b.id, ids)

    def test_deplacer_action_reparents_and_reorders(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.ARTICLES}{self.petit_enfant.id}/deplacer/',
            {'parent': self.enfant2.id, 'ordre': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.petit_enfant.refresh_from_db()
        self.assertEqual(self.petit_enfant.parent_id, self.enfant2.id)
        self.assertEqual(self.petit_enfant.ordre, 5)

    def test_deplacer_to_root_sets_parent_null(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.ARTICLES}{self.enfant1.id}/deplacer/',
            {'parent': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.enfant1.refresh_from_db()
        self.assertIsNone(self.enfant1.parent_id)
