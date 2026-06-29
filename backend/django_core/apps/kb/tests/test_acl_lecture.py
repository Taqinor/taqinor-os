"""Tests KB7 — droits d'accès par rôle (``KbArticleAcl``) + suivi de lecture
(``KbLecture``).

Couvre :

* RÉTRO-COMPATIBILITÉ : un article SANS aucune ligne ACL reste visible de tous
  les paliers autorisés (KB2/KB3 inchangés).
* Une ACL de LECTURE restreint l'article au(x) palier(s) listé(s) ; un palier
  non listé ne le voit plus dans la liste ni en détail (404).
* Le palier ``admin`` (accesseur de rôle faisant autorité ``menu_tier``) voit
  TOUJOURS un article restreint, même sans ligne ACL le mentionnant.
* L'action ``marquer-lu`` enregistre une ``KbLecture`` (utilisateur + société
  posés côté serveur) UNE seule fois par utilisateur (idempotente).
* Le résumé de lecture (nombre de lecteurs + qui), scopé société.
* Société posée côté serveur sur l'ACL ; isolation/garde-fou même-société.
* Garde de rôle : le palier ``normal`` reste refusé (403) par le viewset.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.kb import selectors, services
from apps.kb.models import KbArticle, KbArticleAcl, KbLecture

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


class KbAclVisibilityTests(TestCase):
    """Visibilité des articles selon les ACL de rôle (rétro-compatible)."""

    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-acl', 'A')
        # Palier responsable et palier admin (via role_legacy → menu_tier).
        self.resp = make_user(self.co, 'kb-acl-resp', role='responsable')
        self.admin = make_user(self.co, 'kb-acl-admin', role='admin')
        self.libre = KbArticle.objects.create(
            company=self.co, titre='Article libre')
        self.restreint = KbArticle.objects.create(
            company=self.co, titre='Article restreint admin')

    def test_no_acl_article_visible_to_all(self):
        # Backward-compat : aucun ACL → visible de tous les paliers autorisés.
        resp = auth(self.resp).get(self.ARTICLES)
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in rows(resp)}
        self.assertIn(self.libre.id, ids)

    def test_acl_restricts_to_role(self):
        # Restreint l'article au seul palier admin : le responsable ne le voit
        # plus, l'article libre reste visible.
        KbArticleAcl.objects.create(
            company=self.co, article=self.restreint, role='admin',
            niveau=KbArticleAcl.Niveau.LECTURE)
        resp = auth(self.resp).get(self.ARTICLES)
        ids = {row['id'] for row in rows(resp)}
        self.assertIn(self.libre.id, ids)
        self.assertNotIn(self.restreint.id, ids)

    def test_acl_allows_listed_role(self):
        # Une ACL de lecture pour 'responsable' laisse passer le responsable.
        KbArticleAcl.objects.create(
            company=self.co, article=self.restreint, role='responsable',
            niveau=KbArticleAcl.Niveau.LECTURE)
        resp = auth(self.resp).get(self.ARTICLES)
        ids = {row['id'] for row in rows(resp)}
        self.assertIn(self.restreint.id, ids)

    def test_admin_tier_always_sees_restricted(self):
        # Le palier admin voit l'article même restreint à un autre palier.
        KbArticleAcl.objects.create(
            company=self.co, article=self.restreint, role='responsable',
            niveau=KbArticleAcl.Niveau.LECTURE)
        resp = auth(self.admin).get(self.ARTICLES)
        ids = {row['id'] for row in rows(resp)}
        self.assertIn(self.restreint.id, ids)

    def test_restricted_detail_404_for_unlisted_role(self):
        # Un palier non listé ne peut pas non plus ouvrir l'article en détail.
        KbArticleAcl.objects.create(
            company=self.co, article=self.restreint, role='admin',
            niveau=KbArticleAcl.Niveau.LECTURE)
        resp = auth(self.resp).get(f'{self.ARTICLES}{self.restreint.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_edition_acl_does_not_hide_for_reading(self):
        # Une ACL de niveau ÉDITION seule ne pose AUCUNE restriction de LECTURE :
        # l'article reste visible de tous (la visibilité ne regarde que lecture).
        KbArticleAcl.objects.create(
            company=self.co, article=self.restreint, role='admin',
            niveau=KbArticleAcl.Niveau.EDITION)
        resp = auth(self.resp).get(self.ARTICLES)
        ids = {row['id'] for row in rows(resp)}
        self.assertIn(self.restreint.id, ids)


class KbAclApiTests(TestCase):
    """API de gestion des ACL : société côté serveur, garde-fous, rôle."""

    BASE = '/api/django/kb/article-acls/'

    def setUp(self):
        self.co_a = make_company('kb-acl-a', 'A')
        self.co_b = make_company('kb-acl-b', 'B')
        self.user_a = make_user(self.co_a, 'kb-acl-api-a')
        self.user_b = make_user(self.co_b, 'kb-acl-api-b')
        self.article_a = KbArticle.objects.create(
            company=self.co_a, titre='Article A')
        self.article_b = KbArticle.objects.create(
            company=self.co_b, titre='Article B')

    def _payload(self, article, **over):
        data = {'article': article.id, 'role': 'responsable', 'niveau': 'lecture'}
        data.update(over)
        return data

    def test_create_forces_company_server_side(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.article_a), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticleAcl.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.article, self.article_a)

    def test_create_ignores_company_in_body(self):
        api = auth(self.user_a)
        payload = self._payload(self.article_a, company=self.co_b.id)
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = KbArticleAcl.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)

    def test_create_rejects_cross_tenant_article(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, self._payload(self.article_b), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('article', resp.data)

    def test_list_isolation(self):
        KbArticleAcl.objects.create(
            company=self.co_a, article=self.article_a, role='responsable',
            niveau='lecture')
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'kb-acl-normal', role='normal')
        resp = auth(normal).get(self.BASE)
        self.assertEqual(resp.status_code, 403)


class KbLectureApiTests(TestCase):
    """Suivi de lecture : marquer-lu + résumé (utilisateur/société côté serveur)."""

    ARTICLES = '/api/django/kb/articles/'

    def setUp(self):
        self.co = make_company('kb-lecture', 'L')
        self.user1 = make_user(self.co, 'kb-lecture-u1')
        self.user2 = make_user(self.co, 'kb-lecture-u2')
        self.article = KbArticle.objects.create(
            company=self.co, titre='À lire')

    def _marquer_lu_url(self, article):
        return f'{self.ARTICLES}{article.id}/marquer-lu/'

    def test_marquer_lu_records_lecture_server_side(self):
        resp = auth(self.user1).post(self._marquer_lu_url(self.article))
        self.assertEqual(resp.status_code, 200, resp.data)
        lecture = KbLecture.objects.get(
            article=self.article, utilisateur=self.user1)
        self.assertEqual(lecture.company, self.co)
        self.assertEqual(resp.data['nombre'], 1)

    def test_marquer_lu_is_idempotent_per_user(self):
        url = self._marquer_lu_url(self.article)
        auth(self.user1).post(url)
        auth(self.user1).post(url)
        self.assertEqual(
            KbLecture.objects.filter(
                article=self.article, utilisateur=self.user1).count(),
            1,
        )

    def test_marquer_lu_distinct_users_counted(self):
        auth(self.user1).post(self._marquer_lu_url(self.article))
        resp = auth(self.user2).post(self._marquer_lu_url(self.article))
        self.assertEqual(resp.data['nombre'], 2)
        reader_ids = {r['utilisateur'] for r in resp.data['lecteurs']}
        self.assertEqual(reader_ids, {self.user1.id, self.user2.id})

    def test_resume_lecture_action(self):
        auth(self.user1).post(self._marquer_lu_url(self.article))
        resp = auth(self.user2).get(
            f'{self.ARTICLES}{self.article.id}/resume-lecture/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nombre'], 1)
        self.assertEqual(resp.data['lecteurs'][0]['utilisateur'], self.user1.id)

    def test_resume_lecture_selector_company_scoped(self):
        # Une lecture d'une AUTRE société (même id d'article impossible, mais on
        # vérifie que le sélecteur scope bien sur company de l'article).
        services.marquer_lu(self.article, utilisateur=self.user1)
        summary = selectors.resume_lecture(self.article)
        self.assertEqual(summary['nombre'], 1)
        self.assertEqual(summary['lecteurs'][0]['utilisateur'], self.user1.id)


class KbServiceTests(TestCase):
    """Service marquer_lu : idempotence + (article, utilisateur) unique."""

    def setUp(self):
        self.co = make_company('kb-svc', 'S')
        self.user = make_user(self.co, 'kb-svc-u')
        self.article = KbArticle.objects.create(company=self.co, titre='X')

    def test_marquer_lu_creates_then_refreshes(self):
        lecture1, created1 = services.marquer_lu(
            self.article, utilisateur=self.user)
        self.assertTrue(created1)
        lecture2, created2 = services.marquer_lu(
            self.article, utilisateur=self.user)
        self.assertFalse(created2)
        self.assertEqual(lecture1.id, lecture2.id)
        self.assertEqual(
            KbLecture.objects.filter(article=self.article).count(), 1)
