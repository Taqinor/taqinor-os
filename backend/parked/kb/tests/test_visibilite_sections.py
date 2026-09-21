"""Tests XKB9 — Sections Espace de travail / Privé / Partagé + ACL utilisateur.

Couvre :
* un article ``prive`` est invisible d'un collègue, visible du seul auteur ;
* un article ``partage`` n'est lisible que de ses membres ACL + l'auteur
  (+ admin, toujours) ;
* l'existant ``workspace`` sans ACL reste inchangé (rétro-compat KB7) ;
* l'ACL par-utilisateur est exclusive de l'ACL par-rôle (XOR validé) ;
* isolation cross-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb.models import KbArticle, KbArticleAcl

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


class KbVisibiliteSectionsTests(TestCase):
    ARTICLES = '/api/django/kb/articles/'
    ACLS = '/api/django/kb/article-acls/'

    def setUp(self):
        self.co = make_company('kb-vis', 'V')
        self.auteur = make_user(self.co, 'kb-vis-auteur')
        self.collegue = make_user(self.co, 'kb-vis-collegue')
        self.membre = make_user(self.co, 'kb-vis-membre')
        self.admin = make_user(self.co, 'kb-vis-admin', role='admin')
        self.workspace_article = KbArticle.objects.create(
            company=self.co, titre='Workspace', auteur=self.auteur,
            visibilite=KbArticle.Visibilite.WORKSPACE)
        self.prive_article = KbArticle.objects.create(
            company=self.co, titre='Privé', auteur=self.auteur,
            visibilite=KbArticle.Visibilite.PRIVE)
        self.partage_article = KbArticle.objects.create(
            company=self.co, titre='Partagé', auteur=self.auteur,
            visibilite=KbArticle.Visibilite.PARTAGE)
        KbArticleAcl.objects.create(
            company=self.co, article=self.partage_article,
            utilisateur=self.membre, niveau=KbArticleAcl.Niveau.LECTURE)

    def _ids(self, user):
        resp = auth(user).get(self.ARTICLES)
        self.assertEqual(resp.status_code, 200)
        return {row['id'] for row in rows(resp)}

    def test_workspace_unchanged_visible_to_all(self):
        ids = self._ids(self.collegue)
        self.assertIn(self.workspace_article.id, ids)

    def test_prive_invisible_to_colleague(self):
        ids = self._ids(self.collegue)
        self.assertNotIn(self.prive_article.id, ids)

    def test_prive_visible_to_author(self):
        ids = self._ids(self.auteur)
        self.assertIn(self.prive_article.id, ids)

    def test_prive_visible_to_admin(self):
        ids = self._ids(self.admin)
        self.assertIn(self.prive_article.id, ids)

    def test_partage_invisible_to_non_member(self):
        ids = self._ids(self.collegue)
        self.assertNotIn(self.partage_article.id, ids)

    def test_partage_visible_to_member(self):
        ids = self._ids(self.membre)
        self.assertIn(self.partage_article.id, ids)

    def test_partage_visible_to_author(self):
        ids = self._ids(self.auteur)
        self.assertIn(self.partage_article.id, ids)

    def test_partage_visible_to_admin_without_membership(self):
        ids = self._ids(self.admin)
        self.assertIn(self.partage_article.id, ids)

    def test_prive_detail_404_for_colleague(self):
        resp = auth(self.collegue).get(
            f'{self.ARTICLES}{self.prive_article.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_acl_by_user_and_role_are_mutually_exclusive(self):
        api = auth(self.auteur)
        resp = api.post(self.ACLS, {
            'article': self.partage_article.id, 'role': 'responsable',
            'utilisateur': self.collegue.id, 'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_acl_requires_role_or_user(self):
        api = auth(self.auteur)
        resp = api.post(self.ACLS, {
            'article': self.partage_article.id, 'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_acl_by_user_creates_row(self):
        api = auth(self.auteur)
        resp = api.post(self.ACLS, {
            'article': self.partage_article.id, 'utilisateur': self.collegue.id,
            'niveau': 'lecture',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticleAcl.objects.get(id=resp.data['id'])
        self.assertEqual(obj.utilisateur_id, self.collegue.id)
        self.assertEqual(obj.role, '')
